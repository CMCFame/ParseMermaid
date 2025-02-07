import base64
import io
from pdf2image import convert_from_path
from openai import OpenAI

PROMPT_TEXT = """You are a Mermaid diagram generator. Follow these rules:
1. Use 'flowchart TD'.
2. Create unique node IDs: replace spaces with underscores, append numbers for duplicates.
3. Use these node shapes:
   - Decisions: {text?}
   - Processes: ["Multi\nline text"]
   - End points: (Disconnect)
4. Preserve exact transition labels. Show all paths, retries, and termination points.
5. Use \n for line breaks.
Example:
flowchart TD
    A["Multi-line\ntext"] -->|exact label| B{Decision}
    B -->|yes| C[Process]
    B -->|no| A
"""

class FlowchartConverter:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def encode_image(self, file_path):
        if file_path.lower().endswith(".pdf"):
            img = convert_from_path(file_path)[0]
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format="PNG")
        else:
            with open(file_path, "rb") as image_file:
                img_byte_arr = io.BytesIO(image_file.read())

        return base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")

    def process_file(self, file_path):
        base64_image = self.encode_image(file_path)

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": PROMPT_TEXT},
                {"role": "user", "content": f"Convert this IVR flowchart:\ndata:image/jpeg;base64,{base64_image}"}
            ],
            max_tokens=4096,
            temperature=0.1,
        )

        mermaid_text = response.choices[0].message.content.strip()
        return mermaid_text if mermaid_text.startswith("flowchart TD") else f"flowchart TD\n{mermaid_text}"


def process_flow_diagram(file_path: str, api_key: str) -> str:
    return FlowchartConverter(api_key).process_file(file_path)
