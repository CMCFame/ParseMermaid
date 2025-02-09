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
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Image encoding error: {e}")
            raise

    def _pdf_to_image(self, pdf_path: str) -> str:
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
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        base64_image = (
            self._pdf_to_image(file_path) 
            if file_ext == '.pdf' 
            else self._encode_image(file_path)
        )
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """
You are an expert Mermaid diagram generator specializing in complex flowchart conversions.

STRICT FORMAT:
1. Always start with 'flowchart TD'
2. Enclose node text in square brackets: ["Node Text"]
3. Use curly brackets {} for decision nodes
4. Ensure all edges are properly formatted
5. Remove unnecessary line breaks and escape sequences
                        """
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Convert this call flow diagram into Mermaid syntax. Ensure correct formatting and structure."},
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
                temperature=0.1
            )
            
            mermaid_text = response.choices[0].message.content.strip()
            
            return self._format_mermaid_code(mermaid_text)
        except Exception as e:
            self.logger.error(f"Conversion failed: {e}")
            raise
    
    def _format_mermaid_code(self, mermaid_text: str) -> str:
        mermaid_text = re.sub(r'```mermaid\\n(.*?)\\n```', r'\1', mermaid_text, flags=re.DOTALL)
        mermaid_text = re.sub(r'\\n', '\\n', mermaid_text)  # Ensure proper line breaks
        mermaid_text = re.sub(r'\b(if|decision|question)\b', r'{\1}', mermaid_text, flags=re.IGNORECASE)
        mermaid_text = re.sub(r'\[([^\]]+)\]', r'["\1"]', mermaid_text)  # Ensure square brackets
        mermaid_text = re.sub(r'\{([^{}]+)\}', r'{\1}', mermaid_text)  # Fix decision nodes
        mermaid_text = re.sub(r'-->\|([^|]+)\|', r'-->|\1|', mermaid_text)  # Fix edge formatting
        return mermaid_text

def process_flow_diagram(file_path: str, api_key: Optional[str] = None) -> str:
    try:
        converter = FlowchartConverter(api_key)
        return converter.convert_diagram(file_path)
    except Exception as e:
        raise RuntimeError(f"Diagram conversion error: {e}")
