"""
Enhanced Streamlit app for IVR flow conversion with improved Mermaid-to-IVR
conversion that produces exact format IVR code.
"""
import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import tempfile
import os
import base64
from PIL import Image
import traceback
from datetime import datetime

from parse_mermaid import parse_mermaid
from openai_converter import convert_image_to_mermaid, process_flow_diagram

# Import exact format IVR converter
from mermaid_ivr_converter import convert_mermaid_to_ivr

# Page configuration
st.set_page_config(
    page_title="Mermaid-to-IVR Converter",
    page_icon="🔄",
    layout="wide"
)

# Constants and examples
DEFAULT_FLOWS = {
    "Simple Callout": '''flowchart TD
A["Welcome<br/>This is an IMPORTANT notification. It is (dow, date, time, time zone).<br/>Press 1 if this is (employee/contact).<br/>Press 3 if you need more time to get (employee/contact) to the phone.<br/>Press 7 if (employee/contact) is not home.<br/>Press 9 to repeat this message."] -->|"input"| B{"9 - repeat or invalid input"}
B --> A
B -->|"7 - not home"| C{"Employee or<br/>Contact?"}
B -->|"3 - need more time"| D["90-second message<br/>Press any key to continue..."]
B -->|"no input"| D
B -->|"1 - this is employee"| E["Custom Message<br/>(Play selected custom message.)"]
C -->|"Employee"| F["Employee Not Home<br/>Please have<br/>(employee) call the<br/>(Level 2) Callout<br/>System at<br/>866-502-7267."]
C -->|"Contact"| G["Contact Not Home<br/>Please inform the<br/>contact that a (Level<br/>2) Notification<br/>occurred at (time)<br/>on (dow, date)."]
E -->|"input"| H{"Confirm<br/>To confirm receipt of this<br/>message, press 1.<br/>To replay the message,<br/>press 3."}
H -->|"1 - accept"| I["Accepted Response<br/>You have accepted<br/>receipt of this message."]
H -->|"3 - repeat"| E
H -->|"invalid input"| J["Invalid Entry.<br/>Invalid entry.<br/>Please try again."]
H -->|"no input"| J
J --> H
I --> K["Goodbye<br/>Thank you.<br/>Goodbye."]
K --> L["Disconnect"]
F --> K
G --> K''',

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
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
        f.write(content)
        return f.name

def validate_mermaid(mermaid_text: str) -> str:
    """Validate Mermaid diagram syntax"""
    try:
        # Just check if we can parse it
        result = parse_mermaid(mermaid_text)
        if not result:
            return "Diagram parsing failed. Check syntax."
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
    This tool converts call flow diagrams into IVR configurations with exact format matching.
    Upload an image of a flowchart or create one using Mermaid syntax.
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
                        # Set API key
                        os.environ["OPENAI_API_KEY"] = openai_api_key
                        
                        # Convert image to Mermaid
                        mermaid_text, error = convert_image_to_mermaid(uploaded_file)
                        
                        if error:
                            st.error(f"Conversion Error: {error}")
                        else:
                            st.session_state.last_mermaid_code = mermaid_text
                            st.success("Image converted successfully!")
                            st.subheader("Generated Mermaid Code")
                            st.code(mermaid_text, language="mermaid")
                            
                    except Exception as e:
                        st.error(f"Conversion Error: {str(e)}")
                        if show_debug:
                            st.exception(e)
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

                    # Convert to IVR using the improved exact format converter
                    ivr_code = convert_mermaid_to_ivr(mermaid_text)
                    st.session_state.last_ivr_code = ivr_code
                    
                    st.subheader("📤 Generated IVR Configuration")
                    st.code(ivr_code, language="javascript")

                    if show_debug:
                        with st.expander("Debug Information"):
                            st.text("Mermaid Code Structure:")
                            try:
                                result = parse_mermaid(mermaid_text)
                                st.json(result)
                            except Exception as e:
                                st.error(f"Parse Error: {str(e)}")

                    # Create download button
                    now = datetime.now().strftime("%Y%m%d_%H%M%S")
                    download_filename = f"ivr_flow_{now}.js"
                    
                    # Use base64 encoding for download
                    b64 = base64.b64encode(ivr_code.encode()).decode()
                    href = f'<a href="data:text/javascript;base64,{b64}" download="{download_filename}">Download IVR Code</a>'
                    st.markdown(href, unsafe_allow_html=True)

                    show_code_diff(mermaid_text, ivr_code)

                except Exception as e:
                    st.error(f"Conversion Error: {str(e)}")
                    if show_debug:
                        st.exception(e)
                        st.text("Traceback:")
                        st.text(traceback.format_exc())
    else:
        st.info("Mermaid code is not available. Please ensure you have converted your image or pasted your Mermaid code.")

    # Add footer
    st.markdown("---")
    st.markdown("🔄 **Mermaid-to-IVR Converter** | Converts call flow diagrams to exact format IVR code")

if __name__ == "__main__":
    main()