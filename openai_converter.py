import os
import re
import base64
import io
import logging
from typing import Optional

import streamlit as st
from openai import OpenAI
from pdf2image import convert_from_path
from PIL import Image


class FlowchartConverter:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI converter with configurable API key sources.
        Priority for API key:
        1. Passed argument
        2. Environment variable
        3. Streamlit secrets
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError("OpenAI API key is required. Provide via argument, environment variable, or Streamlit secrets.")

        self.client = OpenAI(api_key=self.api_key)
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

    def _encode_image(self, image_path: str) -> str:
        """Convert image to base64 encoded string."""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Image encoding error: {e}")
            raise RuntimeError(f"Image encoding failed: {e}")

    def _pdf_to_image(self, pdf_path: str) -> str:
        """Convert the first page of a PDF to a base64 image."""
        try:
            images = convert_from_path(pdf_path, first_page=1, last_page=1)
            if not images:
                raise ValueError("No images extracted from PDF.")

            img_byte_arr = io.BytesIO()
            images[0].save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)

            return base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
        except Exception as e:
            self.logger.error(f"PDF conversion error: {e}")
            raise RuntimeError(f"PDF conversion failed: {e}")

    def clean_mermaid_code(self, text: str) -> str:
        """Extracts and cleans Mermaid code from AI-generated responses."""
        match = re.search(r'```mermaid\n(.*?)\n```', text, re.DOTALL)
        return match.group(1).strip() if match else text.strip()

    def convert_diagram(self, file_path: str) -> str:
        """
        Convert a flowchart diagram to Mermaid syntax.
        Supports both PDFs and images.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_ext = os.path.splitext(file_path)[1].lower()
        base64_image = self._pdf_to_image(file_path) if file_ext == '.pdf' else self._encode_image(file_path)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert in Mermaid.js flowchart generation. 
                        Convert the provided diagram into **strictly valid** Mermaid syntax.

                        REQUIREMENTS:
                        - Use `flowchart TD`
                        - **Action nodes**: Use square brackets `[]`
                        - **Decision nodes**: Use curly braces `{}`
                        - **Ensure all edges are preserved** (`A --> B`, `B --|Yes|--> C`)
                        - **Maintain loop and retry handling**
                        - **Output ONLY Mermaid syntax** in triple backticks (` ``` `). No extra text.
                        """
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Convert this call flow diagram to Mermaid with 100% accuracy."},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.1
            )

            mermaid_text = response.choices[0].message.content.strip()
            return self.clean_mermaid_code(mermaid_text)

        except Exception as e:
            self.logger.error(f"AI conversion failed: {e}")
            raise RuntimeError(f"Mermaid conversion error: {e}")


def process_flow_diagram(file_path: str, api_key: Optional[str] = None) -> str:
    """
    Wrapper function for diagram conversion.
    Args:
        file_path: Path to diagram file (PDF or image)
        api_key: Optional OpenAI API key
    Returns:
        Cleaned Mermaid syntax.
    """
    try:
        converter = FlowchartConverter(api_key)
        return converter.convert_diagram(file_path)
    except Exception as e:
        raise RuntimeError(f"Diagram conversion error: {e}")
