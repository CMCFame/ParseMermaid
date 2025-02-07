import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from PIL import Image
import os

@dataclass
class FlowElement:
    type: str  # 'rectangle', 'diamond', 'circle'
    text: str
    coordinates: Tuple[int, int, int, int]
    id: str

@dataclass
class Connection:
    from_id: str
    to_id: str
    label: Optional[str] = None

class FlowDetector:
    def __init__(self):
        self.min_contour_area = 1000
        self.padding = 10
        self.next_id = 1

    def process_file(self, file_path: str) -> str:
        """Process PDF or image file and return Mermaid diagram."""
        if file_path.lower().endswith('.pdf'):
            images = convert_from_path(file_path)
            image = np.array(images[0])  # Process first page for now
        else:
            image = cv2.imread(file_path)
        
        return self.process_image(image)

    def process_image(self, image: np.ndarray) -> str:
        """Convert image to Mermaid diagram."""
        # Preprocessing
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Detect elements
        elements = []
        for contour in contours:
            if cv2.contourArea(contour) < self.min_contour_area:
                continue
                
            element = self._analyze_shape(contour, gray)
            if element:
                elements.append(element)
        
        # Detect connections
        connections = self._detect_connections(edges, elements)
        
        # Generate Mermaid
        return self._generate_mermaid(elements, connections)

    def _analyze_shape(self, contour, gray_image) -> Optional[FlowElement]:
        """Analyze contour to determine shape and extract text."""
        approx = cv2.approxPolyDP(contour, 0.04 * cv2.arcLength(contour, True), True)
        
        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)
        
        # Extract text using OCR
        roi = gray_image[y-self.padding:y+h+self.padding, x-self.padding:x+w+self.padding]
        text = pytesseract.image_to_string(roi).strip()
        
        # Determine shape type
        if len(approx) == 4:
            # Check if rectangle or diamond
            angles = self._get_angles(approx)
            if all(abs(angle - 90) < 10 for angle in angles):
                shape_type = 'rectangle'
            else:
                shape_type = 'diamond'
        elif len(approx) > 8:
            shape_type = 'circle'
        else:
            return None
            
        return FlowElement(
            type=shape_type,
            text=text,
            coordinates=(x, y, w, h),
            id=f"node{self.next_id}"
        )

    def _detect_connections(self, edges: np.ndarray, elements: List[FlowElement]) -> List[Connection]:
        """Detect connections between elements."""
        connections = []
        
        # Use HoughLines to detect lines
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=50, maxLineGap=10)
        
        if lines is None:
            return connections
            
        for line in lines:
            x1, y1, x2, y2 = line[0]
            
            # Find connected elements
            from_element = self._find_nearest_element((x1, y1), elements)
            to_element = self._find_nearest_element((x2, y2), elements)
            
            if from_element and to_element and from_element != to_element:
                connections.append(Connection(
                    from_id=from_element.id,
                    to_id=to_element.id
                ))
        
        return connections

    def _generate_mermaid(self, elements: List[FlowElement], connections: List[Connection]) -> str:
        """Generate Mermaid diagram from detected elements and connections."""
        mermaid = ["flowchart TD"]
        
        # Add nodes
        for element in elements:
            if element.type == 'diamond':
                mermaid.append(f'    {element.id}{{"{ element.text }"}}')
            elif element.type == 'circle':
                mermaid.append(f'    {element.id}(("{element.text}"))')
            else:  # rectangle
                mermaid.append(f'    {element.id}["{element.text}"]')
        
        # Add connections
        for conn in connections:
            mermaid.append(f'    {conn.from_id} --> {conn.to_id}')
        
        return '\n'.join(mermaid)

    @staticmethod
    def _get_angles(points) -> List[float]:
        """Calculate angles between connected points."""
        angles = []
        n = len(points)
        for i in range(n):
            p1 = points[i][0]
            p2 = points[(i+1)%n][0]
            p3 = points[(i+2)%n][0]
            
            angle = np.degrees(np.arctan2(p3[1]-p2[1], p3[0]-p2[0]) - 
                             np.arctan2(p1[1]-p2[1], p1[0]-p2[0]))
            angle = abs(angle)
            if angle > 180:
                angle = 360 - angle
            angles.append(angle)
        return angles

    @staticmethod
    def _find_nearest_element(point: Tuple[int, int], elements: List[FlowElement]) -> Optional[FlowElement]:
        """Find the nearest element to a point."""
        min_dist = float('inf')
        nearest = None
        
        for element in elements:
            x, y, w, h = element.coordinates
            center = (x + w/2, y + h/2)
            dist = np.sqrt((point[0]-center[0])**2 + (point[1]-center[1])**2)
            
            if dist < min_dist:
                min_dist = dist
                nearest = element
        
        return nearest

def process_flow_diagram(file_path: str) -> str:
    """Main function to process flow diagrams."""
    detector = FlowDetector()
    return detector.process_file(file_path)