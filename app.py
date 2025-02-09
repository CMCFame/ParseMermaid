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

# Define DEFAULT_FLOWS before using it
DEFAULT_FLOWS = {
    "Simple Callout": '''flowchart TD
    A["Start of Call"] --> B{"Are you available?"}
    B -->|"1 - Yes"| C["Accept Callout"]
    B -->|"3 - No"| D["Decline Callout"]
    C --> E["Record Response"]
    D --> E
    E --> F["End Call"]''',
    
    "PIN Change Flow": '''flowchart TD
    A["Enter Current PIN"] --> B{"PIN Correct?"}
    B -->|"Yes"| C["Enter New PIN"]
    B -->|"No"| D["Access Denied"]
    C --> E{"Confirm New PIN"}
    E -->|"Match"| F["PIN Updated Successfully"]
    E -->|"No Match"| G["PIN Change Failed"]
    D --> H["End"]
    F --> H
    G --> H''',
    
    "Transfer Request": '''flowchart TD
    A["Transfer Request"] --> B{"Transfer Possible?"}
    B -->|"Yes"| C["Initiate Transfer"]
    B -->|"No"| D["Transfer Denied"]
    C --> E["Confirm Transfer"]
    D --> F["End Call"]
    E --> F'''
}

def save_temp_file(content: str, suffix: str = '.js') -> str:
    """Save content to a temporary file"""
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

def format_ivr_code(ivr_nodes: list, format_type: str = 'javascript') -> str:
    """Format IVR nodes to specified output format"""
    if format_type == 'javascript':
        return "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"
    elif format_type == 'json':
        return json.dumps(ivr_nodes, indent=2)
    elif format_type == 'yaml':
        return yaml.dump(ivr_nodes, allow_unicode=True)
    else:
        raise ValueError(f"Unsupported format: {format_type}")

def render_mermaid_safely(mermaid_text: str):
    """
    Safely render Mermaid diagram with multiple fallback strategies
    """
    try:
        # Sanitize the Mermaid text
        mermaid_text = mermaid_text.replace('"', '\\"')
        
        # Attempt rendering with custom HTML and JavaScript
        st.markdown(f"""
        <div id="mermaid-container" style="width: 100%; overflow-x: auto;"></div>
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            try {{
                mermaid.initialize({{startOnLoad:false}});
                const container = document.getElementById('mermaid-container');
                
                mermaid.render('mermaidGraph', `{mermaid_text}`, function(svgCode) {{
                    container.innerHTML = svgCode;
                }}, container);
            }} catch (error) {{
                console.error('Mermaid rendering error:', error);
                container.innerHTML = '<pre>' + error.message + '</pre>';
            }}
        }});
        </script>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Mermaid rendering failed: {e}")
        st.code(mermaid_text, language="mermaid")

def main():
    st.set_page_config(
        page_title="Mermaid-to-IVR Converter",
        page_icon="🔄",
        layout="wide"
    )

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
    mermaid_text = ""

    if conversion_method == "Mermaid Editor":
        # Example flow selection for Mermaid Editor
        selected_example = st.selectbox(
            "Load Example Flow", 
            ["Custom"] + list(DEFAULT_FLOWS.keys())
        )
        
        # Mermaid diagram input
        mermaid_text = st.text_area(
            "Enter or Edit Mermaid Flowchart", 
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
                    image = Image.open(uploaded_file)
                    st.image(image, caption="Uploaded Flowchart", use_column_width=True)
                except Exception as e:
                    st.error(f"Error previewing image: {e}")

        if uploaded_file and openai_api_key:
            if st.button("🔄 Convert Image/PDF to Mermaid"):
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name
                
                try:
                    # Convert image to Mermaid
                    mermaid_text = process_flow_diagram(tmp_file_path, openai_api_key)
                    
                    st.subheader("AI-Generated Mermaid Diagram")
                    st.code(mermaid_text, language="mermaid")
                    
                    st.success("Image successfully converted to Mermaid diagram!")
                except Exception as e:
                    st.error(f"Conversion Error: {e}")
                    mermaid_text = ""
                finally:
                    os.unlink(tmp_file_path)

    # ### CHANGE: Added a second text area to let the user override/fix Mermaid if needed
    if mermaid_text:
        st.subheader("Edit Mermaid Code Before Parsing")
        mermaid_text = st.text_area("Override / Fine-tune the Mermaid code", mermaid_text, height=300)

    # Diagram preview column
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Conversion button
        if st.button("➡ Convert to IVR Code"):
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
                # Show JavaScript as default for code block syntax highlighting
                syntax_lang = "javascript" if export_format.lower() == "javascript" else export_format.lower()
                st.code(output, language=syntax_lang)

                # Debug information
                if show_debug_info:
                    with st.expander("Conversion Details"):
                        st.write("**Parsed Graph**")
                        st.json(parsed_graph)
                        st.write("**IVR Nodes**")
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
                render_mermaid_safely(mermaid_text)
        except Exception as e:
            st.error(f"Preview Error: {e}")

if __name__ == "__main__":
    main()
