"""
Enhanced Streamlit app for IVR flow conversion with improved state management and error handling
"""
import streamlit as st
import streamlit_mermaid as st_mermaid
import json
from typing import Optional, Dict
import tempfile
import os
from PIL import Image
import logging
from parse_mermaid import parse_mermaid, MermaidParser
from openai_ivr_converter import (
    convert_mermaid_to_ivr, 
    OpenAIIVRConverter, 
    IVRNodeValidator,
    NodeType
)
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

# Custom CSS
st.markdown("""
    <style>
        .stAlert { display: none; }
        .main { padding-top: 2rem; }
        .stTextArea>div>div>textarea { font-family: monospace; }
        .output-container { margin-top: 1rem; }
        .comparison-view { display: flex; gap: 1rem; }
        .preview-container { min-height: 400px; }
        .success-message { color: #0f5132; background-color: #d1e7dd; padding: 1rem; border-radius: 0.25rem; }
        .error-message { color: #842029; background-color: #f8d7da; padding: 1rem; border-radius: 0.25rem; }
        .warning-message { color: #664d03; background-color: #fff3cd; padding: 1rem; border-radius: 0.25rem; }
    </style>
""", unsafe_allow_html=True)

class SessionState:
    """Enhanced session state management"""
    REQUIRED_KEYS = {
        'mermaid_code': None,
        'ivr_code': None,
        'original_image': None,
        'conversion_step': 0,
        'diagram_height': 400,
        'validation_errors': [],
        'conversion_status': None,
        'last_converted_node': None
    }

    @classmethod
    def initialize(cls):
        """Initialize all required session state variables"""
        for key, default_value in cls.REQUIRED_KEYS.items():
            if key not in st.session_state:
                st.session_state[key] = default_value

    @classmethod
    def reset_conversion_state(cls):
        """Reset conversion-related state"""
        st.session_state.conversion_step = 0
        st.session_state.validation_errors = []
        st.session_state.conversion_status = None
        st.session_state.last_converted_node = None

class IVRFlowValidator:
    """Validates IVR flow structure and content"""
    
    @staticmethod
    def validate_mermaid(mermaid_text: str) -> list:
        """Validate Mermaid diagram syntax and structure"""
        errors = []
        try:
            parser = MermaidParser()
            parsed = parser.parse(mermaid_text)
            
            # Validate basic structure
            if not parsed['nodes']:
                errors.append("Diagram must contain at least one node")
            
            # Validate node connections
            if not parsed['edges']:
                errors.append("Diagram must contain at least one connection")
            
            # Validate start/end nodes
            start_nodes = [n for n in parsed['nodes'].values() 
                         if n.node_type == NodeType.START]
            if not start_nodes:
                errors.append("Diagram must have a start node")
                
        except Exception as e:
            errors.append(f"Diagram validation error: {str(e)}")
            
        return errors

    @staticmethod
    def validate_ivr_code(ivr_code: str) -> list:
        """Validate generated IVR code"""
        errors = []
        try:
            # Extract node array
            if not 'module.exports = [' in ivr_code:
                errors.append("Invalid IVR code format")
                return errors
                
            # Parse nodes
            nodes_str = ivr_code.split('module.exports = [')[1].rsplit('];')[0]
            nodes = json.loads(f"[{nodes_str}]")
            
            # Validate each node
            validator = IVRNodeValidator()
            for node in nodes:
                try:
                    node_type = OpenAIIVRConverter._determine_node_type(node)
                    validator.validate_node(node, node_type)
                except Exception as e:
                    errors.append(f"Node validation error: {str(e)}")
                    
        except json.JSONDecodeError:
            errors.append("Invalid JSON in generated code")
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            
        return errors

def save_temp_file(content: str, suffix: str = '.js') -> str:
    """Save content to temporary file with error handling"""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            f.write(content)
            return f.name
    except Exception as e:
        logger.error(f"Error saving temporary file: {str(e)}")
        raise

def render_mermaid_safely(mermaid_text: str):
    """Show Mermaid diagram preview with enhanced error handling"""
    try:
        with st.container():
            st_mermaid.st_mermaid(mermaid_text, height=st.session_state.diagram_height)
            
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("🔍 Maximize"):
                    st.session_state.diagram_height = (
                        800 if st.session_state.diagram_height == 400 else 400
                    )
                    st.experimental_rerun()
    except Exception as e:
        st.error(f"Preview Error: {str(e)}")
        st.code(mermaid_text, language="mermaid")

def show_side_by_side(image: Image.Image, mermaid_text: str):
    """Display image and diagram side by side with enhanced layout"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Original Image")
        st.image(image, use_column_width=True)
    
    with col2:
        st.subheader("Generated Diagram")
        render_mermaid_safely(mermaid_text)

def process_uploaded_image(uploaded_file) -> Optional[str]:
    """Process uploaded image with enhanced error handling"""
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_file = tmp_file.name
            return process_flow_diagram(temp_file, st.session_state.openai_api_key)
    except Exception as e:
        st.error(f"Image Processing Error: {str(e)}")
        return None
    finally:
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)

def show_code_section(code: str, language: str, title: str):
    """Show code with enhanced display options"""
    with st.expander(title, expanded=True):
        st.code(code, language=language)
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button(f"📋 Copy {title}", key=f"copy_{language}"):
                try:
                    import pyperclip
                    pyperclip.copy(code)
                    st.success(f"{title} copied!")
                except Exception as e:
                    st.error(f"Copy failed: {str(e)}")
        
        with col2:
            if language == 'javascript':
                if st.button("⬇️ Download", key=f"download_{language}"):
                    try:
                        tmp_file = save_temp_file(code)
                        with open(tmp_file, 'rb') as f:
                            st.download_button(
                                label="Save IVR Code",
                                data=f,
                                file_name="ivr_flow.js",
                                mime="text/javascript"
                            )
                        os.unlink(tmp_file)
                    except Exception as e:
                        st.error(f"Download failed: {str(e)}")

def handle_ivr_conversion(mermaid_code: str, show_debug: bool = False) -> bool:
    """Handle IVR conversion with enhanced error handling and validation"""
    try:
        # Validate Mermaid code first
        errors = IVRFlowValidator.validate_mermaid(mermaid_code)
        if errors:
            for error in errors:
                st.error(f"Validation Error: {error}")
            return False
        
        # Convert to IVR
        ivr_code = convert_mermaid_to_ivr(mermaid_code, st.session_state.openai_api_key)
        
        # Validate generated IVR code
        errors = IVRFlowValidator.validate_ivr_code(ivr_code)
        if errors:
            for error in errors:
                st.warning(f"IVR Code Warning: {error}")
        
        # Display the code
        show_code_section(ivr_code, "javascript", "Generated IVR Code")
        
        # Store in session state
        st.session_state.ivr_code = ivr_code
        st.session_state.conversion_status = "success"
        
        return True
        
    except Exception as e:
        st.error(f"IVR Conversion Error: {str(e)}")
        if show_debug:
            st.exception(e)
        st.session_state.conversion_status = "error"
        return False

def show_conversion_status():
    """Display conversion status with appropriate styling"""
    if st.session_state.conversion_status == "success":
        st.markdown(
            '<div class="success-message">✅ Conversion completed successfully!</div>',
            unsafe_allow_html=True
        )
    elif st.session_state.conversion_status == "error":
        st.markdown(
            '<div class="error-message">❌ Conversion failed. Please check the errors above.</div>',
            unsafe_allow_html=True
        )

def main():
    # Initialize session state
    SessionState.initialize()

    st.title("🔄 IVR Flow Designer")
    st.markdown("""
        Convert flow diagrams into IVR configurations with enhanced validation and error handling.
        Upload an image or create your Mermaid diagram directly.
    """)

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        input_method = st.radio(
            "Input Method",
            ["Image Upload", "Mermaid Editor"],
            help="Choose how you want to input your IVR flow"
        )

        with st.expander("Advanced Settings"):
            validate_syntax = st.checkbox(
                "Validate Diagram",
                value=True,
                help="Enable detailed syntax validation"
            )
            show_debug = st.checkbox(
                "Show Debug Info",
                value=False,
                help="Display additional debugging information"
            )

        st.subheader("API Configuration")
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Required for conversion. Keep this secure!"
        )
        st.session_state.openai_api_key = api_key

    # Main content area
    if not st.session_state.openai_api_key:
        st.warning("⚠️ Please enter your OpenAI API key in the sidebar to continue.")
        return

    # Display area with two columns
    col1, col2 = st.columns([3, 2])

    with col1:
        if input_method == "Image Upload":
            uploaded_file = st.file_uploader(
                "Upload Flowchart",
                type=['pdf', 'png', 'jpg', 'jpeg'],
                help="Support for PDF and common image formats"
            )

            if uploaded_file:
                image = Image.open(uploaded_file)
                st.session_state.original_image = image
                
                if st.button("🔄 Convert Image to Mermaid", help="Start image conversion process"):
                    with st.spinner("Converting image to Mermaid diagram..."):
                        mermaid_code = process_uploaded_image(uploaded_file)
                        if mermaid_code:
                            st.session_state.mermaid_code = mermaid_code
                            st.session_state.conversion_step = 1
                            st.experimental_rerun()

        else:  # Mermaid Editor
            st.session_state.mermaid_code = st.text_area(
                "Mermaid Diagram",
                value=st.session_state.mermaid_code if st.session_state.mermaid_code else "",
                height=300,
                help="Enter your Mermaid diagram code here"
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
        if st.button("🔄 Convert to IVR", help="Generate IVR configuration"):
            with st.spinner("Converting to IVR configuration..."):
                if validate_syntax:
                    errors = IVRFlowValidator.validate_mermaid(st.session_state.mermaid_code)
                    if errors:
                        for error in errors:
                            st.error(error)
                    else:
                        handle_ivr_conversion(st.session_state.mermaid_code, show_debug)
                else:
                    handle_ivr_conversion(st.session_state.mermaid_code, show_debug)

        # Show conversion status
        if st.session_state.conversion_status:
            show_conversion_status()
                # Show debug information
    if show_debug and st.session_state.conversion_step > 0:
        with st.expander("Debug Information"):
            st.write("Session State:", {
                k: v for k, v in st.session_state.items() 
                if k not in ['openai_api_key', 'mermaid_code', 'ivr_code']
            })
            st.write("Current Step:", st.session_state.conversion_step)
            st.write("Validation Errors:", st.session_state.validation_errors)
            if st.session_state.last_converted_node:
                st.write("Last Converted Node:", st.session_state.last_converted_node)

if __name__ == "__main__":
    main()