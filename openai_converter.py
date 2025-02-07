import os
from openai import OpenAI
import base64
from PIL import Image
import io
from pdf2image import convert_from_path

class FlowchartConverter:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def pdf_to_image(self, pdf_path):
        images = convert_from_path(pdf_path)
        img_byte_arr = io.BytesIO()
        images[0].save(img_byte_arr, format='PNG')
        return base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')

    def process_file(self, file_path):
        is_pdf = file_path.lower().endswith('.pdf')
        base64_image = self.pdf_to_image(file_path) if is_pdf else self.encode_image(file_path)

        response = self.client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "system",
                    "content": """You are a specialized Mermaid diagram generator for IVR flowcharts. 
                    Generate precise Mermaid code following these rules:
                    1. Use 'flowchart TD' directive
                    2. Create unique node IDs based on the text content
                    3. Use proper node shapes:
                       - Decision diamonds: {text}
                       - Process boxes: [text]
                       - End/rounded nodes: (text)
                    4. Include all connection arrows and labels
                    5. Keep text content exactly as shown
                    6. Follow standard Mermaid indentation (4 spaces)
                    7. Ensure node IDs are valid JavaScript identifiers"""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Convert this IVR flowchart to Mermaid code. Preserve all text exactly as shown, use proper node shapes, and include all connections with their labels."
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
            temperature=0.1
        )

        mermaid_text = response.choices[0].message.content
        
        # Clean up the response
        mermaid_text = mermaid_text.replace('```mermaid\n', '').replace('```', '')
        if not mermaid_text.startswith('flowchart TD'):
            mermaid_text = 'flowchart TD\n' + mermaid_text
            
        # Additional formatting cleanup
        lines = mermaid_text.split('\n')
        formatted_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('flowchart'):
                line = '    ' + line
            formatted_lines.append(line)
            
        return '\n'.join(formatted_lines)

def process_flow_diagram(file_path: str, api_key: str) -> str:
    converter = FlowchartConverter(api_key)
    return converter.process_file(file_path)
