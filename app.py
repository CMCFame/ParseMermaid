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
from improved_converter import convert_mermaid_to_ivr  # Use enhanced converter
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
A["Welcome<br/>This is an electric callout from (Level 2).<br/>Press 1, if this is (employee).<br/>Press 3, if you need more time to get (employee) to the phone.<br/>Press 7, if (employee) is not home.<br/>Press 9, to repeat this message."] -->|"input"| B{"1 - this is employee"}
A -->|"no input - go to pg 3"| C["30-second message<br/>Press any key to continue..."]
A -->|"7 - not home"| D["Employee Not Home"]
A -->|"3 - need more time"| C
A -->|"retry logic"| A
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
D --> E''',

    "Notification Flow": '''flowchart TD
A["Welcome<br/>This is an IMPORTANT notification. It is (dow, date, time, time zone).<br/>Press 1 if this is (employee/contact).<br/>Press 3 if you need more time to get (employee/contact) to the phone.<br/>Press 7 if (employee/contact) is not home.<br/>Press 9 to repeat this message."] -->|"9 - repeat or invalid input"| A
A -->|"retry logic<br/>(max 2x)"| A
A -->|"no input - go to pg 21"| B["90-second message<br/>Press any key to continue..."]
A -->|"3 - need more time"| B
A -->|"7 - not home"| C{"Employee or<br/>Contact?"}
A -->|"1 - this is employee"| G["Custom Message<br/>(Play selected custom message.)"]
B --> A
C -->|"Employee"| D["Employee Not Home<br/>Please have (employee) call the (Level 2) Callout System at 866-502-7267."]
C -->|"Contact"| E["Contact Not Home<br/>Please inform the contact that a (Level 2) Notification occurred at (time) on (dow, date)."]
D --> F["Goodbye<br/>Thank you.<br/>Goodbye."]
E --> F
F --> L["Disconnect"]
G --> H["Confirm<br/>To confirm receipt of this message, press 1.<br/>To replay the message, press 3."]
H -->|"3 - repeat"| G
H -->|"invalid input<br/>no input"| I["Invalid Entry<br/>Invalid entry.<br/>Please try again."]
H -->|"1 - accept"| J["Accepted Response<br/>You have accepted receipt of this message."]
I -->|"retry"| H
J --> K["Goodbye<br/>Thank you.<br/>Goodbye."]
K --> L
'''
}

def save_temp_file(content: str, suffix: str = '.js') -> str:
    """Save content to a temporary file and return the path"""
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
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
    This tool converts Mermaid flow diagrams into ARCOS IVR configurations in standard format.
    The generated code follows the exact structure used in production IVR callflow systems.
    """)

    # Initialize session state variables if not already set
    if 'last_mermaid_code' not in st.session_state:
        st.session_state.last_mermaid_code = ""
    if 'last_ivr_code' not in st.session_state:
        st.session_state.last_ivr_code = ""

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Input method selection
        conversion_method = st.radio(
            "Input Method",
            ["Mermaid Editor", "Image Upload"]
        )
        
        # Advanced settings
        st.subheader("Advanced Settings")
        validate_syntax = st.checkbox("Validate Diagram", value=True)
        show_debug = st.checkbox("Show Debug Info", value=False)

        # API Configuration (required only for image conversion)
        st.subheader("API Configuration")
        openai_api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Required for image processing and Mermaid conversion"
        )

    mermaid_text = ""
    
    if conversion_method == "Mermaid Editor":
        # Example flow selection
        selected_example = st.selectbox(
            "Load Example Flow",
            ["Custom"] + list(DEFAULT_FLOWS.keys())
        )
        
        # Mermaid editor text area
        if selected_example != "Custom":
            mermaid_text = st.text_area(
                "Mermaid Diagram",
                DEFAULT_FLOWS[selected_example],
                height=400
            )
        else:
            mermaid_text = st.text_area(
                "Mermaid Diagram",
                st.session_state.last_mermaid_code,
                height=400
            )
        # Save the text in session state
        st.session_state.last_mermaid_code = mermaid_text

    else:  # Image Upload method
        col1, col2 = st.columns(2)
        with col1:
            uploaded_file = st.file_uploader(
                "Upload Flowchart",
                type=['pdf', 'png', 'jpg', 'jpeg']
            )
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
                        if show_debug:
                            st.exception(e)
                    finally:
                        if 'tmp_file' in locals():
                            os.unlink(tmp_file.name)
        else:
            if not openai_api_key:
                st.info("Please provide an OpenAI API key in the sidebar to enable image conversion.")
            if not uploaded_file:
                st.info("Please upload an image or PDF for conversion.")
        
        # Load any existing mermaid code from session state
        mermaid_text = st.session_state.last_mermaid_code

    # Preview the Mermaid diagram (if available)
    if mermaid_text and mermaid_text.strip():
        st.subheader("👁️ Mermaid Diagram Preview")
        render_mermaid_safely(mermaid_text)
    else:
        st.warning("No Mermaid code available. Please convert an image or paste your Mermaid code above.")

    # Only enable IVR conversion if valid Mermaid code is present
    if mermaid_text and mermaid_text.strip():
        if st.button("🔄 Convert to IVR"):
            with st.spinner("Converting to IVR..."):
                try:
                    if validate_syntax:
                        error = validate_mermaid(mermaid_text)
                        if error:
                            st.error(error)
                            return

                    # Convert to IVR using the enhanced converter
                    ivr_code = convert_mermaid_to_ivr(mermaid_text)
                    st.session_state.last_ivr_code = ivr_code
                    
                    # Use the raw IVR code output
                    output = ivr_code

                    st.subheader("📤 Generated IVR Configuration")
                    st.code(output, language="javascript")

                    if show_debug:
                        with st.expander("Debug Information"):
                            st.text("Parsed Nodes:")
                            try:
                                json_str = ivr_code[16:-1].strip()
                                st.json(json.loads(json_str))
                            except Exception as e:
                                st.error(f"Parse Error: {str(e)}")

                    # Provide download button
                    tmp_file = save_temp_file(output)
                    with open(tmp_file, 'rb') as f:
                        st.download_button(
                            label="⬇️ Download IVR Configuration",
                            data=f,
                            file_name="ivr_flow.js",
                            mime="text/plain"
                        )
                    os.unlink(tmp_file)

                    # Show comparison between original and converted
                    show_code_diff(mermaid_text, output)

                except Exception as e:
                    st.error(f"Conversion Error: {str(e)}")
                    if show_debug:
                        st.exception(e)
                        st.text("Traceback:")
                        st.text(traceback.format_exc())
    else:
        st.info("Mermaid code is not available. Please ensure you have converted your image or pasted your Mermaid code.")

if __name__ == "__main__":
    main()