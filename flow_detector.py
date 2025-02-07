import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from PIL import Image
import os
import re

@dataclass
class FlowElement:
    type: str  # 'rectangle', 'diamond', 'circle', 'action'
    text: str
    coordinates: Tuple[int, int, int, int]
    id: str
    connections: Set[str] = None  # IDs of connected elements

    def __post_init__(self):
        if self.connections is None:
            self.connections = set()

class FlowDetector:
    def __init__(self):
        self.min_contour_area = 500  # Reduced to catch smaller elements
        self.padding = 5
        self.next_id = 1
        self.connection_threshold = 30  # Pixels distance for connection detection

    def process_file(self, file_path: str) -> str:
        if file_path.lower().endswith('.pdf'):
            images = convert_from_path(file_path)
            image = np.array(images[0])
        else:
            image = cv2.imread(file_path)
        return self.process_image(image)

    def process_image(self, image: np.ndarray) -> str:
        # Preprocessing
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Find contours
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        # Detect elements
        elements = []
        processed_areas = np.zeros_like(binary)
        
        for i, contour in enumerate(contours):
            if cv2.contourArea(contour) < self.min_contour_area:
                continue
                
            # Check if area already processed
            x, y, w, h = cv2.boundingRect(contour)
            if np.any(processed_areas[y:y+h, x:x+w]):
                continue
                
            element = self._analyze_shape(contour, gray)
            if element:
                elements.append(element)
                # Mark area as processed
                cv2.drawContours(processed_areas, [contour], -1, 255, -1)

        # Detect arrows and connections
        self._detect_connections(binary, elements)
        
        # Generate Mermaid code
        return self._generate_mermaid(elements)

    def _analyze_shape(self, contour, gray_image) -> Optional[FlowElement]:
        approx = cv2.approxPolyDP(contour, 0.04 * cv2.arcLength(contour, True), True)
        x, y, w, h = cv2.boundingRect(contour)
        
        # Extract and clean text
        roi = gray_image[max(0, y-self.padding):min(gray_image.shape[0], y+h+self.padding), 
                        max(0, x-self.padding):min(gray_image.shape[1], x+w+self.padding)]
        text = pytesseract.image_to_string(roi)
        text = self._clean_text(text)
        
        if not text:
            return None
            
        # Determine shape type
        if len(approx) == 4:
            aspect_ratio = float(w)/h
            if 0.95 <= aspect_ratio <= 1.05:  # Square-ish
                shape_type = "decision"
            else:
                shape_type = "rectangle"
        elif len(approx) > 6:
            shape_type = "circle"
        else:
            shape_type = "action"  # Default type
            
        element_id = f"node{self.next_id}"
        self.next_id += 1
        
        return FlowElement(
            type=shape_type,
            text=text,
            coordinates=(x, y, w, h),
            id=element_id
        )

    def _clean_text(self, text: str) -> str:
        # Remove newlines and extra spaces
        text = ' '.join(text.split())
        # Remove special characters
        text = re.sub(r'[^\w\s\-.,?]', '', text)
        return text.strip()

    def _detect_connections(self, binary_image: np.ndarray, elements: List[FlowElement]):
        # Detect arrows using morphological operations
        kernel = np.ones((3,3), np.uint8)
        arrows = cv2.morphologyEx(binary_image, cv2.MORPH_OPEN, kernel)
        
        # Find arrow contours
        arrow_contours, _ = cv2.findContours(arrows, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        for arrow in arrow_contours:
            if cv2.contourArea(arrow) < self.min_contour_area / 2:  # Arrows are usually smaller
                continue
                
            # Get arrow endpoints
            points = cv2.approxPolyDP(arrow, 0.1 * cv2.arcLength(arrow, True), True)
            if len(points) < 2:
                continue
                
            start_point = tuple(points[0][0])
            end_point = tuple(points[-1][0])
            
            # Find connected elements
            from_element = self._find_nearest_element(start_point, elements)
            to_element = self._find_nearest_element(end_point, elements)
            
            if from_element and to_element and from_element != to_element:
                from_element.connections.add(to_element.id)

    def _generate_mermaid(self, elements: List[FlowElement]) -> str:
        mermaid_lines = ["flowchart TD"]
        
        # Node definitions
        for element in elements:
            if element.type == "decision":
                mermaid_lines.append(f'    {element.id}{{{{{element.text}}}}}')
            elif element.type == "circle":
                mermaid_lines.append(f'    {element.id}(({element.text}))')
            else:
                mermaid_lines.append(f'    {element.id}["{element.text}"]')
        
        # Connection definitions
        added_connections = set()
        for element in elements:
            for connected_id in element.connections:
                connection = f"{element.id}-->{connected_id}"
                if connection not in added_connections:
                    mermaid_lines.append(f"    {connection}")
                    added_connections.add(connection)
        
        return '\n'.join(mermaid_lines)

    def _find_nearest_element(self, point: Tuple[int, int], 
                            elements: List[FlowElement]) -> Optional[FlowElement]:
        min_dist = float('inf')
        nearest = None
        
        for element in elements:
            x, y, w, h = element.coordinates
            center = (x + w/2, y + h/2)
            dist = np.sqrt((point[0]-center[0])**2 + (point[1]-center[1])**2)
            
            if dist < min_dist and dist < self.connection_threshold:
                min_dist = dist
                nearest = element
        
        return nearest

def process_flow_diagram(file_path: str) -> str:
    detector = FlowDetector()
    return detector.process_file(file_path)