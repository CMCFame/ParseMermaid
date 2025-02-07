import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import yaml
from typing import Optional, Dict, Any
import tempfile
import os

from openai_converter import process_flow_diagram
from parse_mermaid import parse_mermaid, MermaidParser
from graph_to_ivr import graph_to_ivr

st.set_page_config(
    page_title="Mermaid-to-IVR Converter",
    page_icon="🔄",
    layout="wide"
)

def main():
    st.title("🔄 Mermaid-to-IVR Converter")
    st.markdown("Convert flow diagrams into IVR code through Mermaid diagrams.")

    api_key = st.sidebar.text_input("OpenAI API Key", type="password")
    
    input_method = st.radio(
        "Select input method",
        ["Upload Diagram", "Write Mermaid Code"]
    )

    mermaid_text = None

    if input_method == "Upload Diagram":
        uploaded_file = st.file_uploader(
            "Upload a PDF or image file",
            type=["pdf", "png", "jpg", "jpeg"]
        )

        if uploaded_file and api_key:
            with st.spinner("Processing diagram..."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
                        tmp.write(uploaded_file.getvalue())
                        temp_path = tmp.name

                    mermaid_text = process_flow_diagram(temp_path, api_key)
                    os.unlink(temp_path)
                    st.success("Diagram processed successfully!")
                except Exception as e:
                    st.error(f"Error processing file: {str(e)}")
                    return
        elif uploaded_file:
            st.warning("Please enter your OpenAI API key in the sidebar.")

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

    if mermaid_text and st.button("🔄 Convert to IVR Code"):
        with st.spinner("Converting..."):
            try:
                graph = parse_mermaid(mermaid_text)
                ivr_nodes = graph_to_ivr(graph)
                output = "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"
                
                st.subheader("📤 Generated IVR Code")
                st.code(output, language="javascript")
                
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