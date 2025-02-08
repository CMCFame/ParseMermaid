import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import yaml
from typing import Optional, Dict, Any
import tempfile
import os
import requests
from parse_mermaid import parse_mermaid, MermaidParser
from graph_to_ivr import graph_to_ivr, IVRTransformer
from openai_converter import process_flow_diagram

# Constants
DEFAULT_MERMAID = '''flowchart TD
    start["Start of call"]
    available["Are you available?\nIf yes press 1, if no press 3"]
    input{"input"}
    invalid["Invalid entry. Please try again"]
    accept["Accept"]
    decline["Decline"]
    done["End Flow"]

    start --> available
    available --> input
    input -->|"invalid input\nor no input"| invalid
    invalid --> input
    input -->|"1 - accept"| accept
    input -->|"3 - decline"| decline
    accept --> done
    decline --> done'''

# Page configuration
st.set_page_config(
    page_title="Mermaid-to-IVR Converter",
    page_icon="🔄",
    layout="wide"
)

# Initialize session state
if 'openai_key' not in st.session_state:
    st.session_state.openai_key = None
if 'conversion_history' not in st.session_state:
    st.session_state.conversion_history = []

def load_example_flows() -> Dict[str, str]:
    """Load predefined example flows"""
    return {
        "Simple Callout": DEFAULT_MERMAID,
        "PIN Change": '''flowchart TD
    start["Enter PIN"]
    validate{"Valid PIN?"}
    new_pin["Enter new PIN"]
    confirm["Confirm new PIN"]
    match{"PINs match?"}
    success["PIN changed successfully"]
    error["Invalid entry"]
    
    start --> validate
    validate -->|No| error
    validate -->|Yes| new_pin
    new_pin --> confirm
    confirm --> match
    match -->|No| error
    match -->|Yes| success''',
        "Transfer Flow": '''flowchart TD
    start["Transfer Request"]
    attempt{"Transfer\nAttempt"}
    success["Transfer Complete"]
    fail["Transfer Failed"]
    end["End Call"]
    
    start --> attempt
    attempt -->|Success| success
    attempt -->|Fail| fail
    success & fail --> end'''
    }

def validate_mermaid(mermaid_text: str) -> Optional[str]:
    """Validate Mermaid diagram syntax"""
    try:
        parser = MermaidParser()
        parser.parse(mermaid_text)
        return None
    except Exception as e:
        return f"Error validating diagram: {str(e)}"

def convert_to_format(data: Any, export_format: str) -> str:
    """Convert data to specified format"""
    if export_format == "JavaScript":
        return "module.exports = " + json.dumps(data, indent=2) + ";"
    elif export_format == "JSON":
        return json.dumps(data, indent=2)
    else:  # YAML
        return yaml.dump(data, allow_unicode=True)

def render_mermaid_editor():
    """Render the Mermaid editor interface"""
    # Sidebar options
    with st.sidebar:
        st.header("⚙️ Editor Options")
        
        # Load example
        example_flows = load_example_flows()
        selected_example = st.selectbox(
            "Load example",
            ["Custom"] + list(example_flows.keys())
        )
        
        # Export options
        st.subheader("Export")
        export_format = st.radio(
            "Export format",
            ["JavaScript", "JSON", "YAML"]
        )
        
        # Advanced options
        st.subheader("Advanced Options")
        add_standard_nodes = st.checkbox("Add standard nodes", value=True)
        validate_diagram = st.checkbox("Validate diagram", value=True)

    # Main editor area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Mermaid Editor")
        mermaid_text = st.text_area(
            "Mermaid Diagram",
            value=example_flows.get(selected_example, DEFAULT_MERMAID),
            height=400
        )

    with col2:
        st.subheader("👁️ Preview")
        if mermaid_text:
            try:
                st_mermaid.st_mermaid(mermaid_text)
            except Exception as e:
                st.error(f"Preview error: {str(e)}")

    # Handle conversion
    if st.button("🔄 Convert to IVR Code"):
        convert_mermaid_to_ivr(mermaid_text, export_format, validate_diagram, add_standard_nodes)

def render_file_converter():
    """Render the file converter interface"""
    st.subheader("📤 File to Mermaid Converter")
    
    # API Key input
    if not st.session_state.openai_key:
        st.session_state.openai_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Required for file conversion"
        )

    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a PDF or image file",
        type=["pdf", "png", "jpg", "jpeg"],
        help="Upload a flowchart diagram to convert to Mermaid"
    )

    if uploaded_file and st.session_state.openai_key:
        # Show file preview
        if uploaded_file.type.startswith('image'):
            st.image(uploaded_file, caption="Preview", use_column_width=True)
        else:
            st.info(f"Selected file: {uploaded_file.name}")
        
        # Convert button
        if st.button("🔄 Convert to Mermaid"):
            with st.spinner("Converting file..."):
                try:
                    # Save uploaded file temporarily
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.type.split('/')[-1]}") as temp_file:
                        temp_file.write(uploaded_file.getvalue())
                        temp_file_path = temp_file.name

                    # Convert file using OpenAI
                    mermaid_code = process_flow_diagram(
                        temp_file_path,
                        st.session_state.openai_key
                    )

                    # Clean up
                    os.unlink(temp_file_path)

                    # Add to conversion history
                    st.session_state.conversion_history.append({
                        'filename': uploaded_file.name,
                        'mermaid_code': mermaid_code
                    })

                    # Show results
                    st.success("Conversion complete!")
                    
                    # Display Mermaid code
                    with st.expander("📝 Generated Mermaid Code", expanded=True):
                        st.code(mermaid_code, language="mermaid")

                    # Preview converted diagram
                    st.subheader("👁️ Preview")
                    st_mermaid.st_mermaid(mermaid_code)

                    # Option to convert to IVR
                    if st.button("🔄 Convert to IVR Code"):
                        convert_mermaid_to_ivr(mermaid_code, "JavaScript", True, True)

                except Exception as e:
                    st.error(f"Conversion failed: {str(e)}")

    elif not st.session_state.openai_key:
        st.warning("Please enter your OpenAI API key to use the file converter.")

    # Show conversion history
    if st.session_state.conversion_history:
        st.subheader("📜 Conversion History")
        for idx, conversion in enumerate(reversed(st.session_state.conversion_history)):
            with st.expander(f"📄 {conversion['filename']}", expanded=False):
                st.code(conversion['mermaid_code'], language="mermaid")

def convert_mermaid_to_ivr(mermaid_text: str, export_format: str, validate: bool, add_standard_nodes: bool):
    """Convert Mermaid diagram to IVR code"""
    try:
        # Validate if required
        if validate:
            error = validate_mermaid(mermaid_text)
            if error:
                st.error(error)
                return

        # Parse and convert
        graph = parse_mermaid(mermaid_text)
        ivr_nodes = graph_to_ivr(graph)
        
        # Format output
        output = convert_to_format(ivr_nodes, export_format)

        # Display results
        st.subheader("📤 Generated Code")
        st.code(output, language="javascript")
        
        # Download option
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'.{export_format.lower()}') as tmp_file:
            tmp_file.write(output)
            
        with open(tmp_file.name, 'rb') as f:
            st.download_button(
                label="⬇️ Download Code",
                data=f,
                file_name=f"ivr_flow.{export_format.lower()}",
                mime="text/plain"
            )
            
        os.unlink(tmp_file.name)

    except Exception as e:
        st.error(f"Conversion error: {str(e)}")
        st.exception(e)

def main():
    """Main application entry point"""
    st.title("🔄 Mermaid-to-IVR Converter")
    st.markdown("""
    Convert between Mermaid diagrams and IVR code. Now with support for converting PDF and image files!
    """)

    # Create tabs for different modes
    tab1, tab2 = st.tabs(["📝 Mermaid Editor", "📤 File Converter"])

    with tab1:
        render_mermaid_editor()

    with tab2:
        render_file_converter()

if __name__ == "__main__":
    main()