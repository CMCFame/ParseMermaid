"""
Enhanced OpenAI converter with IVR-specific capabilities
"""
import os
import re
import logging
import base64
import io
from typing import Optional, List, Dict
from dataclasses import dataclass
from PIL import Image
from pdf2image import convert_from_path
import streamlit as st
from openai import OpenAI

@dataclass
class ConversionConfig:
    """Configuration for conversion process"""
    temperature: float = 0.1
    max_tokens: int = 4096
    supported_formats: set = None
    
    def __post_init__(self):
        if self.supported_formats is None:
            self.supported_formats = {'.pdf', '.png', '.jpg', '.jpeg'}

class IVRPromptLibrary:
    """IVR-specific prompting templates"""
    
    SYSTEM_PROMPT = """You are an expert in converting IVR (Interactive Voice Response) flow diagrams to Mermaid syntax. Focus on precise call flow logic and IVR-specific elements.

Required Elements to Identify and Convert:
1. Entry Points:
   - Call start nodes
   - Initial greetings
   - System initialization

2. User Interaction Points:
   - DTMF input collection
   - Menu option selections
   - PIN/code entry
   - Confirmation prompts

3. Decision Logic:
   - Yes/No branches
   - Multi-choice menus
   - Conditional routing
   - Input validation

4. Error Handling:
   - Invalid input recovery
   - Timeout handling
   - Retry loops
   - Maximum attempt limits

5. Call Flow Control:
   - Transfers
   - Call termination
   - System messages
   - Hold/wait states

Mermaid Syntax Requirements:
1. Start with: flowchart TD
2. Node Format:
   - Entry: A["Start Call"]
   - Menu: B{"Enter Selection"}
   - Action: C["Play Message"]
   - Input: D["Get DTMF"]
   - Exit: E["End Call"]

3. Connection Format:
   - Basic: -->
   - With DTMF: -->|"Press 1"|
   - Error: -->|"Invalid"|
   - Timeout: -.->

Example IVR Flow:
flowchart TD
    A["Start Call"] --> B{"Main Menu"}
    B -->|"Press 1"| C["Check Balance"]
    B -->|"Press 2"| D["Transfer to Agent"]
    B -->|"Invalid"| E["Retry Message"]
    E --> B
    C --> F["End Call"]
    D --> F"""

    ERROR_RECOVERY = """If the diagram is unclear or complex:
1. Focus on core call flow first
2. Add error handling paths
3. Include retry loops for invalid inputs
4. Ensure all paths lead to resolution"""

class ImageProcessor:
    """Enhanced image processing capabilities"""
    
    @staticmethod
    def process_image(image_path: str, max_size: tuple = (1000, 1000)) -> Image.Image:
        """Process and optimize image for conversion"""
        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            # Resize if too large
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Enhance contrast for better text recognition
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.2)
            
            return img

    @staticmethod
    def pdf_to_image(pdf_path: str, dpi: int = 200) -> Image.Image:
        """Convert PDF to image with optimization"""
        images = convert_from_path(pdf_path, dpi=dpi, first_page=1, last_page=1)
        if not images:
            raise ValueError("Failed to extract image from PDF")
        return images[0]

class FlowchartConverter:
    """Enhanced OpenAI-powered flowchart converter"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize converter with configuration"""
        self.api_key = (
            api_key or 
            st.secrets.get("OPENAI_API_KEY") or 
            os.getenv("OPENAI_API_KEY")
        )
        
        if not self.api_key:
            raise ValueError("OpenAI API key not found")
        
        self.client = OpenAI(api_key=self.api_key)
        self.config = ConversionConfig()
        self.logger = logging.getLogger(__name__)
        self.image_processor = ImageProcessor()

    def convert_diagram(self, file_path: str) -> str:
        """
        Convert flow diagram to Mermaid syntax
        
        Args:
            file_path: Path to diagram file
            
        Returns:
            str: Mermaid diagram syntax
        """
        try:
            # Validate file
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in self.config.supported_formats:
                raise ValueError(f"Unsupported format. Supported: {self.config.supported_formats}")
            
            # Process image
            if file_ext == '.pdf':
                image = self.image_processor.pdf_to_image(file_path)
            else:
                image = self.image_processor.process_image(file_path)
            
            # Convert to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            base64_image = base64.b64encode(buffered.getvalue()).decode()
            
            # Make API call
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": IVRPromptLibrary.SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Convert this IVR flow diagram to Mermaid syntax. "
                                       "Ensure accurate capture of call flow logic, menu options, "
                                       "and error handling paths."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            # Extract and clean Mermaid code
            mermaid_text = self._clean_mermaid_code(
                response.choices[0].message.content
            )
            
            # Validate syntax
            if not self._validate_mermaid_syntax(mermaid_text):
                # Try recovery with simpler conversion
                self.logger.warning("Initial conversion failed validation, attempting recovery")
                return self._attempt_recovery_conversion(base64_image)
            
            return mermaid_text
            
        except Exception as e:
            self.logger.error(f"Conversion failed: {str(e)}")
            raise RuntimeError(f"Diagram conversion error: {str(e)}")

    def _clean_mermaid_code(self, raw_text: str) -> str:
        """Clean and format Mermaid code"""
        # Extract code from markdown blocks if present
        code_match = re.search(r'```(?:mermaid)?\n(.*?)```', raw_text, re.DOTALL)
        if code_match:
            raw_text = code_match.group(1)
        
        # Ensure proper flowchart definition
        if not raw_text.strip().startswith('flowchart TD'):
            raw_text = f'flowchart TD\n{raw_text}'
        
        # Clean up whitespace and empty lines
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        return '\n'.join(lines)

    def _validate_mermaid_syntax(self, mermaid_text: str) -> bool:
        """Validate basic Mermaid syntax"""
        required_elements = [
            # Must have flowchart definition
            r'flowchart\s+TD',
            # Must have at least one node
            r'\w+\s*[\["{\(]',
            # Must have at least one connection
            r'-->'
        ]
        
        return all(re.search(pattern, mermaid_text) for pattern in required_elements)

    def _attempt_recovery_conversion(self, base64_image: str) -> str:
        """Attempt simplified conversion for recovery"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": f"{IVRPromptLibrary.SYSTEM_PROMPT}\n{IVRPromptLibrary.ERROR_RECOVERY}"
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Convert this diagram, focusing on core call flow "
                                       "and essential error handling only."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=self.config.max_tokens,
                temperature=0.3  # More conservative for recovery
            )
            
            return self._clean_mermaid_code(
                response.choices[0].message.content
            )
            
        except Exception as e:
            raise RuntimeError(f"Recovery conversion failed: {str(e)}")

def process_flow_diagram(file_path: str, api_key: Optional[str] = None) -> str:
    """Convenience wrapper for diagram conversion"""
    converter = FlowchartConverter(api_key)
    return converter.convert_diagram(file_path)