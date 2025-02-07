import os
import base64
import io
from PIL import Image
from pdf2image import convert_from_path
from openai import OpenAI


class FlowchartConverter:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def pdf_to_image(self, pdf_path):
        images = convert_from_path(pdf_path)
        img_byte_arr = io.BytesIO()
        images[0].save(img_byte_arr, format="PNG")
        return base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")

    def process_file(self, file_path):
        is_pdf = file_path.lower().endswith(".pdf")
        base64_image = self.pdf_to_image(file_path) if is_pdf else self.encode_image(file_path)

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        """You are a specialized Mermaid diagram generator for IVR flowcharts. 
                        Generate precise Mermaid code following these strict rules:

                        1. Use 'flowchart TD' directive
                        2. Create unique node IDs using these patterns:
                           - For duplicate node types: append numbers (Goodbye1, Goodbye2)
                           - Replace spaces with underscores in IDs
                           - Keep original text EXACTLY preserved in labels
                        3. Node shapes must match:
                           - Decisions: {text?}
                           - Processes: [\"Multi\nline text\"]
                           - End points: (Disconnect)
                        4. Connection rules:
                           - ALWAYS preserve EXACT transition labels (e.g., '7 - not home')
                           - Include ALL possible exit paths from each node
                           - Show return loops (e.g., invalid entries going back)
                        5. Text preservation requirements:
                           - Maintain original line breaks using \n
                           - Keep all punctuation and parentheses
                           - Preserve exact numbering (e.g., 'Press 3, if...')
                           - Include placeholder text exactly as shown (e.g., '(callout reason)')
                        6. Formatting rules:
                           - Use 4-space indentation
                           - No markdown backticks in output
                           - Start nodes vertically under flowchart TD
                        7. Required elements:
                           - All nodes from the visual flowchart
                           - Every transition option shown in image
                           - Error handling paths and retries
                           - Disconnect nodes for termination points

                        Example structure to match:
                        flowchart TD
                            A[\"Multi-line\ntext\"] -->|exact label| B{Decision}
                            B -->|yes| C[Process]
                            B -->|no| A"""
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Convert this IVR flowchart to Mermaid code, including all decision points, "
                        "labels, and the exact text shown:\n"
                        f"data:image/jpeg;base64,{base64_image}"
                    ),
                },
            ],
            max_tokens=4096,
            temperature=0.1,
        )

        mermaid_text = response.choices[0].message.content

        # Clean up the response
        mermaid_text = mermaid_text.replace("\nmermaid\n", "").strip()
        if not mermaid_text.startswith("flowchart TD"):
            mermaid_text = "flowchart TD\n" + mermaid_text

        # Additional formatting cleanup
        lines = mermaid_text.split("\n")
        formatted_lines = [
            "    " + line.strip() if line and not line.startswith("flowchart") else line.strip()
            for line in lines
        ]

        return "\n".join(formatted_lines)


def process_flow_diagram(file_path: str, api_key: str) -> str:
    converter = FlowchartConverter(api_key)
    return converter.process_file(file_path)
