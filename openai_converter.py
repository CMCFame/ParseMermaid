import os
import re
from typing import Optional
import logging
import base64
import io

import streamlit as st
import openai
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
        
        openai.api_key = self.api_key

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
        Convert flow diagram to Mermaid syntax.
        Supports PDF and image files.
        Uses model="gpt-4o" under openai==0.28.0
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
        
        # System instructions for mermaid generation
        system_instructions = """You are an expert Mermaid diagram generator. 
1. Interpret the provided flowchart image (base64).
2. Output a valid Mermaid flowchart with no syntax errors.
3. Always enclose the code in triple backticks (```mermaid ... ```).
4. Start with 'flowchart TD'.
5. Use unique node IDs (A1, B1, C1, etc.).
6. Retain original text from the flowchart as best you can without paraphrasing.
7. Label edges exactly as in the diagram, e.g. -->|"1 - Yes"| or --> for unlabeled edges.
"""

        messages = [
            {"role": "system", "content": system_instructions},
            {
                "role": "user",
                "content": f"Convert this flowchart image (base64) to Mermaid:\n\ndata:image/png;base64,{base64_image}"
            }
        ]

        try:
            # Using pinned openai==0.28.0 => ChatCompletion.create is still valid
            response = openai.ChatCompletion.create(
                model="gpt-4o",  # Your custom GPT-4-like model name
                messages=messages,
                max_tokens=2048,
                temperature=0.0
            )
            
            raw_response = response.choices[0].message.content.strip()
            self.logger.info(f"Raw GPT Response: {raw_response}")

            # Extract the code between ```mermaid ... ```
            mermaid_match = re.search(r'```mermaid\s+(.*?)```', raw_response, re.DOTALL | re.IGNORECASE)
            if mermaid_match:
                mermaid_text = mermaid_match.group(1).strip()
            else:
                # If GPT didn't wrap in code fences, fallback to entire text
                mermaid_text = raw_response

            # Ensure it starts with flowchart TD
            if not mermaid_text.startswith('flowchart TD'):
                mermaid_text = f'flowchart TD\n{mermaid_text}'
            
            return mermaid_text
        
        except Exception as e:
            self.logger.error(f"Conversion failed: {e}")
            raise

def process_flow_diagram(file_path: str, api_key: Optional[str] = None) -> str:
    """
    Wrapper function for file diagram conversion.
    Pins openai==0.28.0 and uses "gpt-4o".
    
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
