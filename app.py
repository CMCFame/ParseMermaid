"""
Enhanced Streamlit app for IVR flow conversion with improved state management
"""
import streamlit as st
import streamlit_mermaid as st_mermaid
import json
from typing import Optional
import tempfile
import os
from PIL import Image
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

# Custom CSS to hide deprecation warning
st.markdown("""
    <style>
        .stAlert { display: none; }
        .main { padding-top: 2rem; }
        .stTextArea>div>div>textarea { font-family: monospace; }
        .output-container { margin-top: 1rem; }
    </style>
""", unsafe_allow_html=True)

def init_session_state():
    """Initialize session state variables"""
    if 'mermaid_code' not in st.session_state:
        st.session_state.mermaid_code = None
    if 'ivr_code' not in st.session_state:
        st.session_state.ivr_code = None
    if 'original_image' not in st.session_state:
        st.session_state.original_image = None
    if 'conversion_step' not in st.session_state:
        st.session_state.conversion_step = 0

def save_temp_file(content: str, suffix: str = '.js') -> str:
    """Save content to temporary file"""
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

def show_diagram_preview():
    """Show Mermaid diagram preview with error handling"""
    if st.session_state.mermaid_code:
        try:
            st.subheader("Diagram Preview")
            st_mermaid.st_mermaid(st.session_state.mermaid_code, height=400)
        except Exception as e:
            st.error(f"Preview Error: {str(e)}")
            st.code(st.session_state.mermaid_code, language="mermaid")

def show_side_by_side_preview():
    """Show image and diagram preview side by side"""
    col1, col2 = st.columns(2)
    
    with col1:
        if st.session_state.original_image:
            st.subheader("Original Image")
            st.image(st.session_state.original_image, use_column_width=True)
    
    with col2:
        if st.session_state.mermaid_code:
            st.subheader("Generated Diagram")
            st_mermaid.st_mermaid(st.session_state.mermaid_code, height=400)

def show_code_outputs():
    """Show Mermaid and IVR code outputs"""
    if st.session_state.mermaid_code:
        with st.expander("Mermaid Code", expanded=True):
            st.code(st.session_state.mermaid_code, language="mermaid")
    
    if st.session_state.ivr_code:
        with st.expander("IVR Code", expanded=True):
            st.code(st.session_state.ivr_code, language="javascript")

def handle_file_upload():
    """Handle file upload and image conversion"""
    uploaded_file = st.file_uploader(
        "Upload Flowchart",
        type=['pdf', 'png', 'jpg', 'jpeg']
    )

    if uploaded_file:
        try:
            image = Image.open(uploaded_file)
            st.session_state.original_image = image
            show_side_by_side_preview()
            
            if st.button("🔄 Convert Image to Mermaid"):
                with st.spinner("Converting image to Mermaid..."):
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            st.session_state.mermaid_code = process_flow_diagram(
                                tmp_file.name,
                                st.session_state.openai_api_key
                            )
                            st.session_state.conversion_step = 1
                            st.experimental_rerun()
                    finally:
                        if 'tmp_file' in locals():
                            os.unlink(tmp_file.name)

def handle_mermaid_editor():
    """Handle Mermaid editor input"""
    st.session_state.mermaid_code = st.text_area(
        "Mermaid Diagram",
        value=st.session_state.mermaid_code if st.session_state.mermaid_code else "",
        height=200
    )
    if st.session_state.mermaid_code:
        show_diagram_preview()

def handle_ivr_conversion():
    """Handle IVR code conversion"""
    if st.session_state.mermaid_code and st.button("🔄 Convert to IVR"):
        with st.spinner("Converting to IVR..."):
            try:
                st.session_state.ivr_code = convert_mermaid_to_ivr(
                    st.session_state.mermaid_code,
                    st.session_state.openai_api_key
                )
                st.session_state.conversion_step = 2
                st.experimental_rerun()
            except Exception as e:
                st.error(f"IVR Conversion Error: {str(e)}")

def main():
    # Initialize session state
    init_session_state()

    st.title("🔄 IVR Flow Designer")
    st.markdown("This tool converts flow diagrams into IVR configurations.")

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        input_method = st.radio(
            "Input Method",
            ["Image Upload", "Mermaid Editor"]
        )

        with st.expander("Advanced Settings"):
            validate_syntax = st.checkbox("Validate Diagram", value=True)
            show_debug = st.checkbox("Show Debug Info", value=False)

        st.subheader("API Configuration")
        st.session_state.openai_api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Required for conversion"
        )

    # Main content area
    if not st.session_state.openai_api_key:
        st.warning("Please enter your OpenAI API key in the sidebar.")
        return

    if input_method == "Image Upload":
        handle_file_upload()
    else:
        handle_mermaid_editor()

    # Show outputs based on conversion step
    if st.session_state.conversion_step >= 1:
        show_code_outputs()
        handle_ivr_conversion()

    # Download option
    if st.session_state.ivr_code:
        tmp_file = save_temp_file(st.session_state.ivr_code)
        with open(tmp_file, 'rb') as f:
            st.download_button(
                label="⬇️ Download IVR Code",
                data=f,
                file_name="ivr_flow.js",
                mime="text/plain"
            )
        os.unlink(tmp_file)

if __name__ == "__main__":
    main()