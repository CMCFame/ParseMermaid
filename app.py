import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import yaml
from typing import Optional, Dict, Any
import tempfile
import os
import traceback
from PIL import Image

from parse_mermaid import parse_mermaid, MermaidParser
from graph_to_ivr import graph_to_ivr, IVRTransformer
from openai_converter import process_flow_diagram

# ... (previous imports and configurations remain the same)

def main():
    st.title("🔄 Mermaid-to-IVR Converter")
    st.markdown("""
    Convert flowcharts to Interactive Voice Response (IVR) JavaScript configurations.
    """)

    # Sidebar configuration
    with st.sidebar:
        st.header("🛠 Conversion Options")
        
        # Conversion method selection
        conversion_method = st.radio(
            "Choose Input Method", 
            ["Mermaid Editor", "Image/PDF Upload"]
        )
        
        # Export format selection
        export_format = st.radio(
            "Export Format", 
            ["JavaScript", "JSON", "YAML"]
        )
        
        # Advanced options
        st.subheader("Advanced Settings")
        validate_syntax = st.checkbox("Validate Diagram", value=True)
        show_debug_info = st.checkbox("Show Detailed Conversion Info", value=False)

    # Main content area
    if conversion_method == "Mermaid Editor":
        # Example flow selection for Mermaid Editor
        selected_example = st.selectbox(
            "Load Example Flow", 
            ["Custom"] + list(DEFAULT_FLOWS.keys())
        )
        
        # Mermaid diagram input
        mermaid_text = st.text_area(
            "Enter Mermaid Flowchart", 
            value=DEFAULT_FLOWS[selected_example] if selected_example != "Custom" else "",
            height=400
        )
    else:
        # Image/PDF Upload Section
        col1, col2 = st.columns(2)
        
        with col1:
            # OpenAI API Key input
            openai_api_key = st.text_input(
                "OpenAI API Key", 
                type="password", 
                help="Required for image-to-Mermaid conversion"
            )
            
            # File uploader
            uploaded_file = st.file_uploader(
                "Upload Flowchart Image or PDF", 
                type=['pdf', 'png', 'jpg', 'jpeg']
            )
        
        with col2:
            # Image preview
            if uploaded_file:
                try:
                    # Open the image
                    image = Image.open(uploaded_file)
                    st.image(image, caption="Uploaded Flowchart", use_column_width=True)
                except Exception as e:
                    st.error(f"Error previewing image: {e}")
        
        # Mermaid conversion section
        mermaid_text = ""
        if uploaded_file and openai_api_key:
            # Conversion button
            if st.button("🔄 Convert Image to Mermaid"):
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name
                
                try:
                    # Convert image to Mermaid
                    mermaid_text = process_flow_diagram(tmp_file_path, openai_api_key)
                    
                    # Display converted Mermaid code
                    st.subheader("Converted Mermaid Diagram")
                    st.code(mermaid_text, language="mermaid")
                    
                    st.success("Image successfully converted to Mermaid diagram!")
                except Exception as e:
                    st.error(f"Conversion Error: {e}")
                    mermaid_text = ""
                finally:
                    # Clean up temporary file
                    os.unlink(tmp_file_path)

    # Diagram preview column
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Conversion button
        if st.button("🔄 Convert to IVR Code"):
            try:
                # Optional syntax validation
                if validate_syntax and mermaid_text:
                    validation_error = validate_mermaid(mermaid_text)
                    if validation_error:
                        st.error(validation_error)
                        return

                # Parse and convert
                parsed_graph = parse_mermaid(mermaid_text)
                ivr_nodes = graph_to_ivr(parsed_graph)
                
                # Format output
                output = format_ivr_code(
                    ivr_nodes, 
                    export_format.lower()
                )

                # Display results
                st.subheader("📤 Generated IVR Configuration")
                st.code(output, language="javascript")

                # Debug information
                if show_debug_info:
                    with st.expander("Conversion Details"):
                        st.json(parsed_graph)
                        st.json(ivr_nodes)

                # Temporary file and download
                temp_file = save_temp_file(
                    output, 
                    suffix=f'.{export_format.lower()}'
                )
                
                with open(temp_file, 'rb') as f:
                    st.download_button(
                        label="⬇️ Download Configuration",
                        data=f,
                        file_name=f"ivr_flow.{export_format.lower()}",
                        mime="text/plain"
                    )
                os.unlink(temp_file)

            except Exception as e:
                st.error(f"Conversion Error: {e}")
                if show_debug_info:
                    st.exception(e)

    with col2:
        # Diagram preview
        st.subheader("👁️ Preview")
        try:
            if mermaid_text:
                st_mermaid.st_mermaid(mermaid_text)
        except Exception as e:
            st.error(f"Preview Error: {e}")

if __name__ == "__main__":
    main()