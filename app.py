"""
Streamlit app for IVR flow conversion with enhanced OpenAI integration
and enforced workflow steps.
"""
import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import tempfile
import os
import re
import datetime
from PIL import Image
import traceback

from parse_mermaid import parse_mermaid, MermaidParser
from mermaid_ivr_converter import convert_mermaid_to_ivr  # Use original converter
from openai_converter import process_flow_diagram

# Page configuration
st.set_page_config(
    page_title="Mermaid-to-IVR Converter",
    page_icon="🔄",
    layout="wide"
)

# Enhanced conversion logic (embedded directly instead of importing)
def enhance_ivr_output(ivr_code):
    """
    Enhance the output of the original converter to match real IVR format.
    This improves the labels, structure, and callflow IDs to match production code.
    """
    try:
        # Extract the nodes array
        nodes_match = re.search(r'module\.exports\s*=\s*(\[.+\]);', ivr_code, re.DOTALL)
        if not nodes_match:
            return ivr_code
            
        nodes_json = nodes_match.group(1)
        nodes = json.loads(nodes_json)
        
        # Dev date for "Live Answer" node
        dev_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Standard callflow IDs mapping
        callflow_ids = {
            "welcome": "1210",
            "notification": "1210",
            "press_1": "1002",
            "press_3": "1005",
            "not_home": "1004",
            "need_more_time": "1006",
            "repeat_message": "1643", 
            "pin_entry": "1008",
            "invalid_input": "1009",
            "timeout": "1010",
            "accept": "1167",
            "decline": "1021",
            "qualified_no": "1266",
            "callout": "1274",
            "wait_message": "1265",
            "goodbye": "1029",
            "error": "1351"
        }
        
        # Improve node labels and structure
        enhanced_nodes = []
        
        # Try to identify main nodes
        welcome_node = None
        for node in nodes:
            if "Welcome" in node.get("log", "") or "This is" in node.get("log", ""):
                welcome_node = node
                break
        
        for node in nodes:
            enhanced_node = node.copy()
            
            # Improve label based on content
            log_content = node.get("log", "").lower()
            
            # Better labeling
            if "welcome" in log_content or "this is" in log_content:
                enhanced_node["label"] = "Live Answer"
                enhanced_node["log"] = f"Dev Date: {dev_date}"
                enhanced_node["maxLoop"] = ["Main", 3, "Problems"]
            elif "invalid" in log_content:
                enhanced_node["label"] = "Invalid Entry"
            elif "not home" in log_content:
                enhanced_node["label"] = "Not Home"
                enhanced_node["nobarge"] = "1"
            elif "pin" in log_content:
                enhanced_node["label"] = "Enter PIN"
            elif "accept" in log_content:
                enhanced_node["label"] = "Accept"
                enhanced_node["nobarge"] = "1"
            elif "decline" in log_content:
                enhanced_node["label"] = "Decline"
                enhanced_node["nobarge"] = "1"
            elif "goodbye" in log_content or "thank you" in log_content:
                enhanced_node["label"] = "Goodbye"
                enhanced_node["nobarge"] = "1"
            elif "press any key" in log_content:
                enhanced_node["label"] = "Sleep"
            
            # Convert playPrompt to array if it's not already
            if "playPrompt" in enhanced_node and not isinstance(enhanced_node["playPrompt"], list):
                # Try to map to standard callflow IDs
                prompt = enhanced_node["playPrompt"]
                if prompt.startswith("callflow:"):
                    node_id = prompt[9:]
                    
                    # Map to standard IDs when possible
                    if "welcome" in log_content or "this is" in log_content:
                        enhanced_node["playPrompt"] = ["callflow:1210"]
                    elif "invalid" in log_content:
                        enhanced_node["playPrompt"] = ["callflow:1009"]
                    elif "not home" in log_content:
                        enhanced_node["playPrompt"] = ["callflow:1004"]
                    elif "pin" in log_content:
                        enhanced_node["playPrompt"] = ["callflow:1008"]
                    elif "accept" in log_content:
                        enhanced_node["playPrompt"] = ["callflow:1167"]
                    elif "goodbye" in log_content:
                        enhanced_node["playPrompt"] = ["callflow:1029"]
                    else:
                        # Keep original but make it an array
                        enhanced_node["playPrompt"] = [prompt]
            
            # Convert playLog to array if it contains multiple lines
            if "log" in enhanced_node and not isinstance(enhanced_node["log"], list):
                log_content = enhanced_node["log"]
                if "\n" in log_content:
                    lines = [line.strip() for line in log_content.split("\n") if line.strip()]
                    enhanced_node["playLog"] = lines
            
            # Improve getDigits structure
            if "getDigits" in enhanced_node:
                get_digits = enhanced_node["getDigits"]
                # Add standard fields if missing
                if "maxTries" not in get_digits:
                    get_digits["maxTries"] = 3
                if "maxTime" not in get_digits:
                    get_digits["maxTime"] = 7
                if "errorPrompt" not in get_digits:
                    get_digits["errorPrompt"] = "callflow:1009"
            
            # Add standard error handling to branch
            if "branch" in enhanced_node:
                branch = enhanced_node["branch"]
                if "error" not in branch:
                    branch["error"] = "Problems"
                if "none" not in branch:
                    branch["none"] = "Problems"
            
            enhanced_nodes.append(enhanced_node)
        
        # Add standard nodes if missing
        node_labels = [node.get("label") for node in enhanced_nodes]
        
        if "Problems" not in node_labels:
            enhanced_nodes.append({
                "label": "Problems",
                "nobarge": "1",
                "playLog": "I'm sorry you are having problems.",
                "playPrompt": "callflow:1351",
                "goto": "Goodbye"
            })
            
        if "Goodbye" not in node_labels:
            enhanced_nodes.append({
                "label": "Goodbye", 
                "log": "Thank you. Goodbye.",
                "playPrompt": "callflow:1029",
                "nobarge": "1",
                "goto": "hangup"
            })
        
        # Return the enhanced IVR code
        return "module.exports = " + json.dumps(enhanced_nodes, indent=2) + ";"
    except Exception as e:
        # If any error occurs, return the original
        print(f"Error enhancing IVR: {str(e)}")
        return ivr_code

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

                    # Convert to IVR using the original converter
                    ivr_code = convert_mermaid_to_ivr(mermaid_text)
                    
                    # Enhance the output to match real IVR code format
                    enhanced_ivr_code = enhance_ivr_output(ivr_code)
                    st.session_state.last_ivr_code = enhanced_ivr_code
                    
                    # Use the enhanced IVR code
                    output = enhanced_ivr_code

                    st.subheader("📤 Generated IVR Configuration")
                    st.code(output, language="javascript")

                    if show_debug:
                        with st.expander("Debug Information"):
                            st.text("Parsed Nodes:")
                            try:
                                json_str = output[16:-1].strip()
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