import os
import re
from typing import Optional
import logging
import base64
import io

import streamlit as st
import openai  # Make sure you have openai installed
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
        
        # ### CHANGE: Revised system prompt for stricter rules
        system_instructions = """You are an expert Mermaid diagram generator. 
        Your task: 
        1. Perform OCR or otherwise interpret the provided image of a flowchart. 
        2. Output a strictly valid Mermaid flowchart with no syntax errors. 
        3. Always enclose the result in triple backticks ```mermaid ... ``` and begin with `flowchart TD`.
        4. For each node:
           - Use unique IDs (A1, B1, C1, etc.). 
           - Enclose node text in square brackets "[ ... ]" or curly braces "{ ... }" if it's a decision. 
           - Retain original text as much as possible without paraphrasing. 
        5. For edges:
           - Keep label text EXACTLY as in the diagram (like "1 - Yes", "2 - No", etc.). 
           - Use the syntax -->|"label"| for labeled edges, and --> for unlabeled edges. 
        6. Ensure it starts with: flowchart TD
        7. Provide no additional commentary outside the mermaid code block.
        """

        messages = [
            {"role": "system", "content": system_instructions},
            {
                "role": "user",
                "content": f"Please convert this flowchart image into Mermaid code. The image is base64-encoded:\n\ndata:image/png;base64,{base64_image}"
            }
        ]

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",  # or "gpt-3.5-turbo" if GPT-4 is unavailable
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
                # If GPT didn't wrap in code fences, fallback
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
