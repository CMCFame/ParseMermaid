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
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except FileNotFoundError:
            raise ValueError(f"Image file not found: {image_path}")
        except Exception as e:
            raise RuntimeError(f"Error encoding image: {str(e)}")

    def pdf_to_image(self, pdf_path):
        try:
            images = convert_from_path(pdf_path)
            if not images:
                raise ValueError("No pages found in the PDF file")
            
            # Process all pages or select specific ones
            selected_page = 0  # You can modify this to allow selection of a page
            image = images[selected_page]
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            return base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
        except FileNotFoundError:
            raise ValueError(f"PDF file not found: {pdf_path}")
        except Exception as e:
            raise RuntimeError(f"Error converting PDF to image: {str(e)}")

    def process_file(self, file_path):
        try:
            is_pdf = file_path.lower().endswith('.pdf')
            
            if is_pdf:
                base64_image = self.pdf_to_image(file_path)
            else:
                base64_image = self.encode_image(file_path)

            # Create the system prompt
            system_prompt = """You are a specialized Mermaid diagram generator for IVR flowcharts. 
Generate precise Mermaid code following these rules:
1. Use 'flowchart TD' directive
2. Create unique node IDs based on the text content
3. Use proper node shapes:
   - Decision diamonds: {text}
   - Process boxes: [text]
   - End/rounded nodes: (text)
4. Include all connection arrows and labels
5. Keep text content exactly as shown
6. Follow Mermaid syntax standards
7. Return only the code, no explanations or additional text"""

            response = self.client.chat.completions.create(
                model="gpt-4",  # Ensure this is correct (e.g., "gpt-4")
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Convert the following image to Mermaid flowchart format: {base64_image}"
                    }
                ],
                temperature=0.3,
            )

            mermaid_code = response.choices[0].message.content

            # Validate the response
            if not mermaid_code:
                raise ValueError("No valid Mermaid code was generated")

            return mermaid_code.strip()

        except Exception as e:
            raise RuntimeError(f"Error processing file: {str(e)}")

    def save_mermaid_file(self, output_path, mermaid_code):
        try:
            with open(output_path, "w") as f:
                f.write(mermaid_code)
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to save Mermaid file: {str(e)}")

# Example usage:
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python flowchart_converter.py <input_file> [output_file]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "flowchart.md"

    try:
        converter = FlowchartConverter(api_key="your-api-key-here")
        mermaid_code = converter.process_file(input_path)
        converter.save_mermaid_file(output_path, mermaid_code)
        print(f"Mermaid code saved to {output_path}")
    except Exception as e:
        print(f"Error: {str(e)}")
