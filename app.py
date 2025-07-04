"""
Streamlit app for IVR flow conversion with enhanced OpenAI integration
and enforced workflow steps.
"""
import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import tempfile
import os
from PIL import Image
import traceback

from parse_mermaid import parse_mermaid, MermaidParser
from mermaid_ivr_converter import convert_mermaid_to_ivr
from openai_converter import process_flow_diagram

# Page configuration
st.set_page_config(
    page_title="Mermaid-to-IVR Converter",
    page_icon="🔄",
    layout="wide"
)

# Constants and examples
DEFAULT_FLOWS = {
    "Simple Callout": '''flowchart TD
A["Welcome<br/>This is an electric callout from (Level 2).<br/>Press 1, if this is (employee).<br/>Press 3, if you need more time to get (employee) to the phone.<br/>Press 7, if (employee) is not home.<br/>Press 9, to repeat this message."] -->|"1"| B{"1 - this is employee"}
A -->|"no input - go to pg 3"| C["30-second message<br/>Press any key to continue..."]
A -->|"7 - not home"| D["Employee Not Home"]
A -->|"3 - need more time"| C
A -->|"9 - repeat"| A
B -->|"yes"| E["Enter Employee PIN"]''',

    "PIN Change": '''flowchart TD
A["Enter PIN"] --> B{"Valid PIN?"}
B -->|"No"| C["Invalid Entry"]
B -->|"Yes"| D["PIN Changed"]
C --> A''',

    "Transfer Flow": '''flowchart TD
A["Transfer Request"] --> B{"Transfer Available?"}
B -->|"Yes"| C["Connect"]
B -->|"No"| D["Failed"]
C --> E["End"]
D --> E'''
}

def save_temp_file(content: str, suffix: str = '.js') -> str:
    """Save content to a temporary file and return the path"""
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
        f.write(content)
        return f.name

def validate_mermaid(mermaid_text: str) -> str:
    """Validate Mermaid diagram syntax"""
    try:
        parser = MermaidParser()
        parser.parse(mermaid_text)
        return None
    except Exception as e:
        return f"Diagram Validation Error: {str(e)}"

def show_code_diff(original: str, converted: str):
    """Show comparison of original and converted code"""
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Original Mermaid")
        st.code(original, language="mermaid")
    with col2:
        st.subheader("Generated IVR Code")
        st.code(converted, language="javascript")

def render_mermaid_safely(mermaid_text: str):
    """Safely render Mermaid diagram with error handling"""
    try:
        st_mermaid.st_mermaid(mermaid_text, height=400)
    except Exception as e:
        st.error(f"Preview Error: {str(e)}")
        st.code(mermaid_text, language="mermaid")

def main():
    st.title("🔄 Mermaid-to-IVR Converter")
    st.markdown("""
    This tool converts flow diagrams into IVR configurations.
    It intelligently parses branching logic from connection labels.
    """)

    # Initialize session state
    if 'last_mermaid_code' not in st.session_state:
        st.session_state.last_mermaid_code = ""
    if 'last_ivr_code' not in st.session_state:
        st.session_state.last_ivr_code = ""

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        conversion_method = st.radio("Input Method", ["Mermaid Editor", "Image Upload"])
        st.subheader("Advanced Settings")
        validate_syntax = st.checkbox("Validate Diagram", value=True)
        show_debug = st.checkbox("Show Debug Info", value=False)
        st.subheader("API Configuration")
        openai_api_key = st.text_input("OpenAI API Key", type="password", help="Required for image processing")

    mermaid_text = ""
    
    if conversion_method == "Mermaid Editor":
        selected_example = st.selectbox("Load Example Flow", ["Custom"] + list(DEFAULT_FLOWS.keys()))
        initial_text = DEFAULT_FLOWS.get(selected_example, st.session_state.last_mermaid_code)
        mermaid_text = st.text_area("Mermaid Diagram", initial_text, height=400)
        st.session_state.last_mermaid_code = mermaid_text
    else:
        col1, col2 = st.columns(2)
        with col1:
            uploaded_file = st.file_uploader("Upload Flowchart", type=['pdf', 'png', 'jpg', 'jpeg'])
        with col2:
            if uploaded_file:
                try:
                    image = Image.open(uploaded_file)
                    st.image(image, caption="Uploaded Flowchart", use_column_width=True)
                except Exception as e:
                    st.error(f"Error loading image: {str(e)}")
        
        if uploaded_file and openai_api_key:
            if st.button("🔄 Convert Image to Mermaid"):
                with st.spinner("Converting image..."):
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            mermaid_text = process_flow_diagram(tmp_file.name, openai_api_key)
                            st.session_state.last_mermaid_code = mermaid_text
                        st.success("Image converted successfully!")
                        st.subheader("Generated Mermaid Code")
                        st.code(mermaid_text, language="mermaid")
                    except Exception as e:
                        st.error(f"Conversion Error: {str(e)}")
                        if show_debug: st.exception(e)
                    finally:
                        if 'tmp_file' in locals(): os.unlink(tmp_file.name)
        else:
            if not openai_api_key: st.info("Please provide an OpenAI API key in the sidebar for image conversion.")
            if not uploaded_file: st.info("Please upload an image or PDF for conversion.")
        
        mermaid_text = st.session_state.last_mermaid_code

    if mermaid_text and mermaid_text.strip():
        st.subheader("👁️ Mermaid Diagram Preview")
        render_mermaid_safely(mermaid_text)
    else:
        st.warning("No Mermaid code to display. Paste code in the editor or convert an image.")

    if mermaid_text and mermaid_text.strip():
        if st.button("🔄 Convert to IVR"):
            with st.spinner("Converting to IVR..."):
                try:
                    if validate_syntax:
                        error = validate_mermaid(mermaid_text)
                        if error:
                            st.error(error)
                            return

                    ivr_flow_dict, notes = convert_mermaid_to_ivr(mermaid_text)
                    
                    # Format for display and download
                    js_output = "module.exports = " + json.dumps(ivr_flow_dict, indent=2) + ";"
                    st.session_state.last_ivr_code = js_output

                    st.subheader("📤 Generated IVR Configuration")
                    st.code(js_output, language="javascript")

                    # Display extracted notes
                    if notes:
                        st.warning("Heads up! The following notes were found in the diagram. These rules are not automatically applied to the IVR flow and may require manual adjustments.")
                        for note in notes:
                            st.info(f"-> {note}")

                    # Download button
                    tmp_file = save_temp_file(js_output)
                    with open(tmp_file, 'rb') as f:
                        st.download_button("⬇️ Download IVR Configuration", f, file_name="ivr_flow.js", mime="application/javascript")
                    os.unlink(tmp_file)

                    show_code_diff(mermaid_text, js_output)

                except Exception as e:
                    st.error(f"Conversion Error: {str(e)}")
                    if show_debug:
                        st.exception(e)
                        st.text(traceback.format_exc())
    else:
        st.info("Mermaid code is not available for conversion.")

if __name__ == "__main__":
    main()