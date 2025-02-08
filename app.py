import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import yaml
import tempfile
import os
from parse_mermaid import parse_mermaid, MermaidParser
from graph_to_ivr import graph_to_ivr
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
if 'mermaid_code' not in st.session_state:
    st.session_state.mermaid_code = DEFAULT_MERMAID

def load_example_flows():
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

def validate_mermaid(mermaid_text: str):
    """Validate Mermaid diagram syntax"""
    try:
        parser = MermaidParser()
        parser.parse(mermaid_text)
        return None
    except Exception as e:
        return f"Error validating diagram: {str(e)}"

def main():
    st.title("🔄 Mermaid-to-IVR Converter")
    
    # Sidebar with options
    with st.sidebar:
        st.header("⚙️ Options")
        
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

    # Main content area
    col1, col2 = st.columns([3, 2])
    
    with col1:
        # OpenAI API Key
        st.session_state.openai_key = st.text_input(
            "OpenAI API Key",
            value=st.session_state.openai_key if st.session_state.openai_key else "",
            type="password",
            help="Required for file conversion"
        )

        # File uploader
        uploaded_file = st.file_uploader(
            "Upload a flowchart (PDF, PNG, JPG)",
            type=["pdf", "png", "jpg", "jpeg"],
            help="Upload a flowchart diagram to convert to Mermaid"
        )

        if uploaded_file and st.session_state.openai_key:
            # Show file preview if it's an image
            if uploaded_file.type.startswith('image'):
                st.image(uploaded_file, caption="Preview", use_column_width=True)
            else:
                st.info(f"Selected PDF: {uploaded_file.name}")
            
            # Convert button for file
            if st.button("Convert File to Mermaid", key="convert_file"):
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

                        # Update session state
                        st.session_state.mermaid_code = mermaid_code
                        st.success("File converted successfully!")

                    except Exception as e:
                        st.error(f"Conversion failed: {str(e)}")

        # Mermaid editor
        st.subheader("📝 Mermaid Editor")
        mermaid_text = st.text_area(
            "Mermaid Diagram",
            value=st.session_state.mermaid_code if not selected_example or selected_example == "Custom" 
                  else example_flows[selected_example],
            height=400
        )

        # Convert button for Mermaid
        if st.button("Convert to IVR Code", key="convert_mermaid"):
            try:
                # Validate if required
                if validate_diagram:
                    error = validate_mermaid(mermaid_text)
                    if error:
                        st.error(error)
                        return

                # Parse and convert
                graph = parse_mermaid(mermaid_text)
                ivr_nodes = graph_to_ivr(graph)
                
                # Format output
                if export_format == "JavaScript":
                    output = "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"
                elif export_format == "JSON":
                    output = json.dumps(ivr_nodes, indent=2)
                else:  # YAML
                    output = yaml.dump(ivr_nodes, allow_unicode=True)

                # Show result
                st.subheader("📤 Generated Code")
                st.code(output, language="javascript")
                
                # Download options
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'.{export_format.lower()}') as tmp_file:
                    tmp_file.write(output)
                    
                with open(tmp_file.name, 'rb') as f:
                    st.download_button(
                        label="⬇️ Download Code",
                        data=f,
                        file_name=f"ivr_flow.{export_format.lower()}",
                        mime="text/plain",
                        key="download_code"
                    )
                os.unlink(tmp_file.name)

            except Exception as e:
                st.error(f"Conversion error: {str(e)}")
                st.exception(e)

    with col2:
        st.subheader("👁️ Preview")
        if mermaid_text:
            try:
                st_mermaid.st_mermaid(mermaid_text)
            except Exception as e:
                st.error(f"Preview error: {str(e)}")

if __name__ == "__main__":
    main()