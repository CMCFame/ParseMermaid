import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import yaml
from typing import Optional, Dict, Any
import tempfile
import os

from parse_mermaid import parse_mermaid, MermaidParser
from graph_to_ivr import graph_to_ivr, IVRTransformer

# Page configuration
st.set_page_config(
    page_title="Mermaid-to-IVR Converter",
    page_icon="🔄",
    layout="wide"
)

# Constants and examples
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

# Helper functions
def save_temp_file(content: str, suffix: str = '.js') -> str:
    """Saves content to a temporary file and returns the path."""
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
        f.write(content)
        return f.name

def load_example_flows() -> Dict[str, str]:
    """Loads predefined example flows."""
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
    """Validates the Mermaid diagram and returns error message if any."""
    try:
        parser = MermaidParser()
        parser.parse(mermaid_text)
        return None
    except Exception as e:
        return f"Error validating diagram: {str(e)}"

def format_ivr_code(ivr_nodes: list) -> str:
    """Formats IVR code with consistent styling."""
    return "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"

def show_code_diff(original: str, converted: str):
    """Shows a comparison of original and converted code."""
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Original Mermaid")
        st.code(original, language="javascript")
    with col2:
        st.subheader("Generated IVR Code")
        st.code(converted, language="javascript")

def main():
    # Title and description
    st.title("🔄 Mermaid-to-IVR Converter")
    st.markdown("""
    This tool converts Mermaid diagrams into JavaScript code for IVR systems.
    Supports multiple node types, subgraphs, and styles.
    """)

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

    # Main area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Mermaid editor
        st.subheader("📝 Mermaid Editor")
        if selected_example != "Custom":
            mermaid_text = st.text_area(
                "Mermaid Diagram",
                example_flows[selected_example],
                height=400
            )
        else:
            mermaid_text = st.text_area(
                "Mermaid Diagram",
                DEFAULT_MERMAID,
                height=400
            )

    with col2:
        # Diagram preview
        st.subheader("👁️ Preview")
        if mermaid_text:
            try:
                st_mermaid.st_mermaid(mermaid_text)
            except Exception as e:
                st.error(f"Preview error: {str(e)}")

    # Convert button
    if st.button("🔄 Convert to IVR Code"):
        with st.spinner("Converting..."):
            # Optional validation
            if validate_diagram:
                error = validate_mermaid(mermaid_text)
                if error:
                    st.error(error)
                    return

            try:
                # Parse and convert
                graph = parse_mermaid(mermaid_text)
                ivr_nodes = graph_to_ivr(graph)
                
                # Format according to selected format
                if export_format == "JavaScript":
                    output = format_ivr_code(ivr_nodes)
                elif export_format == "JSON":
                    output = json.dumps(ivr_nodes, indent=2)
                else:  # YAML
                    output = yaml.dump(ivr_nodes, allow_unicode=True)

                # Show result
                st.subheader("📤 Generated Code")
                st.code(output, language="javascript")
                
                # Download options
                tmp_file = save_temp_file(output)
                with open(tmp_file, 'rb') as f:
                    st.download_button(
                        label="⬇️ Download Code",
                        data=f,
                        file_name=f"ivr_flow.{export_format.lower()}",
                        mime="text/plain"
                    )
                os.unlink(tmp_file)

                # Show differences
                show_code_diff(mermaid_text, output)

            except Exception as e:
                st.error(f"Conversion error: {str(e)}")
                st.exception(e)

if __name__ == "__main__":
    main()