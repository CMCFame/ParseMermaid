import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
from typing import List, Dict, Tuple, Optional, Set, Any
from dataclasses import dataclass
from PIL import Image
import os
import re

# Data Classes for Flow Elements
@dataclass
class Connection:
    source: str
    target: str
    label: Optional[str] = None
    condition: Optional[str] = None

@dataclass
class FlowElement:
    type: str
    text: str
    coordinates: Tuple[int, int, int, int]
    id: str
    connections: Set[str] = None
    conditions: Dict[str, str] = None

    def __post_init__(self):
        self.connections = set() if self.connections is None else self.connections
        self.conditions = {} if self.conditions is None else self.conditions

@dataclass
class ProcessedImage:
    binary: np.ndarray
    gray: np.ndarray
    edges: np.ndarray
    hierarchy: np.ndarray

class ARCOSPreprocessor:
    @staticmethod
    def enhance_image(image: np.ndarray) -> np.ndarray:
        # Enhance image quality for better text detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray)
        enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(denoised)
        return enhanced

    @staticmethod
    def preprocess_image(image: np.ndarray) -> ProcessedImage:
        # Initial preprocessing
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Binary threshold
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Edge detection
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
        
        # Find contours with hierarchy
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        return ProcessedImage(binary, gray, edges, hierarchy[0] if hierarchy is not None else None)

class ARCOSTextExtractor:
    def __init__(self):
        self.config = '--oem 3 --psm 6'
        self.keywords = {
            'welcome': ['welcome', 'callout from', 'press'],
            'input': ['input', 'enter', 'press'],
            'action': ['please', 'call', 'system'],
            'response': ['recorded', 'accept', 'decline'],
            'end': ['goodbye', 'disconnect', 'thank you']
        }

    def extract_text(self, roi: np.ndarray) -> str:
        # Enhance ROI for better OCR
        _, roi_binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((2,2), np.uint8)
        roi_processed = cv2.morphologyEx(roi_binary, cv2.MORPH_CLOSE, kernel)
        
        # Extract text
        text = pytesseract.image_to_string(roi_processed, config=self.config)
        return self.clean_text(text)

    def clean_text(self, text: str) -> str:
        # Remove special characters and normalize spaces
        text = re.sub(r'[^\w\s\-.,?()]', '', text)
        text = ' '.join(text.split())
        return text.strip()

    def classify_text(self, text: str) -> str:
        text_lower = text.lower()
        for element_type, patterns in self.keywords.items():
            if any(pattern in text_lower for pattern in patterns):
                return element_type
        return 'action'

class ARCOSFlowDetector:
    def __init__(self):
        self.preprocessor = ARCOSPreprocessor()
        self.text_extractor = ARCOSTextExtractor()
        self.min_contour_area = 1000
        self.next_id = 1
        
        # ARCOS-specific patterns
        self.arrow_patterns = ['-->', '->']
        self.condition_patterns = [
            r'if\s+([^,\.]+)',
            r'press\s+(\d+)',
            r'(\d+)\s*-\s*([a-zA-Z\s]+)'
        ]

    def process_file(self, file_path: str) -> str:
        # Load and convert file
        if file_path.lower().endswith('.pdf'):
            images = convert_from_path(file_path)
            image = np.array(images[0])
        else:
            image = cv2.imread(file_path)
            
        # Process image
        processed = self.preprocessor.preprocess_image(image)
        elements = self.detect_elements(processed)
        connections = self.detect_connections(elements, processed)
        
        return self.generate_mermaid(elements, connections)

    def detect_elements(self, processed: ProcessedImage) -> List[FlowElement]:
        contours, _ = cv2.findContours(processed.binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        elements = []
        
        for contour in contours:
            if cv2.contourArea(contour) < self.min_contour_area:
                continue
                
            element = self.process_contour(contour, processed.gray)
            if element:
                elements.append(element)
        
        return sorted(elements, key=lambda e: e.coordinates[1])

    def process_contour(self, contour: np.ndarray, gray: np.ndarray) -> Optional[FlowElement]:
        x, y, w, h = cv2.boundingRect(contour)
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        
        # Extract text
        roi = gray[y:y+h, x:x+w]
        text = self.text_extractor.extract_text(roi)
        
        if not text:
            return None
            
        # Determine type
        element_type = self.determine_element_type(approx, text)
        
        return FlowElement(
            type=element_type,
            text=text,
            coordinates=(x, y, w, h),
            id=f"{element_type}_{self.next_id}"
        )

    def determine_element_type(self, approx: np.ndarray, text: str) -> str:
        if len(approx) == 4:
            # Check if diamond
            angles = [self.angle_between_points(approx[i][0], approx[(i+1)%4][0], approx[(i+2)%4][0]) 
                     for i in range(4)]
            if max(angles) > 100 or min(angles) < 80:
                return 'input'
        
        return self.text_extractor.classify_text(text)

    @staticmethod
    def angle_between_points(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
        v1 = p1 - p2
        v2 = p3 - p2
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        return np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0)))

    def detect_connections(self, elements: List[FlowElement], processed: ProcessedImage) -> List[Connection]:
        connections = []
        
        # Use Hough lines to detect arrows
        lines = cv2.HoughLinesP(processed.edges, 1, np.pi/180, 50, 
                              minLineLength=30, maxLineGap=10)
        
        if lines is None:
            return connections
            
        for line in lines:
            x1, y1, x2, y2 = line[0]
            source = self.find_nearest_element((x1, y1), elements)
            target = self.find_nearest_element((x2, y2), elements)
            
            if source and target and source != target:
                condition = self.extract_condition(source, target, processed.gray)
                connections.append(Connection(source.id, target.id, condition=condition))
        
        return connections

    def find_nearest_element(self, point: Tuple[int, int], 
                           elements: List[FlowElement]) -> Optional[FlowElement]:
        nearest = None
        min_dist = float('inf')
        
        for element in elements:
            x, y, w, h = element.coordinates
            center = (x + w/2, y + h/2)
            dist = np.sqrt((point[0]-center[0])**2 + (point[1]-center[1])**2)
            
            if dist < min_dist:
                min_dist = dist
                nearest = element
                
        return nearest

    def extract_condition(self, source: FlowElement, target: FlowElement, 
                         gray: np.ndarray) -> Optional[str]:
        # Extract region between elements
        x1, y1, w1, h1 = source.coordinates
        x2, y2, w2, h2 = target.coordinates
        
        roi_x = min(x1, x2)
        roi_y = min(y1 + h1, y2)
        roi_w = abs(x2 - x1) + max(w1, w2)
        roi_h = abs(y2 - (y1 + h1))
        
        if roi_h <= 0 or roi_w <= 0:
            return None
            
        roi = gray[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        text = self.text_extractor.extract_text(roi)
        
        # Extract condition from text
        for pattern in self.condition_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
                
        return None

    def generate_mermaid(self, elements: List[FlowElement], 
                        connections: List[Connection]) -> str:
        mermaid_lines = ["flowchart TD"]
        
        # Node definitions
        for element in elements:
            node_text = element.text.replace('"', "'")
            
            if element.type == 'input':
                mermaid_lines.append(f'    {element.id}{{{{{node_text}}}}}')
            elif element.type == 'end':
                mermaid_lines.append(f'    {element.id}(("{node_text}"))')
            else:
                mermaid_lines.append(f'    {element.id}["{node_text}"]')
        
        # Connections
        added_connections = set()
        for conn in connections:
            if f"{conn.source}->{conn.target}" not in added_connections:
                if conn.condition:
                    mermaid_lines.append(f'    {conn.source} -->|"{conn.condition}"| {conn.target}')
                else:
                    mermaid_lines.append(f'    {conn.source} --> {conn.target}')
                added_connections.add(f"{conn.source}->{conn.target}")
        
        return '\n'.join(mermaid_lines)

def process_flow_diagram(file_path: str) -> str:
    detector = ARCOSFlowDetector()
    return detector.process_file(file_path)