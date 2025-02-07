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
        img_byte_arr = img_byte_arr.getvalue()
        return base64.b64encode(img_byte_arr).decode('utf-8')

    def process_file(self, file_path):
        is_pdf = file_path.lower().endswith('.pdf')
        base64_image = self.pdf_to_image(file_path) if is_pdf else self.encode_image(file_path)

        vision_response = self.client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this flowchart image. Describe the flow nodes and their connections in detail, including all text content and decision paths. Focus especially on the exact text in each node and the conditions for each connection."
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
            max_tokens=4096
        )

        description = vision_response.choices[0].message.content

        mermaid_response = self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert in converting flowchart descriptions to Mermaid syntax. Create precise Mermaid flowchart code that exactly matches the described nodes, connections, and conditions. Use proper Mermaid shapes: [] for process nodes, {} for decision nodes, () for rounded nodes. Include all text content exactly as given."
                },
                {
                    "role": "user",
                    "content": f"Convert this flowchart description to Mermaid syntax: {description}"
                }
            ],
            max_tokens=4096
        )

        return mermaid_response.choices[0].message.content

def process_flow_diagram(file_path: str, api_key: str) -> str:
    converter = FlowchartConverter(api_key)
    return converter.process_file(file_path)