"""
Streamlit app for IVR flow conversion
"""
import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import yaml
from typing import Optional, Dict, Any
import tempfile
import os
from PIL import Image
import traceback
import logging
from parse_mermaid import parse_mermaid, MermaidParser
from openai_ivr_converter import convert_mermaid_to_ivr
from openai_converter import process_flow_diagram

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="IVR Flow Designer",
    page_icon="🔄",
    layout="wide"
)

def save_temp_file(content: str, suffix: str = '.js') -> str:
    """Save content to a temporary file and return the path"""
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
        f.write(content)
        return f.name

def validate_mermaid(mermaid_text: str) -> Optional[str]:
    """Validate Mermaid diagram syntax"""
    try:
        parser = MermaidParser()
        parser.parse(mermaid_text)
        return None
    except Exception as e:
        return f"Diagram Validation Error: {str(e)}"

def main():
    st.title("🔄 IVR Flow Designer")
    st.markdown("This tool converts flow diagrams into IVR configurations. Supports multiple input methods and formats.")

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Input method selection
        input_method = st.radio(
            "Input Method",
            ["Image Upload", "Mermaid Editor"]
        )

        # Advanced settings
        with st.expander("Advanced Settings"):
            validate_syntax = st.checkbox("Validate Diagram", value=True)
            show_debug = st.checkbox("Show Debug Info", value=False)

        # API Configuration
        st.subheader("API Configuration")
        openai_api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Required for image processing and IVR conversion"
        )

    # Main area
    if input_method == "Image Upload":
        # Image upload
        uploaded_file = st.file_uploader(
            "Upload Flowchart",
            type=['pdf', 'png', 'jpg', 'jpeg']
        )

        if uploaded_file:
            # Display original image
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Original Image")
                image = Image.open(uploaded_file)
                st.image(image, use_column_width=True)

            # Convert image to Mermaid button
            if st.button("🔄 Convert Image to Mermaid"):
                with st.spinner("Converting image..."):
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            mermaid_text = process_flow_diagram(tmp_file.name, openai_api_key)
                        
                        with col2:
                            st.subheader("Generated Diagram")
                            st_mermaid.st_mermaid(mermaid_text, height=400)

                        st.subheader("Generated Mermaid Code")
                        st.code(mermaid_text, language="mermaid")

                        # Convert to IVR button
                        if st.button("🔄 Convert to IVR"):
                            with st.spinner("Converting to IVR..."):
                                ivr_code = convert_mermaid_to_ivr(mermaid_text, openai_api_key)
                                st.subheader("Generated IVR Code")
                                st.code(ivr_code, language="javascript")
                                
                                # Download button
                                tmp_file = save_temp_file(ivr_code)
                                with open(tmp_file, 'rb') as f:
                                    st.download_button(
                                        label="⬇️ Download IVR Code",
                                        data=f,
                                        file_name="ivr_flow.js",
                                        mime="text/plain"
                                    )
                                os.unlink(tmp_file)
                                
                    except Exception as e:
                        st.error(f"Conversion Error: {str(e)}")
                        if show_debug:
                            st.exception(e)
                    finally:
                        if 'tmp_file' in locals():
                            os.unlink(tmp_file.name)

    else:  # Mermaid Editor
        # Mermaid input
        mermaid_text = st.text_area(
            "Mermaid Diagram",
            height=200
        )

        if mermaid_text:
            # Preview
            st.subheader("Preview")
            st_mermaid.st_mermaid(mermaid_text, height=400)

            # Convert to IVR button
            if st.button("🔄 Convert to IVR"):
                with st.spinner("Converting to IVR..."):
                    try:
                        if validate_syntax:
                            error = validate_mermaid(mermaid_text)
                            if error:
                                st.error(error)
                                return

                        ivr_code = convert_mermaid_to_ivr(mermaid_text, openai_api_key)
                        st.subheader("Generated IVR Code")
                        st.code(ivr_code, language="javascript")

                        # Download button
                        tmp_file = save_temp_file(ivr_code)
                        with open(tmp_file, 'rb') as f:
                            st.download_button(
                                label="⬇️ Download IVR Code",
                                data=f,
                                file_name="ivr_flow.js",
                                mime="text/plain"
                            )
                        os.unlink(tmp_file)

                    except Exception as e:
                        st.error(f"Conversion Error: {str(e)}")
                        if show_debug:
                            st.exception(e)

if __name__ == "__main__":
    main()