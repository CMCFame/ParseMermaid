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
                        "content": """You are an expert at converting complex flowcharts and call flows into precise Mermaid diagram syntax. 
                        Generate a clean, executable Mermaid flowchart that accurately represents the input diagram.
                        
                        Requirements:
                        - Use 'flowchart TD' as the first line
                        - Node IDs should be unique (A1, B1, etc.)
                        - Use descriptive node texts
                        - Capture all connections and decision paths
                        - Use arrow styles that match the original diagram's flow"""
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Convert this diagram to Mermaid syntax"},
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
                temperature=0.2
            )
            
            # Extract Mermaid code
            mermaid_text = response.choices[0].message.content.strip()
            
            # Clean up potential code block markers
            mermaid_text = re.sub(r'^```(mermaid)?|```$', '', mermaid_text, flags=re.MULTILINE).strip()
            
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
        st.error(f"Diagram conversion error: {e}")
        return ""