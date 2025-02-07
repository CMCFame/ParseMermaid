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
9. Double-check every node has matching quotation marks

Example format:
flowchart TD
    A1["Welcome text\nMore text"] -->|"label text"| B1{"Decision text"}
    B1 -->|"yes"| C1["Action text"]
    C1 --> D1((End text))"""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Convert this IVR flowchart to Mermaid code following the system message format EXACTLY. Ensure every node uses the correct syntax and all connections are properly labeled."
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