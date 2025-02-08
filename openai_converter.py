import os
from openai import OpenAI
import base64
from PIL import Image
import io
from pdf2image import convert_from_path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FlowchartConverter:
    def __init__(self, api_key):
        """Initialize the converter with OpenAI API key"""
        self.client = OpenAI(api_key=api_key)

    def encode_image(self, image_path):
        """Convert an image file to base64 string"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding image: {str(e)}")
            raise

    def pdf_to_image(self, pdf_path):
        """Convert first page of PDF to image and return as base64 string"""
        try:
            # Convert PDF to image
            images = convert_from_path(pdf_path, first_page=1, last_page=1)
            if not images:
                raise ValueError("No images extracted from PDF")
            
            # Convert PIL image to bytes
            img_byte_arr = io.BytesIO()
            images[0].save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            return base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error converting PDF to image: {str(e)}")
            raise

    def process_file(self, file_path):
        """Process a file (PDF or image) and return Mermaid diagram code"""
        try:
            # Determine if file is PDF or image
            is_pdf = file_path.lower().endswith('.pdf')
            
            # Convert file to base64
            base64_image = self.pdf_to_image(file_path) if is_pdf else self.encode_image(file_path)

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a specialized Mermaid diagram generator for IVR flowcharts. Follow these EXACT rules:

1. Start with 'flowchart TD'
2. Node ID format: Use A1, B1, C1, etc.
3. Node syntax must be EXACTLY:
   - For all rectangular boxes: nodeId["exact text content"]
   - For decision diamonds: nodeId{"exact text content"}
   - For end nodes: nodeId((exact text content))
4. Connection syntax must be EXACTLY:
   - With label: sourceId -->|"label text"| targetId
   - Without label: sourceId --> targetId
5. Text content:
   - Use \n for line breaks
   - Keep ALL text exactly as shown
   - Include ALL parentheses in text content
6. Indentation:
   - Use 4 spaces for each line after flowchart TD
7. Never use [ ] for decision nodes or { } for regular nodes
8. Preserve ALL connection labels exactly as shown
9. Double-check every node has matching quotation marks"""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Convert this IVR flowchart to Mermaid code following the system message format EXACTLY. Make sure every node uses the correct syntax and all connections are properly labeled."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0
            )

            # Extract and clean up the Mermaid code
            mermaid_text = response.choices[0].message.content
            
            # Remove code block markers if present
            mermaid_text = mermaid_text.replace('```mermaid\n', '').replace('```', '')
            
            # Ensure the diagram starts with flowchart TD
            if not mermaid_text.startswith('flowchart TD'):
                mermaid_text = 'flowchart TD\n' + mermaid_text
            
            # Format the code with proper indentation
            lines = mermaid_text.split('\n')
            formatted_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('flowchart'):
                    line = '    ' + line
                formatted_lines.append(line)
            
            return '\n'.join(formatted_lines)

        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            raise

def process_flow_diagram(file_path: str, api_key: str) -> str:
    """
    Wrapper function to process a flow diagram file and return Mermaid code
    
    Args:
        file_path: Path to the input file (PDF, PNG, or JPEG)
        api_key: OpenAI API key
    
    Returns:
        str: Generated Mermaid diagram code
    """
    try:
        converter = FlowchartConverter(api_key)
        return converter.process_file(file_path)
    except Exception as e:
        logger.error(f"Error in process_flow_diagram: {str(e)}")
        raise