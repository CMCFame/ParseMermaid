import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import yaml
import tempfile
import os
import traceback
from PIL import Image

from parse_mermaid import parse_mermaid, MermaidParser
from graph_to_ivr import graph_to_ivr, IVRTransformer
from openai_converter import process_flow_diagram

DEFAULT_FLOWS = {
    "Simple Callout": """flowchart TD
    A["Start of Call"] --> B{"Are you available?"}
    B -->|"1 - Yes"| C["Accept Callout"]
    B -->|"3 - No"| D["Decline Callout"]
    C --> E["Record Response"]
    D --> E
    E --> F["End Call"]""",
    
    "PIN Change Flow": """flowchart TD
    A["Enter Current PIN"] --> B{"PIN Correct?"}
    B -->|"Yes"| C["Enter New PIN"]
    B -->|"No"| D["Access Denied"]
    C --> E{"Confirm New PIN"}
    E -->|"Match"| F["PIN Updated Successfully"]
    E -->|"No Match"| G["PIN Change Failed"]
    D --> H["End"]
    F --> H
    G --> H""",
    
    "Transfer Request": """flowchart TD
    A["Transfer Request"] --> B{"Transfer Possible?"}
    B -->|"Yes"| C["Initiate Transfer"]
    B -->|"No"| D["Transfer Denied"]
    C --> E["Confirm Transfer"]
    D --> F["End Call"]
    E --> F"""
}

def save_temp_file(content: str, suffix: str = ".js") -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(content)
        return f.name

def validate_mermaid(mermaid_text: str) -> str:
    try:
        parser = MermaidParser()
        parser.parse(mermaid_text)
        return None
    except Exception as e:
        return f"Diagram Validation Error: {str(e)}"

def format_ivr_code(ivr_nodes: list, format_type: str = "javascript") -> str:
    if format_type == "javascript":
        return "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"
    elif format_type == "json":
        return json.dumps(ivr_nodes, indent=2)
    elif format_type == "yaml":
        return yaml.dump(ivr_nodes, allow_unicode=True)
    raise ValueError(f"Unsupported format: {format_type}")

def render_mermaid_safely(mermaid_text: str):
    try:
        st_mermaid(mermaid_text)
    except Exception as e:
        st.error(f"Mermaid rendering failed: {e}")
        st.code(mermaid_text, language="mermaid")

def main():
    st.set_page_config(page_title="Mermaid-to-IVR Converter", page_icon="🔄", layout="wide")
    st.title("🔄 Mermaid-to-IVR Converter")
    st.markdown("Convert flowcharts to Interactive Voice Response (IVR) JavaScript configurations.")
    
    with st.sidebar:
        st.header("🛠 Conversion Options")
        conversion_method = st.radio("Choose Input Method", ["Mermaid Editor", "Image/PDF Upload"])
        export_format = st.radio("Export Format", ["JavaScript", "JSON", "YAML"])
        st.subheader("Advanced Settings")
        validate_syntax = st.checkbox("Validate Diagram", value=True)
        show_debug_info = st.checkbox("Show Detailed Conversion Info", value=False)
    
    mermaid_text = ""
    
    if conversion_method == "Mermaid Editor":
        selected_example = st.selectbox("Load Example Flow", ["Custom"] + list(DEFAULT_FLOWS.keys()))
        mermaid_text = st.text_area(
            "Enter Mermaid Flowchart",
            value=DEFAULT_FLOWS[selected_example] if selected_example != "Custom" else "",
            height=400
        )
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            openai_api_key = st.text_input("OpenAI API Key", type="password", help="Required for image-to-Mermaid conversion")
            uploaded_file = st.file_uploader("Upload Flowchart Image or PDF", type=["pdf", "png", "jpg", "jpeg"])
        
        with col2:
            if uploaded_file:
                try:
                    image = Image.open(uploaded_file)
                    st.image(image, caption="Uploaded Flowchart", use_column_width=True)
                except Exception as e:
                    st.error(f"Error previewing image: {e}")
        
        if uploaded_file and openai_api_key and st.button("🔄 Convert Image to Mermaid"):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name
                
                mermaid_text = process_flow_diagram(tmp_file_path, openai_api_key)
                st.subheader("Converted Mermaid Diagram")
                st.code(mermaid_text, language="mermaid")
                st.success("Image successfully converted to Mermaid diagram!")
                os.unlink(tmp_file_path)
            except Exception as e:
                st.error(f"Conversion Error: {e}")
    
    if mermaid_text:
        st.subheader("👁️ Preview Mermaid Diagram")
        render_mermaid_safely(mermaid_text)
    
if __name__ == "__main__":
    main()
