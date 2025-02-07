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

    # Debug Mode Toggle
    debug_mode = st.sidebar.checkbox("Debug Mode")

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
                    if debug_mode:
                        st.write("OpenAI Generated Mermaid Text:", mermaid_text)
                    st.success("Diagram processed successfully!")
                except Exception as e:
                    st.error(f"Error processing file: {str(e)}")
                    if debug_mode:
                        st.exception(e)
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
                if debug_mode:
                    st.exception(e)

    if mermaid_text and st.button("🔄 Convert to IVR Code"):
        with st.spinner("Converting..."):
            try:
                # Step 1: Parse Mermaid to Graph
                if debug_mode:
                    st.write("Step 1: Parsing Mermaid text...")
                graph = parse_mermaid(mermaid_text)
                if debug_mode:
                    st.write("Parsed graph structure:", graph)
                    st.write("Number of nodes:", len(graph['nodes']))
                    st.write("Number of edges:", len(graph['edges']))

                # Step 2: Convert Graph to IVR
                if debug_mode:
                    st.write("Step 2: Converting to IVR...")
                ivr_nodes = graph_to_ivr(graph)
                if debug_mode:
                    st.write("Generated IVR nodes:", ivr_nodes)
                    st.write("Number of IVR nodes:", len(ivr_nodes))

                # Step 3: Generate final output
                output = "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"
                
                st.subheader("📤 Generated IVR Code")
                st.code(output, language="javascript")
                
                # Create download button
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
                if debug_mode:
                    st.exception(e)
                    st.write("Current mermaid_text:", mermaid_text)

if __name__ == "__main__":
    main()