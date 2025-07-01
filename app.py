"""
Updated app.py - Integration example showing how to modify your existing Streamlit app
to work with cloud CSV management for Streamlit Cloud deployment
"""

import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import tempfile
import os
import pandas as pd
from PIL import Image
import traceback

# NEW: Import cloud CSV manager
from cloud_csv_manager import get_csv_database_path, show_database_status

# Your existing imports
from parse_mermaid import parse_mermaid, MermaidParser
from openai_converter import process_flow_diagram

# NEW: Import enhanced converter with cloud CSV support
try:
    from integration_replacement import convert_mermaid_to_ivr_with_report, validate_ivr_configuration
    ENHANCED_MODE_AVAILABLE = True
except ImportError:
    # Fallback to your existing converter
    from mermaid_ivr_converter import convert_mermaid_to_ivr
    ENHANCED_MODE_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title="IVR Code Generator - Cloud Ready",
    page_icon="🌐",
    layout="wide"
)

# Your existing DEFAULT_FLOWS
DEFAULT_FLOWS = {
    "Simple Callout": '''flowchart TD
A["Welcome<br/>This is an electric callout from North Dayton.<br/>Press 1, if this is employee.<br/>Press 3, if you need more time to get employee to the phone.<br/>Press 7, if employee is not home.<br/>Press 9, to repeat this message."] -->|"1"| B{"1 - this is employee"}
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

# Your existing utility functions
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

# NEW: Enhanced conversion function with cloud CSV support
def enhanced_conversion_with_cloud_csv(mermaid_text: str, validate_syntax: bool, show_debug: bool):
    """Enhanced conversion that works with cloud CSV management - FIXED VERSION"""
    
    # Get the CSV database path (handles cloud loading automatically)
    csv_path = get_csv_database_path()
    
    if not csv_path:
        st.error("❌ Audio database not available")
        st.info("💡 Please configure your audio database source in the app settings or upload a CSV file")
        return
    
    # Configuration section
    st.subheader("⚙️ Conversion Configuration")
    col1, col2 = st.columns(2)
    
    with col1:
        company_context = st.selectbox(
            "Company Context", 
            ["Auto-detect", "aep", "dpl", "weceg", "integrys", "general"],
            help="Select company for context-specific audio file mapping"
        )
    
    with col2:
        conversion_mode = st.radio(
            "Mode",
            ["🚀 Intelligent Mapping", "📝 Basic Conversion"] if ENHANCED_MODE_AVAILABLE else ["📝 Basic Conversion"],
            help="Intelligent mapping provides production-ready code with automatic audio file ID resolution"
        )
    
    # Conversion button
    if st.button("🔄 Convert to IVR", type="primary"):
        with st.spinner("Converting with intelligent mapping..."):
            try:
                # Validate syntax if requested
                if validate_syntax:
                    error = validate_mermaid(mermaid_text)
                    if error:
                        st.error(error)
                        return
                
                # Choose conversion method
                if conversion_mode.startswith("🚀") and ENHANCED_MODE_AVAILABLE:
                    # Enhanced conversion with intelligent mapping
                    company = None if company_context == "Auto-detect" else company_context
                    
                    # Use the cloud CSV path
                    ivr_flow_dict, notes, conversion_report = convert_mermaid_to_ivr_with_report(
                        mermaid_text, 
                        company=company,
                        csv_file_path=csv_path  # Use dynamically loaded CSV
                    )
                    
                    # Display enhanced results
                    if conversion_report:
                        st.subheader("📊 Intelligent Mapping Results")
                        summary = conversion_report['conversion_summary']
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Success Rate", f"{summary['overall_success_rate']}%")
                        with col2:
                            st.metric("Confidence", f"{summary['average_confidence']:.2f}")
                        with col3:
                            st.metric("Mapped Segments", summary['mapped_segments'])
                        with col4:
                            st.metric("Review Needed", summary['nodes_requiring_review'])
                        
                        # Show missing audio files
                        if conversion_report.get('missing_audio_files'):
                            st.warning("⚠️ Missing Audio Files - New Recordings Needed")
                            missing_df = pd.DataFrame(conversion_report['missing_audio_files'])
                            st.dataframe(missing_df, use_container_width=True)
                            st.info("💡 Send this list to your audio production team")
                        
                        # FIXED: Show low confidence mappings with proper key handling
                        if conversion_report.get('low_confidence_mappings'):
                            st.info("🔍 Low Confidence Mappings - Review Recommended")
                            for mapping in conversion_report['low_confidence_mappings']:
                                # Handle both old and new key structures
                                node_id = mapping.get('node_label', mapping.get('node_id', 'Unknown'))
                                mermaid_id = mapping.get('mermaid_id', '')
                                confidence = mapping.get('confidence', 0)
                                
                                # Create display title
                                if mermaid_id and mermaid_id != node_id:
                                    title = f"Node {node_id} ({mermaid_id}) - Confidence: {confidence:.2f}"
                                else:
                                    title = f"Node {node_id} - Confidence: {confidence:.2f}"
                                
                                with st.expander(title):
                                    segments = mapping.get('segments', [])
                                    if segments:
                                        st.json(segments)
                                    else:
                                        st.write("No segment details available")
                        
                        # Show label mapping if available
                        if conversion_report.get('label_mapping'):
                            with st.expander("🏷️ Label Mapping (Mermaid ID → Descriptive Name)"):
                                for mermaid_id, descriptive_label in conversion_report['label_mapping'].items():
                                    st.write(f"**{mermaid_id}** → {descriptive_label}")
                    
                    # Validate the output
                    validation_result = validate_ivr_configuration(ivr_flow_dict, csv_path)
                    if not validation_result['is_valid']:
                        st.error("❌ Generated IVR code has validation errors:")
                        for error in validation_result['errors']:
                            st.error(f"  • {error}")
                    
                    # Success indicators
                    success_rate = conversion_report['conversion_summary']['overall_success_rate'] if conversion_report else 0
                    if (conversion_report and 
                        success_rate >= 80 and  # Lowered threshold since you're getting 17.6%
                        validation_result['is_valid']):
                        st.success("✅ **Good Quality IVR Code Generated!**")
                        if success_rate >= 95:
                            st.balloons()
                    elif success_rate > 0:
                        st.info(f"ℹ️ **IVR Code Generated** - {success_rate}% success rate (can be improved with more audio data)")
                        
                else:
                    # Basic conversion (your existing method)
                    from mermaid_ivr_converter import convert_mermaid_to_ivr
                    ivr_flow_dict, notes = convert_mermaid_to_ivr(mermaid_text)
                    conversion_report = None
                    
                    # Display basic results
                    if notes:
                        st.warning("📝 Notes found in diagram:")
                        for note in notes:
                            st.info(f"• {note}")
                
                # Format and display the JavaScript output
                js_output = "module.exports = " + json.dumps(ivr_flow_dict, indent=2) + ";"
                st.session_state.last_ivr_code = js_output
                
                # Display generated code
                st.subheader("📤 Generated IVR Configuration")
                st.code(js_output, language="javascript")
                
                # Download functionality
                tmp_file = save_temp_file(js_output)
                with open(tmp_file, 'rb') as f:
                    filename = "ivr_flow_intelligent.js" if conversion_mode.startswith("🚀") else "ivr_flow.js"
                    st.download_button(
                        "⬇️ Download IVR Configuration", 
                        f, 
                        file_name=filename, 
                        mime="application/javascript"
                    )
                os.unlink(tmp_file)
                
                # Show code comparison
                show_code_diff(mermaid_text, js_output)
                
                # Show improvement suggestions
                if conversion_report and conversion_report['conversion_summary']['overall_success_rate'] < 80:
                    st.info("💡 **Tips to Improve Success Rate:**")
                    st.write("• Add more transcribed audio files to your database")
                    st.write("• Verify company context matches your CSV data")
                    st.write("• Check that text in diagram matches your audio transcriptions")
                
            except Exception as e:
                st.error(f"❌ Conversion Error: {str(e)}")
                if show_debug:
                    st.exception(e)

def show_diagnostic_section():
    """Add this to your sidebar or main app for debugging"""
    with st.expander("🔍 System Diagnostic"):
        from integration_replacement import check_system_status
        
        status = check_system_status()
        
        st.write("**System Status:**")
        for key, value in status.items():
            if key != 'recommended_setup':
                icon = "✅" if value else "❌"
                st.write(f"{icon} {key.replace('_', ' ').title()}: {value}")
        
        if status.get('recommended_setup'):
            st.write("**Recommendations:**")
            for rec in status['recommended_setup']:
                st.write(f"💡 {rec}")

def main():
    st.title("🌐 IVR Code Generator - Cloud Ready")
    
    # Enhanced description
    st.markdown("""
    **Transform flow diagrams into production-ready IVR configurations with cloud-native audio file mapping.**
    
    🎯 **Cloud Features:**
    - **☁️ Cloud CSV Management**: Loads audio database from external sources
    - **🚀 Intelligent Mapping**: Automatic text-to-audio-ID resolution  
    - **📊 Quality Metrics**: Real-time confidence and success scoring
    - **🔒 Secure**: No sensitive data stored in GitHub repository
    """)
    
    # Initialize session state
    if 'last_mermaid_code' not in st.session_state:
        st.session_state.last_mermaid_code = ""
    if 'last_ivr_code' not in st.session_state:
        st.session_state.last_ivr_code = ""
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # NEW: Show database status
        st.subheader("💾 Audio Database")
        show_database_status()
        
        conversion_method = st.radio("Input Method", ["Mermaid Editor", "Image Upload"])
        
        st.subheader("Advanced Settings")
        validate_syntax = st.checkbox("Validate Diagram", value=True)
        show_debug = st.checkbox("Show Debug Info", value=False)
        
        st.subheader("API Configuration")
        openai_api_key = st.text_input("OpenAI API Key", type="password", help="Required for image processing")
        
        # Status indicators
        if ENHANCED_MODE_AVAILABLE:
            st.success("✅ Enhanced Mode Ready")
        else:
            st.warning("⚠️ Basic Mode Only")
    
    mermaid_text = ""
    
    # Input method selection (your existing code)
    if conversion_method == "Mermaid Editor":
        selected_example = st.selectbox("Load Example Flow", ["Custom"] + list(DEFAULT_FLOWS.keys()))
        initial_text = DEFAULT_FLOWS.get(selected_example, st.session_state.last_mermaid_code)
        mermaid_text = st.text_area("Mermaid Diagram", initial_text, height=400)
        st.session_state.last_mermaid_code = mermaid_text
    else:
        # Image upload functionality (your existing code)
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
                        st.success("✅ Image converted successfully!")
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
                st.info("Please provide an OpenAI API key in the sidebar for image conversion.")
            if not uploaded_file:
                st.info("Please upload an image or PDF for conversion.")
        
        mermaid_text = st.session_state.last_mermaid_code
    
    # Mermaid preview
    if mermaid_text and mermaid_text.strip():
        st.subheader("👁️ Mermaid Diagram Preview")
        render_mermaid_safely(mermaid_text)
    else:
        st.warning("No Mermaid code to display. Paste code in the editor or convert an image.")
    
    # NEW: Enhanced conversion section with cloud CSV support
    if mermaid_text and mermaid_text.strip():
        enhanced_conversion_with_cloud_csv(mermaid_text, validate_syntax, show_debug)
    else:
        st.info("Mermaid code is not available for conversion.")

if __name__ == "__main__":
    main()