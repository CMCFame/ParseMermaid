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

# Custom CSS to hide deprecation warning and improve UI
st.markdown("""
    <style>
        .stAlert { display: none; }
        .main { padding-top: 2rem; }
        .stTextArea>div>div>textarea { font-family: monospace; }
        .output-container { margin-top: 1rem; }
        .comparison-view { display: flex; gap: 1rem; }
        .preview-container { min-height: 400px; }
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
    if 'diagram_height' not in st.session_state:
        st.session_state.diagram_height = 400

def save_temp_file(content: str, suffix: str = '.js') -> str:
    """Save content to temporary file"""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            f.write(content)
            return f.name
    except Exception as e:
        logger.error(f"Error saving temporary file: {str(e)}")
        raise

def validate_mermaid(mermaid_text: str) -> Optional[str]:
    """Validate Mermaid diagram syntax"""
    try:
        parser = MermaidParser()
        parser.parse(mermaid_text)
        return None
    except Exception as e:
        return f"Diagram Validation Error: {str(e)}"

def render_mermaid_safely(mermaid_text: str):
    """Show Mermaid diagram preview with error handling"""
    try:
        with st.container():
            st_mermaid.st_mermaid(mermaid_text, height=st.session_state.diagram_height)
            
            # Add maximize option
            if st.button("🔍 Maximize", key="maximize_diagram"):
                st.session_state.diagram_height = 800 if st.session_state.diagram_height == 400 else 400
                st.experimental_rerun()
    except Exception as e:
        st.error(f"Preview Error: {str(e)}")
        st.code(mermaid_text, language="mermaid")

def show_side_by_side(image: Image.Image, mermaid_text: str):
    """Display image and diagram side by side"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Original Image")
        st.image(image, use_column_width=True)
    
    with col2:
        st.subheader("Generated Diagram")
        render_mermaid_safely(mermaid_text)

def process_uploaded_image(uploaded_file) -> Optional[str]:
    """Process uploaded image and convert to Mermaid"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            mermaid_text = process_flow_diagram(tmp_file.name, st.session_state.openai_api_key)
            return mermaid_text
    except Exception as e:
        st.error(f"Image Processing Error: {str(e)}")
        return None
    finally:
        if 'tmp_file' in locals():
            os.unlink(tmp_file.name)

def show_code_section(code: str, language: str, title: str):
    """Show code with copy and expand options"""
    with st.expander(title, expanded=True):
        st.code(code, language=language)
        
        # Add copy button
        if st.button(f"📋 Copy {title}", key=f"copy_{language}"):
            try:
                import pyperclip
                pyperclip.copy(code)
                st.success(f"{title} copied to clipboard!")
            except Exception as e:
                st.error(f"Could not copy to clipboard: {str(e)}")

def handle_ivr_conversion(mermaid_code: str, show_debug: bool = False):
    """Handle IVR conversion with error handling"""
    try:
        ivr_code = convert_mermaid_to_ivr(mermaid_code, st.session_state.openai_api_key)
        show_code_section(ivr_code, "javascript", "Generated IVR Code")
        
        # Save IVR code in session state
        st.session_state.ivr_code = ivr_code
        
        # Add download button
        tmp_file = save_temp_file(ivr_code)
        with open(tmp_file, 'rb') as f:
            st.download_button(
                label="⬇️ Download IVR Code",
                data=f,
                file_name="ivr_flow.js",
                mime="text/plain"
            )
        os.unlink(tmp_file)
        
        return True
    except Exception as e:
        st.error(f"IVR Conversion Error: {str(e)}")
        if show_debug:
            st.exception(e)
        return False

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

    # Display area with two columns
    col1, col2 = st.columns([3, 2])

    with col1:
        if input_method == "Image Upload":
            uploaded_file = st.file_uploader(
                "Upload Flowchart",
                type=['pdf', 'png', 'jpg', 'jpeg']
            )

            if uploaded_file:
                image = Image.open(uploaded_file)
                st.session_state.original_image = image
                
                if st.button("🔄 Convert Image to Mermaid"):
                    with st.spinner("Converting image to Mermaid..."):
                        mermaid_code = process_uploaded_image(uploaded_file)
                        if mermaid_code:
                            st.session_state.mermaid_code = mermaid_code
                            st.session_state.conversion_step = 1
                            st.experimental_rerun()

        else:  # Mermaid Editor
            st.session_state.mermaid_code = st.text_area(
                "Mermaid Diagram",
                value=st.session_state.mermaid_code if st.session_state.mermaid_code else "",
                height=300
            )

    with col2:
        if st.session_state.original_image and st.session_state.mermaid_code:
            show_side_by_side(st.session_state.original_image, st.session_state.mermaid_code)
        elif st.session_state.mermaid_code:
            st.subheader("Diagram Preview")
            render_mermaid_safely(st.session_state.mermaid_code)

    # Show Mermaid code if available
    if st.session_state.mermaid_code:
        show_code_section(st.session_state.mermaid_code, "mermaid", "Generated Mermaid Code")

        # Convert to IVR button
        if st.button("🔄 Convert to IVR"):
            with st.spinner("Converting to IVR..."):
                if validate_syntax:
                    error = validate_mermaid(st.session_state.mermaid_code)
                    if error:
                        st.error(error)
                        return

                handle_ivr_conversion(st.session_state.mermaid_code, show_debug)

    # Show debug information
    if show_debug and st.session_state.conversion_step > 0:
        with st.expander("Debug Information"):
            st.write("Session State:", st.session_state)
            st.write("Current Step:", st.session_state.conversion_step)

if __name__ == "__main__":
    main()