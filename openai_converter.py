import os
import re
from typing import Optional
import logging
import base64
import io

import streamlit as st
from openai import OpenAI
from pdf2image import convert_from_path
from PIL import Image

class FlowchartConverter:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI converter with configurable API key sources
        
        Priority for API key:
        1. Passed argument
        2. Streamlit secrets
        3. Environment variable
        """
        self.api_key = (
            api_key or 
            st.secrets.get("OPENAI_API_KEY") or 
            os.getenv("OPENAI_API_KEY")
        )
        
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. "
                "Please provide via argument, Streamlit secrets, or environment variable."
            )
        
        self.client = OpenAI(api_key=self.api_key)
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

    def _encode_image(self, image_path: str) -> str:
        """Convert image to base64 encoded string"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Image encoding error: {e}")
            raise

    def _pdf_to_image(self, pdf_path: str) -> str:
        """Convert PDF's first page to base64 image"""
        try:
            images = convert_from_path(pdf_path, first_page=1, last_page=1)
            
            if not images:
                raise ValueError("No images extracted from PDF")
            
            img_byte_arr = io.BytesIO()
            images[0].save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            return base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
        except Exception as e:
            self.logger.error(f"PDF conversion error: {e}")
            raise

    def convert_diagram(self, file_path: str) -> str:
        """
        Convert flow diagram to Mermaid syntax
        
        Supports PDF and image files
        """
        # Validate file
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Determine file type
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Encode image/PDF
        base64_image = (
            self._pdf_to_image(file_path) 
            if file_ext == '.pdf' 
            else self._encode_image(file_path)
        )
        
        # OpenAI API call
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert Mermaid diagram generator specializing in complex flowchart conversions. 

MERMAID SYNTAX GUIDELINES:
1. Always start with 'flowchart TD'
2. Use unique node IDs (A1, B1, C1, etc.)
3. Node Text Formatting:
   - Use <br> for line breaks
   - Escape special characters
   - Enclose text in square brackets with quotes
4. Connection Syntax:
   - Standard connection: -->
   - Labeled connection: -->| label |
   - Capture all paths, including error and retry flows
5. Decision Nodes:
   - Use {} for decision/diamond nodes
6. Preserve Complete Flow:
   - Capture all decision points
   - Include all original messaging
   - Maintain logical flow
7. Handle:
   - Retry paths
   - Invalid inputs
   - Alternative routes

CRITICAL REQUIREMENTS:
- 100% Accuracy to Source Diagram
- No Information Loss
- Exact Path Replication"""
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Convert this complex call flow diagram to precise Mermaid syntax."},
                            {
                                "type": "image_url", 
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.1  # Highly deterministic
            )
            
            # Extract Mermaid code
            mermaid_text = response.choices[0].message.content.strip()
            
            # Clean up potential code block markers
            mermaid_text = re.sub(r'^```(mermaid)?|```$', '', mermaid_text, flags=re.MULTILINE).strip()
            
            # Ensure starts with flowchart definition
            return mermaid_text if mermaid_text.startswith('flowchart') else f'flowchart TD\n{mermaid_text}'
        
        except Exception as e:
            self.logger.error(f"Conversion failed: {e}")
            raise

def process_flow_diagram(file_path: str, api_key: Optional[str] = None) -> str:
    """
    Wrapper function for file diagram conversion
    
    Args:
        file_path: Path to diagram file (PDF or image)
        api_key: Optional OpenAI API key
    
    Returns:
        Mermaid diagram syntax
    """
    try:
        converter = FlowchartConverter(api_key)
        return converter.convert_diagram(file_path)
    except Exception as e:
        raise RuntimeError(f"Diagram conversion error: {e}")