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
def parse_mermaid_for_enhancement(mermaid_code):
    """
    Parse mermaid code to extract nodes, connections, and filter out notes.
    This is a simplified parser for the enhancement function.
    """
    nodes = {}
    connections = []
    
    # Ignore subgraphs, classes, and notes
    lines = [line.strip() for line in mermaid_code.splitlines() if line.strip()]
    for line in lines:
        # Skip subgraph, class definitions, and end
        if (line.startswith('subgraph') or line.startswith('class') or 
            line == 'end' or line.startswith('flowchart') or line.startswith('%%')):
            continue
        
        # Parse node definitions
        if '-->' not in line:
            # Match node patterns like A["Text"] or B{"Text"}
            node_match = re.match(r'^(\w+)\s*[\[\{\(]"?([^"\]\}\)]+)"?[\]\}\)]', line)
            if node_match:
                node_id, content = node_match.groups()
                # Check if this is a decision node
                is_decision = '?' in content or line.strip()[2] == '{'
                nodes[node_id] = {
                    'id': node_id,
                    'content': content.replace('<br/>', '\n').strip(),
                    'is_decision': is_decision,
                    'connections': []
                }
        
        # Parse connections
        elif '-->' in line:
            # Pattern with label: A -->|"label"| B
            conn_match = re.match(r'(\w+)\s*-->\s*(?:\|"?([^|"]+)"?\|\s*)?(\w+)', line)
            if conn_match:
                source, label, target = conn_match.groups()
                label = label.strip() if label else ""
                connections.append({
                    'source': source,
                    'target': target,
                    'label': label
                })
    
    # Add connections to nodes
    for conn in connections:
        if conn['source'] in nodes:
            nodes[conn['source']]['connections'].append(conn)
    
    return nodes, connections

def enhance_ivr_output_with_mermaid(mermaid_code, ivr_code):
    """
    Enhanced version that uses the original mermaid to improve the IVR output.
    This helps filter out notes and better understand the flow.
    """
    try:
        # Parse the mermaid code to understand the real flow
        nodes, connections = parse_mermaid_for_enhancement(mermaid_code)
        
        # Extract the nodes array from IVR code
        nodes_match = re.search(r'module\.exports\s*=\s*(\[.+\]);', ivr_code, re.DOTALL)
        if not nodes_match:
            return ivr_code
            
        nodes_json = nodes_match.group(1)
        ivr_nodes = json.loads(nodes_json)
        
        # Dev date for "Live Answer" node
        dev_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create better IVR nodes based on the mermaid structure
        enhanced_nodes = []
        processed_nodes = set()
        
        # Find the start node (usually node A)
        start_nodes = [node_id for node_id, node in nodes.items() 
                      if not any(conn['target'] == node_id for conn in connections)]
        
        # Function to process a node and its connections
        def process_node(node_id):
            if node_id in processed_nodes or node_id not in nodes:
                return
                
            processed_nodes.add(node_id)
            node = nodes[node_id]
            
            # Create the IVR node
            ivr_node = create_ivr_node(node_id, node)
            enhanced_nodes.append(ivr_node)
            
            # Process connected nodes
            for conn in node['connections']:
                process_node(conn['target'])
        
        # Process starting from start nodes
        for start_node in start_nodes:
            process_node(start_node)
            
        # Process any remaining nodes
        for node_id in nodes:
            process_node(node_id)
            
        # Add standard nodes if needed
        node_labels = [node.get("label", "") for node in enhanced_nodes]
        
        if "Problems" not in node_labels:
            enhanced_nodes.append({
                "label": "Problems",
                "nobarge": "1",
                "playLog": "I'm sorry you are having problems.",
                "playPrompt": ["callflow:1351"],
                "goto": "Goodbye"
            })
            
        if "Goodbye" not in node_labels:
            enhanced_nodes.append({
                "label": "Goodbye", 
                "log": "Thank you. Goodbye.",
                "playPrompt": ["callflow:1029"],
                "nobarge": "1",
                "goto": "hangup"
            })
        
        # Return the enhanced IVR code
        return "module.exports = " + json.dumps(enhanced_nodes, indent=2) + ";"
    except Exception as e:
        # If any error occurs, return the original
        print(f"Error enhancing IVR: {str(e)}")
        return ivr_code

def create_ivr_node(node_id, node):
    """Create an IVR node with appropriate structure and labels"""
    content = node['content']
    
    # Determine the semantic label
    label = determine_node_label(node_id, content)
    
    # Basic node structure
    ivr_node = {
        "label": label,
        "log": content
    }
    
    # Add maxLoop for Live Answer
    if label == "Live Answer":
        ivr_node["log"] = f"Dev Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ivr_node["maxLoop"] = ["Main", 3, "Problems"]
    
    # Convert content to playLog array if multiple lines
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    if len(lines) > 1:
        ivr_node["playLog"] = lines
    
    # Set appropriate playPrompt
    ivr_node["playPrompt"] = get_play_prompt(content, label)
    
    # Handle decision nodes
    if node['is_decision']:
        ivr_node = add_decision_properties(ivr_node, node)
    else:
        # Add goto for simple nodes with one connection
        outgoing = node['connections']
        if len(outgoing) == 1:
            target_id = outgoing[0]['target']
            target_label = determine_node_label(target_id, "")
            ivr_node["goto"] = target_label
    
    # Special properties for certain nodes
    if "not home" in content.lower() or label in ["Not Home", "Goodbye", "Accept", "Decline"]:
        ivr_node["nobarge"] = "1"
    
    return ivr_node

def determine_node_label(node_id, content):
    """Determine a semantic label based on node content"""
    content_lower = content.lower()
    
    # Check for common patterns
    if "welcome" in content_lower or (node_id == 'A' and "this is" in content_lower):
        return "Live Answer"
    elif "invalid" in content_lower:
        return "Invalid Entry"
    elif "not home" in content_lower:
        return "Not Home"
    elif "pin" in content_lower:
        return "Enter PIN"
    elif "accept" in content_lower:
        return "Accept"
    elif "decline" in content_lower:
        return "Decline"
    elif "goodbye" in content_lower or "thank you" in content_lower:
        return "Goodbye"
    elif "press any key" in content_lower or "continue" in content_lower:
        return "Sleep"
    elif "disconnect" in content_lower:
        return "Disconnect"
    elif "custom message" in content_lower:
        return "Custom Message"
    elif "confirm" in content_lower:
        return "Confirm"
    elif "?" in content_lower:
        return "Decision"
    else:
        # Default label based on node ID
        return f"Node-{node_id}"

def get_play_prompt(content, label):
    """Generate appropriate playPrompt array"""
    content_lower = content.lower()
    
    # Map common content to standard callflow IDs
    if label == "Live Answer" or "welcome" in content_lower or "this is" in content_lower:
        return ["callflow:1210"]
    elif "invalid" in content_lower:
        return ["callflow:1009"]
    elif "not home" in content_lower:
        if "employee" in content_lower:
            return ["callflow:1017", "names:{{contact_id}}", "callflow:1174"]
        else:
            return ["callflow:1017"]
    elif "pin" in content_lower:
        return ["callflow:1008"]
    elif "accept" in content_lower:
        return ["callflow:1167"]
    elif "decline" in content_lower:
        return ["callflow:1021"]
    elif "goodbye" in content_lower or "thank you" in content_lower:
        return ["callflow:1029"]
    elif "press any key" in content_lower:
        return ["callflow:1265"]
    elif "custom message" in content_lower:
        return ["custom:{{custom_message}}"]
    elif "confirm" in content_lower:
        return ["callflow:1035"]
    else:
        # Default using node ID
        return [f"callflow:{label}"]

def add_decision_properties(ivr_node, node):
    """Add getDigits and branch properties for decision nodes"""
    # Set up getDigits object
    get_digits = {
        "numDigits": 1,
        "maxTries": 3,
        "maxTime": 7,
        "validChoices": "1|3|7|9",  # Default
        "errorPrompt": "callflow:1009"
    }
    
    # Build branch object based on connections
    branch = {}
    valid_choices = []
    
    for conn in node['connections']:
        label = conn['label'].lower()
        target_id = conn['target']
        target_label = determine_node_label(target_id, "")
        
        # Map connection label to digit
        if '1' in label or 'yes' in label or 'accept' in label:
            branch['1'] = target_label
            valid_choices.append('1')
        elif '3' in label or 'more time' in label or 'repeat' in label:
            branch['3'] = target_label
            valid_choices.append('3')
        elif '7' in label or 'not home' in label:
            branch['7'] = target_label
            valid_choices.append('7')
        elif '9' in label or 'repeat' in label:
            branch['9'] = target_label
            valid_choices.append('9')
        elif 'error' in label or 'invalid' in label:
            branch['error'] = target_label
        elif 'none' in label or 'no input' in label:
            branch['none'] = target_label
        elif re.search(r'\d+', label):
            # Extract any digit
            digit_match = re.search(r'(\d+)', label)
            if digit_match:
                digit = digit_match.group(1)
                branch[digit] = target_label
                valid_choices.append(digit)
    
    # Add standard error handling
    if 'error' not in branch:
        branch['error'] = 'Problems'
    if 'none' not in branch:
        branch['none'] = 'Problems'
    
    # Update validChoices if we have values
    if valid_choices:
        get_digits['validChoices'] = '|'.join(sorted(set(valid_choices)))
    
    # Add to node
    ivr_node['getDigits'] = get_digits
    ivr_node['branch'] = branch
    
    return ivr_node

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
                    enhanced_ivr_code = enhance_ivr_output_with_mermaid(mermaid_text, ivr_code)
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