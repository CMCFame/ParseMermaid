import os
import base64
import io
from PIL import Image
from pdf2image import convert_from_path
import openai

class FlowchartConverter:
    def __init__(self, api_key):
        # Assign the API key to openai
        openai.api_key = api_key

    def encode_image(self, image_path: str) -> str:
        """
        Reads an image file from disk and returns its base64-encoded string.
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def pdf_to_image(self, pdf_path: str) -> str:
        """
        Converts the first page of a PDF to PNG in memory, then returns
        its base64-encoded string.
        """
        images = convert_from_path(pdf_path)
        img_byte_arr = io.BytesIO()
        # Save the first page as PNG
        images[0].save(img_byte_arr, format="PNG")
        return base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")

    def process_file(self, file_path: str) -> str:
        """
        Determines if the file is a PDF or an image, extracts it as a base64 string,
        and sends it to the OpenAI ChatCompletion API requesting Mermaid code.
        """
        # Determine file type
        is_pdf = file_path.lower().endswith(".pdf")
        # Convert PDF or Image to base64-encoded string
        base64_image = (
            self.pdf_to_image(file_path) if is_pdf else self.encode_image(file_path)
        )

        # Create the ChatCompletion request
        response = openai.ChatCompletion.create(
            model="gpt-4",  # or "gpt-3.5-turbo" if you do not have GPT-4 access
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a specialized Mermaid diagram generator for IVR flowcharts. "
                        "Read the provided flowchart (via base64 image). "
                        "Your output must be valid Mermaid code for a 'flowchart TD' diagram. "
                        "You must: "
                        "1) Maintain exact punctuation, text, and line breaks for each node. "
                        "2) Use the following shapes:\n"
                        "   - [text] for standard process nodes\n"
                        "   - {text} for decisions\n"
                        "   - (text) for start/end nodes\n"
                        "3) Include all arrows, with their labels. "
                        "4) Do not omit text. Keep it verbatim, including parentheses. "
                        "5) Do not add or remove words. "
                        "6) Indent with 4 spaces. "
                        "7) Return only Mermaid code starting with 'flowchart TD' and nothing else."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        "Convert this IVR flowchart to Mermaid code, including all decision points, "
                        "labels, and the exact text shown:\n"
                        f"data:image/jpeg;base64,{base64_image}"
                    )
                }
            ],
            max_tokens=3000,       # Adjust as needed
            temperature=0.0        # Lower temperature reduces paraphrasing
        )

        # Extract the mermaid text
        mermaid_text = response.choices[0].message.content
        # Normalize line endings
        mermaid_text = mermaid_text.replace("\r\n", "\n").strip()

        # Ensure it starts with "flowchart TD"
        if not mermaid_text.startswith("flowchart TD"):
            mermaid_text = "flowchart TD\n" + mermaid_text

        # Optionally indent all lines except the directive
        lines = mermaid_text.split("\n")
        formatted_lines = []
        for line in lines:
            line = line.rstrip()
            if line and not line.startswith("flowchart"):
                line = "    " + line
            formatted_lines.append(line)

        return "\n".join(formatted_lines)

def process_flow_diagram(file_path: str, api_key: str) -> str:
    """
    A helper function to directly invoke the converter and return the processed Mermaid code.
    """
    converter = FlowchartConverter(api_key)
    return converter.process_file(file_path)

if __name__ == "__main__":
    # Example usage:
    your_api_key = "YOUR_OPENAI_API_KEY"
    diagram_path = "path/to/your_flowchart.pdf"  # or .jpg, .png, etc.
    try:
        result = process_flow_diagram(diagram_path, your_api_key)
        print("Mermaid Output:\n")
        print(result)
    except Exception as e:
        print("Error processing file:")
        print(e)
