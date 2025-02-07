import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import yaml
from typing import Optional, Dict, Any
import tempfile
import os
from PIL import Image

from parse_mermaid import parse_mermaid, MermaidParser
from graph_to_ivr import graph_to_ivr, IVRTransformer
from flow_detector import process_flow_diagram

# Page configuration
st.set_page_config(
    page_title="Mermaid-to-IVR Converter",
    page_icon="🔄",
    layout="wide"
)

def process_uploaded_file(uploaded_file) -> Optional[str]:
    """Process uploaded PDF or image file."""
    if uploaded_file is None:
        return None
        
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
        tmp.write(uploaded_file.getvalue())
        temp_path = tmp.name
    
    try:
        # Process the file and get Mermaid diagram
        mermaid_code = process_flow_diagram(temp_path)
        os.unlink(temp_path)
        return mermaid_code
    except Exception as e:
        os.unlink(temp_path)
        raise e

def main():
    st.title("🔄 Mermaid-to-IVR Converter")
    st.markdown("""
    This tool converts flow diagrams into IVR code through Mermaid diagrams.
    You can either upload a diagram image/PDF or write Mermaid code directly.
    """)

    # Input method selection
    input_method = st.radio(
        "Select input method",
        ["Upload Diagram", "Write Mermaid Code"]
    )

    mermaid_text = None

    if input_method == "Upload Diagram":
        st.subheader("📎 Upload Flow Diagram")
        uploaded_file = st.file_uploader(
            "Upload a PDF or image file",
            type=["pdf", "png", "jpg", "jpeg"]
        )

        if uploaded_file:
            with st.spinner("Processing diagram..."):
                try:
                    mermaid_text = process_uploaded_file(uploaded_file)
                    if mermaid_text:
                        st.success("Diagram processed successfully!")
                except Exception as e:
                    st.error(f"Error processing file: {str(e)}")
                    return

    # Rest of the UI (Mermaid editor, preview, etc.)
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Mermaid Editor")
        if input_method == "Write Mermaid Code":
            mermaid_text = st.text_area(
                "Mermaid Diagram",
                height=400,
                value=mermaid_text or "flowchart TD"
            )
        elif mermaid_text:
            mermaid_text = st.text_area(
                "Generated Mermaid Code (you can edit)",
                value=mermaid_text,
                height=400
            )

    with col2:
        if mermaid_text:
            st.subheader("👁️ Preview")
            try:
                st_mermaid.st_mermaid(mermaid_text)
            except Exception as e:
                st.error(f"Preview error: {str(e)}")

    # Convert button
    if mermaid_text and st.button("🔄 Convert to IVR Code"):
        with st.spinner("Converting..."):
            try:
                # Parse and convert
                graph = parse_mermaid(mermaid_text)
                ivr_nodes = graph_to_ivr(graph)
                
                # Show result
                st.subheader("📤 Generated IVR Code")
                output = "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"
                st.code(output, language="javascript")
                
                # Download option
                tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.js')
                with open(tmp_file.name, 'w') as f:
                    f.write(output)
                
                with open(tmp_file.name, 'rb') as f:
                    st.download_button(
                        label="⬇️ Download Code",
                        data=f,
                        file_name="ivr_flow.js",
                        mime="text/javascript"
                    )
                os.unlink(tmp_file.name)

            except Exception as e:
                st.error(f"Conversion error: {str(e)}")
                st.exception(e)

if __name__ == "__main__":
    main()