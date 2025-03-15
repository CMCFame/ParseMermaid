"""
Enhanced OpenAI converter with specific handling for call flow diagrams.
Converts image to Mermaid with focus on actual flow elements and excludes
notes, comments, and decorative elements.
"""
import os
import base64
import io
import tempfile
from typing import Optional, Tuple
from PIL import Image
import fitz  # PyMuPDF
import openai
import streamlit as st

def convert_image_to_mermaid(image_file):
    """Convert an uploaded image to mermaid syntax using OpenAI's vision capabilities."""
    try:
        # Check if OpenAI API key is available
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None, "OpenAI API key not found"
        
        client = openai.OpenAI(api_key=api_key)
        
        # Check if it's a PDF
        if image_file.name.lower().endswith('.pdf'):
            images = extract_images_from_pdf(image_file)
            if not images:
                return None, "Could not extract images from PDF"
            # Use the first page for simplicity
            image_content = images[0]
        else:
            # Process regular image files
            image = Image.open(image_file)
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            image_content = buffered.getvalue()
        
        # Encode image to base64
        base64_image = base64.b64encode(image_content).decode('utf-8')
        
        # Improved prompt for cleaner Mermaid generation
        prompt = """
        Your task is to convert this call flow diagram to Mermaid.js flowchart syntax.
        
        IMPORTANT: FOCUS ONLY ON THE ACTUAL FLOW DIAGRAM ELEMENTS
        
        INCLUDE:
        1. Main flow nodes and their connections
        2. Decision points (questions or choices)
        3. Process nodes (actions or messages)
        4. All button press options and their destinations
        5. Exact text in nodes (use <br/> for line breaks)
        6. Connection labels showing button presses or options
        
        EXCLUDE:
        1. Notes or comments sections
        2. Footer information and copyright notices
        3. Class definitions for styling
        4. Company information or confidentiality statements
        5. Page numbers and references
        6. Diagram titles or legends not part of the flow
        7. Any decorative or non-functional elements
        
        FORMAT REQUIREMENTS:
        1. Use flowchart TD for top-down flow
        2. Use ["text"] for process nodes
        3. Use {"text"} for decision nodes
        4. Use -->|"label"| for connections with labels
        5. Use proper node IDs (A, B, C, etc.)
        6. Format text exactly as shown - preserve all button options
        
        EXAMPLE (good format):
        ```
        flowchart TD
            A["Welcome<br/>Press 1 for Support"] -->|"1"| B{"Support Options"}
            B -->|"1 - Technical"| C["Technical Support"]
            B -->|"2 - Billing"| D["Billing Support"]
        ```
        
        Return ONLY the Mermaid code, nothing else.
        """
        
        # Make request to OpenAI
        response = client.chat.completions.create(
            model="gpt-4o",  # Use the appropriate model
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]
                }
            ],
            max_tokens=4000
        )
        
        # Extract the mermaid code from the response
        mermaid_code = response.choices[0].message.content.strip()
        
        # Clean up the mermaid code
        if "```mermaid" in mermaid_code:
            mermaid_code = mermaid_code.split("```mermaid")[1]
        elif "```" in mermaid_code:
            mermaid_code = mermaid_code.split("```")[1]
        
        if "```" in mermaid_code:
            mermaid_code = mermaid_code.split("```")[0]
        
        mermaid_code = mermaid_code.strip()
        
        # Remove any remaining class definitions or subgraphs
        cleaned_lines = []
        skip_line = False
        for line in mermaid_code.split('\n'):
            if line.strip().startswith('class ') or line.strip().startswith('classDef '):
                continue
            if line.strip().startswith('subgraph '):
                skip_line = True
                continue
            if skip_line and line.strip() == 'end':
                skip_line = False
                continue
            if not skip_line:
                cleaned_lines.append(line)
        
        mermaid_code = '\n'.join(cleaned_lines)
        
        # Validate mermaid code has proper flowchart structure
        if not mermaid_code.strip().startswith('flowchart '):
            # Add flowchart TD if missing
            mermaid_code = 'flowchart TD\n' + mermaid_code
            
        return mermaid_code, None
    
    except Exception as e:
        return None, f"Error converting image to Mermaid: {str(e)}"

def extract_images_from_pdf(pdf_file):
    """Extract images from a PDF file."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            temp_pdf.write(pdf_file.read())
            temp_pdf_path = temp_pdf.name
        
        images = []
        doc = fitz.open(temp_pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
            img_data = pix.tobytes("png")
            images.append(img_data)
        
        os.unlink(temp_pdf_path)
        return images
    
    except Exception as e:
        st.error(f"Error extracting images from PDF: {str(e)}")
        return []

def process_flow_diagram(file_path, api_key=None):
    """Process a flow diagram image and convert it to Mermaid syntax."""
    try:
        # Set API key
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            
        # Read file
        with open(file_path, "rb") as f:
            file_content = f.read()
            
        # Create a file-like object
        file_obj = io.BytesIO(file_content)
        file_obj.name = os.path.basename(file_path)
        
        # Convert to Mermaid
        mermaid_code, error = convert_image_to_mermaid(file_obj)
        
        if error:
            raise Exception(error)
            
        return mermaid_code
        
    except Exception as e:
        raise Exception(f"Error processing flow diagram: {str(e)}")