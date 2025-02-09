"""
Streamlit app for IVR flow conversion with enhanced UI
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
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants and examples
DEFAULT_FLOWS = {
    "Simple Callout": '''flowchart TD
    A["Welcome<br/>This is an electric callout from (Level 2).<br/>Press 1, if this is (employee).<br/>Press 3, if you need more time to get (employee) to the phone.<br/>Press 7, if (employee) is not home.<br/>Press 9, to repeat this message."] -->|"input"| B{"1 - this is employee"}
    A -->|"no input - go to pg 3"| C["30-second message<br/>Press any key to continue..."]
    A -->|"7 - not home"| D["Employee Not Home"]
    A -->|"3 - need more time"| C
    A -->|"retry logic"| A
    B -->|"yes"| E["Enter Employee PIN"]'''
}

# Custom CSS to hide deprecation warning and improve UI
CUSTOM_CSS = """
<style>
    .stAlert { display: none; }
    .stTextArea>div>div>textarea {
        font-family: monospace;
    }
    .main .block-container {
        padding-top: 2rem;
    }
    .uploadedFile {
        max-width: 100%;
    }
    .comparison-view {
        display: flex;
        gap: 1rem;
    }
    .maximize-button {
        position: absolute;
        top: 10px;
        right: 10px;
        z-index: 1000;
    }
    .element-container {
        position: relative;
    }
</style>
"""

def save_temp_file(content: str, suffix: str = '.js') -> str:
    """Save content to a temporary file and return the path"""
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

def render_mermaid_safely(mermaid_text: str, height: int = 300):
    """Safely render Mermaid diagram with error handling and maximize option"""
    try:
        with st.container():
            st_mermaid.st_mermaid(mermaid_text, height=height)
            
            # Add maximize button
            if st.button("🔍 Maximize", key=f"maximize_{hash(mermaid_text)}"):
                with st.expander("Maximized View", expanded=True):
                    st_mermaid.st_mermaid(mermaid_text, height=600)
    except Exception as e:
        st.error(f"Preview Error: {str(e)}")
        st.code(mermaid_text, language="mermaid")

def show_comparison_view(image: Image.Image, mermaid_text: str):
    """Show side-by-side comparison of image and diagram"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Original Image")
        st.image(image, caption="Uploaded Flowchart", use_column_width=True)
    
    with col2:
        st.subheader("Diagram Preview")
        render_mermaid_safely(mermaid_text)

def process_uploaded_image(uploaded_file) -> Image.Image:
    """Process uploaded image with size constraints"""
    image = Image.open(uploaded_file)
    max_width = 800  # Increased max width for better visibility
    ratio = max_width / image.size[0]
    new_size = (max_width, int(image.size[1] * ratio))
    image.thumbnail(new_size, Image.Resampling.LANCZOS)
    return image

def main():
    # Apply custom CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    st.title("🔄 IVR Flow Designer")
    st.markdown("""
    This tool converts flow diagrams into IVR configurations.
    Supports multiple input methods and formats.
    """)

    # Initialize session state
    if 'mermaid_code' not in st.session_state:
        st.session_state.mermaid_code = None
    if 'uploaded_image' not in st.session_state:
        st.session_state.uploaded_image = None
    if 'comparison_view' not in st.session_state:
        st.session_state.comparison_view = False

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Input method selection
        conversion_method = st.radio(
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

    # Main content area
    if conversion_method == "Image Upload":
        uploaded_file = st.file_uploader(
            "Upload Flowchart",
            type=['pdf', 'png', 'jpg', 'jpeg']
        )
        
        if uploaded_file:
            try:
                image = process_uploaded_image(uploaded_file)
                st.session_state.uploaded_image = image
                
                # Show comparison view if we have both image and diagram
                if st.session_state.mermaid_code:
                    show_comparison_view(image, st.session_state.mermaid_code)
                else:
                    st.image(image, caption="Uploaded Flowchart", use_column_width=True)
                
                # Convert image to Mermaid button
                if st.button("🔄 Convert Image to Mermaid"):
                    with st.spinner("Converting image..."):
                        try:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                                tmp_file.write(uploaded_file.getvalue())
                                mermaid_text = process_flow_diagram(tmp_file.name, openai_api_key)
                                st.session_state.mermaid_code = mermaid_text
                            
                            st.success("Image converted successfully!")
                            st.session_state.comparison_view = True
                            
                        except Exception as e:
                            st.error(f"Conversion Error: {str(e)}")
                            if show_debug:
                                st.exception(e)
                        finally:
                            if 'tmp_file' in locals():
                                os.unlink(tmp_file.name)
            except Exception as e:
                st.error(f"Error loading image: {str(e)}")
    
    else:  # Mermaid Editor
        if st.session_state.mermaid_code:
            mermaid_text = st.text_area(
                "Mermaid Diagram",
                st.session_state.mermaid_code,
                height=300
            )
        else:
            mermaid_text = st.text_area(
                "Mermaid Diagram",
                "",
                height=300
            )
        
        st.session_state.mermaid_code = mermaid_text

    # Show diagram preview
    if st.session_state.mermaid_code:
        if not st.session_state.comparison_view:
            st.subheader("👁️ Preview")
            render_mermaid_safely(st.session_state.mermaid_code)

    # Convert to IVR button
    if st.session_state.mermaid_code and st.button("🔄 Convert to IVR"):
        if not openai_api_key:
            st.error("Please provide an OpenAI API key in the sidebar.")
            return

        with st.spinner("Converting to IVR..."):
            try:
                # Validate diagram if requested
                if validate_syntax:
                    error = validate_mermaid(st.session_state.mermaid_code)
                    if error:
                        st.error(error)
                        return

                # Convert to IVR
                ivr_code = convert_mermaid_to_ivr(st.session_state.mermaid_code, openai_api_key)
                
                # Show result
                st.subheader("📤 Generated IVR Configuration")
                st.code(ivr_code, language="javascript")

                # Debug information
                if show_debug:
                    with st.expander("Debug Information"):
                        st.text("Original Response:")
                        st.code(ivr_code)
                        st.text("Parsed Nodes:")
                        try:
                            json_str = ivr_code[16:-1].strip()
                            st.json(json.loads(json_str))
                        except Exception as e:
                            st.error(f"Parse Error: {str(e)}")

                # Download option
                tmp_file = save_temp_file(ivr_code)
                with open(tmp_file, 'rb') as f:
                    st.download_button(
                        label="⬇️ Download Configuration",
                        data=f,
                        file_name="ivr_flow.js",
                        mime="text/plain"
                    )
                os.unlink(tmp_file)

            except Exception as e:
                st.error(f"Conversion Error: {str(e)}")
                if show_debug:
                    st.exception(e)
                    st.text("Traceback:")
                    st.text(traceback.format_exc())

if __name__ == "__main__":
    main()