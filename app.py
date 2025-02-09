"""
Enhanced Streamlit application for IVR flow conversion
"""
import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import yaml
from typing import Optional, Dict, Any
import tempfile
import os
import traceback
from PIL import Image
import time

from parse_mermaid import parse_mermaid, MermaidParser
from graph_to_ivr import graph_to_ivr, IVRTransformer
from openai_converter import process_flow_diagram

# Default example flows with comprehensive IVR patterns
DEFAULT_FLOWS = {
    "Simple Callout": '''flowchart TD
    A["Start Call"] --> B{"Are you available?<br/>Press 1 for Yes, 3 for No"}
    B -->|"1 - Yes"| C["Accept Call"]
    B -->|"3 - No"| D["Decline Call"]
    B --> E["Input"]
    E -->|"Invalid Input"| F["Retry Message"]
    F --> E
    C --> G["Record Response"]
    D --> G
    G --> H["End Call"]''',
    
    "PIN Verification": '''flowchart TD
    A["Welcome"] --> B["Enter PIN"]
    B --> C{"Validate PIN"}
    C -->|"Valid"| D["Main Menu"]
    C -->|"Invalid"| E["Error Message"]
    E --> F{"Retry Count < 3"}
    F -->|"Yes"| B
    F -->|"No"| G["Lock Account"]
    D --> H["End Call"]
    G --> H''',
    
    "Transfer Flow": '''flowchart TD
    A["Start"] --> B{"Transfer Available?"}
    B -->|"Yes"| C["Queue Transfer"]
    B -->|"No"| D["Play Message"]
    C --> E["Play Hold Music"]
    E --> F{"Agent Available?"}
    F -->|"Yes"| G["Connect Call"]
    F -->|"No"| E
    D --> H["End Call"]
    G --> H'''
}

class AppState:
    """Manage application state and session data"""
    
    @staticmethod
    def init_session_state():
        """Initialize session state variables"""
        if 'conversion_history' not in st.session_state:
            st.session_state.conversion_history = []
        if 'last_mermaid_code' not in st.session_state:
            st.session_state.last_mermaid_code = None
        if 'last_ivr_code' not in st.session_state:
            st.session_state.last_ivr_code = None

class FileHandler:
    """Handle file operations and conversions"""
    
    @staticmethod
    def save_temp_file(content: str, suffix: str = '.js') -> str:
        """Save content to temporary file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            f.write(content)
            return f.name

    @staticmethod
    def format_ivr_code(ivr_nodes: list, format_type: str = 'javascript') -> str:
        """Format IVR nodes to specified output format"""
        try:
            if format_type == 'javascript':
                return "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"
            elif format_type == 'json':
                return json.dumps(ivr_nodes, indent=2)
            elif format_type == 'yaml':
                return yaml.dump(ivr_nodes, allow_unicode=True)
            else:
                raise ValueError(f"Unsupported format: {format_type}")
        except Exception as e:
            raise ValueError(f"Error formatting IVR code: {str(e)}")

class MermaidHandler:
    """Handle Mermaid diagram operations"""
    
    @staticmethod
    def validate_mermaid(mermaid_text: str) -> Optional[str]:
        """Validate Mermaid diagram syntax"""
        try:
            parser = MermaidParser()
            parser.parse(mermaid_text)
            return None
        except Exception as e:
            return f"Diagram Validation Error: {str(e)}"

    @staticmethod
    def render_mermaid_safely(mermaid_text: str):
        """Safely render Mermaid diagram with error handling"""
        try:
            # Initial cleanup
            mermaid_text = mermaid_text.strip()
            if not mermaid_text.startswith('flowchart'):
                st.error("Invalid Mermaid diagram: Must start with 'flowchart'")
                return

            # Attempt rendering with st_mermaid
            st_mermaid.st_mermaid(mermaid_text, height=400)

        except Exception as e:
            st.error(f"Error rendering diagram: {str(e)}")
            st.code(mermaid_text, language="mermaid")

class UIComponents:
    """Streamlit UI components and layouts"""
    
    @staticmethod
    def show_header():
        """Display application header"""
        st.set_page_config(
            page_title="IVR Flow Designer",
            page_icon="🔄",
            layout="wide"
        )
        st.title("🔄 IVR Flow Designer")
        st.markdown("""
        Convert flowcharts to Interactive Voice Response (IVR) configurations.
        Support for drag-and-drop images, PDF uploads, and direct Mermaid editing.
        """)

    @staticmethod
    def show_sidebar():
        """Display sidebar configuration"""
        with st.sidebar:
            st.header("🛠 Configuration")
            
            # Input method selection
            conversion_method = st.radio(
                "Input Method",
                ["Mermaid Editor", "Image Upload"],
                help="Choose how to input your IVR flow"
            )
            
            # Export format selection
            export_format = st.radio(
                "Export Format",
                ["JavaScript", "JSON", "YAML"],
                help="Choose the output format for your IVR configuration"
            )
            
            # Advanced settings
            st.subheader("Advanced Settings")
            validate_syntax = st.checkbox(
                "Validate Diagram",
                value=True,
                help="Perform syntax validation before conversion"
            )
            show_debug_info = st.checkbox(
                "Show Debug Info",
                value=False,
                help="Display detailed conversion information"
            )
            
            return conversion_method, export_format, validate_syntax, show_debug_info

def main():
    """Main application logic"""
    AppState.init_session_state()
    UIComponents.show_header()
    
    # Sidebar configuration
    conversion_method, export_format, validate_syntax, show_debug_info = UIComponents.show_sidebar()
    
    # Main content area
    if conversion_method == "Mermaid Editor":
        # Example flow selection
        selected_example = st.selectbox(
            "Load Example Flow",
            ["Custom"] + list(DEFAULT_FLOWS.keys()),
            help="Choose a pre-built example or create your own"
        )
        
        # Mermaid editor
        mermaid_text = st.text_area(
            "Mermaid Diagram",
            value=DEFAULT_FLOWS[selected_example] if selected_example != "Custom" else "",
            height=400,
            help="Enter your Mermaid diagram code here"
        )
        
    else:  # Image Upload
        col1, col2 = st.columns(2)
        
        with col1:
            # API key input
            openai_api_key = st.text_input(
                "OpenAI API Key",
                type="password",
                help="Required for image-to-Mermaid conversion"
            )
            
            # File uploader
            uploaded_file = st.file_uploader(
                "Upload Flowchart",
                type=['pdf', 'png', 'jpg', 'jpeg'],
                help="Upload your flowchart image or PDF"
            )
        
        with col2:
            if uploaded_file:
                try:
                    image = Image.open(uploaded_file)
                    st.image(image, caption="Uploaded Flowchart", use_column_width=True)
                except Exception as e:
                    st.error(f"Error loading image: {str(e)}")
        
        # Convert image to Mermaid
        mermaid_text = ""
        if uploaded_file and openai_api_key:
            if st.button("🔄 Convert Image to Mermaid"):
                with st.spinner("Converting image to Mermaid diagram..."):
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_file_path = tmp_file.name
                        
                        mermaid_text = process_flow_diagram(tmp_file_path, openai_api_key)
                        st.session_state.last_mermaid_code = mermaid_text
                        
                        st.success("Image successfully converted!")
                        st.subheader("Generated Mermaid Code")
                        st.code(mermaid_text, language="mermaid")
                        
                    except Exception as e:
                        st.error(f"Conversion Error: {str(e)}")
                        mermaid_text = ""
                    finally:
                        if 'tmp_file_path' in locals():
                            os.unlink(tmp_file_path)
    
    # Preview and conversion section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.button("🔄 Convert to IVR"):
            with st.spinner("Converting to IVR configuration..."):
                try:
                    if validate_syntax:
                        validation_error = MermaidHandler.validate_mermaid(mermaid_text)
                        if validation_error:
                            st.error(validation_error)
                            return
                    
                    # Parse and convert
                    parsed_graph = parse_mermaid(mermaid_text)
                    ivr_nodes = graph_to_ivr(parsed_graph)
                    
                    # Format output
                    output = FileHandler.format_ivr_code(ivr_nodes, export_format.lower())
                    st.session_state.last_ivr_code = output
                    
                    # Display results
                    st.subheader("📤 Generated IVR Configuration")
                    st.code(output, language=export_format.lower())
                    
                    # Debug information
                    if show_debug_info:
                        with st.expander("Debug Information"):
                            st.json(parsed_graph)
                            st.json(ivr_nodes)
                    
                    # Save file for download
                    temp_file = FileHandler.save_temp_file(
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
                    
                    # Add to conversion history
                    st.session_state.conversion_history.append({
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'mermaid': mermaid_text,
                        'ivr': output
                    })
                    
                except Exception as e:
                    st.error(f"Conversion Error: {str(e)}")
                    if show_debug_info:
                        st.exception(e)
    
    with col2:
        st.subheader("👁️ Preview")
        if mermaid_text:
            MermaidHandler.render_mermaid_safely(mermaid_text)
    
    # Conversion history
    if st.session_state.conversion_history and show_debug_info:
        st.subheader("🕒 Conversion History")
        for idx, entry in enumerate(reversed(st.session_state.conversion_history[-5:])):
            with st.expander(f"Conversion {len(st.session_state.conversion_history) - idx}"):
                st.text(f"Timestamp: {entry['timestamp']}")
                st.code(entry['mermaid'], language="mermaid")
                st.code(entry['ivr'], language=export_format.lower())

if __name__ == "__main__":
    main()