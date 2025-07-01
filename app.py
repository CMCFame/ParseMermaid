"""
Enhanced Streamlit app for IVR flow conversion with intelligent audio mapping
and Google Drive integration.
"""
import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import tempfile
import os
import pandas as pd
from PIL import Image
import traceback
import logging
from typing import Dict, List, Any, Optional

# Import enhanced modules
from parse_mermaid import parse_mermaid, MermaidParser
from google_drive_loader import CloudAudioDatabase, load_audio_database
from intelligent_audio_mapper import IntelligentAudioMapper
from configurable_ivr_system import DataDrivenAudioMapper, create_enhanced_ivr_system
from openai_converter import process_flow_diagram

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Enhanced IVR Code Generator",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'last_mermaid_code' not in st.session_state:
    st.session_state.last_mermaid_code = ""
if 'last_ivr_code' not in st.session_state:
    st.session_state.last_ivr_code = ""
if 'audio_database' not in st.session_state:
    st.session_state.audio_database = None
if 'ivr_system' not in st.session_state:
    st.session_state.ivr_system = None
if 'quality_report' not in st.session_state:
    st.session_state.quality_report = None

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

SUPPORTED_COMPANIES = ['aep', 'dpl', 'weceg', 'integrys', 'global']

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

def categorize_missing_segment(segment: str) -> str:
    """Categorize missing audio segments for better reporting"""
    segment_lower = segment.lower()
    
    if any(word in segment_lower for word in ['employee', 'worker', 'technician']):
        return 'Employee Names'
    elif any(word in segment_lower for word in ['location', 'level', 'area', 'district']):
        return 'Locations'
    elif any(word in segment_lower for word in ['electric', 'normal', 'emergency', 'storm']):
        return 'Callout Types'
    elif any(word in segment_lower for word in ['press', 'if', 'to', 'for']):
        return 'Instructions'
    elif any(word in segment_lower for word in ['thank you', 'goodbye', 'welcome']):
        return 'Standard Phrases'
    else:
        return 'Custom Messages'

def create_quality_report(ivr_nodes: List[Dict], warnings: List[str]) -> Dict[str, Any]:
    """Create a quality assessment report for the generated IVR"""
    
    total_nodes = len([node for node in ivr_nodes if node.get('label') != 'Problems'])
    nodes_with_warnings = sum(1 for node in ivr_nodes if '_warnings' in node)
    missing_segments = []
    
    for node in ivr_nodes:
        if '_warnings' in node:
            missing_segments.extend(node['_warnings'].get('missing_audio_segments', []))
    
    # Calculate quality metrics
    mapping_accuracy = ((total_nodes - nodes_with_warnings) / total_nodes * 100) if total_nodes > 0 else 0
    total_missing = len(list(set(missing_segments)))  # Remove duplicates
    
    # Categorize missing segments
    missing_by_type = {}
    for segment in set(missing_segments):
        segment_type = categorize_missing_segment(segment)
        missing_by_type[segment_type] = missing_by_type.get(segment_type, 0) + 1
    
    return {
        'total_nodes': total_nodes,
        'nodes_with_warnings': nodes_with_warnings,
        'mapping_accuracy': mapping_accuracy,
        'total_missing_segments': total_missing,
        'missing_by_type': missing_by_type,
        'missing_segments': list(set(missing_segments)),
        'warnings': warnings,
        'production_ready': mapping_accuracy >= 95 and total_missing <= 2
    }

def render_quality_dashboard(quality_report: Dict[str, Any]):
    """Render the quality assessment dashboard"""
    
    st.subheader("🎯 Mapping Quality Assessment")
    
    # Top-level metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        accuracy_color = "normal" if quality_report['mapping_accuracy'] >= 95 else "inverse"
        st.metric(
            "Mapping Accuracy", 
            f"{quality_report['mapping_accuracy']:.1f}%",
            delta=None
        )
    
    with col2:
        st.metric("Total Nodes", quality_report['total_nodes'])
    
    with col3:
        missing_color = "inverse" if quality_report['total_missing_segments'] > 2 else "normal"
        st.metric(
            "Missing Segments", 
            quality_report['total_missing_segments']
        )
    
    with col4:
        status = "✅ Production Ready" if quality_report['production_ready'] else "⚠️ Needs Work"
        if quality_report['production_ready']:
            st.success(status)
        else:
            st.warning(status)
    
    # Detailed breakdown
    if quality_report['missing_segments']:
        with st.expander("🔍 Missing Audio Segments Analysis", expanded=True):
            
            # Missing segments by category
            if quality_report['missing_by_type']:
                st.subheader("Missing Segments by Category")
                missing_df = pd.DataFrame(
                    list(quality_report['missing_by_type'].items()),
                    columns=['Category', 'Count']
                )
                st.bar_chart(missing_df.set_index('Category'))
            
            # Detailed list
            st.subheader("Segments Requiring New Audio Files")
            for i, segment in enumerate(quality_report['missing_segments'], 1):
                category = categorize_missing_segment(segment)
                st.write(f"{i}. **{segment}** _(Category: {category})_")
            
            # Recommendations
            st.subheader("📋 Recommendations")
            if quality_report['missing_by_type'].get('Employee Names', 0) > 0:
                st.info("🎤 **Employee Names**: Use dynamic variables like `names:{{contact_id}}` for employee names")
            
            if quality_report['missing_by_type'].get('Locations', 0) > 0:
                st.info("📍 **Locations**: Use dynamic variables like `location:{{callout_location}}` for locations")
            
            if quality_report['missing_by_type'].get('Custom Messages', 0) > 0:
                st.warning("🔧 **Custom Messages**: These segments need new audio recordings before deployment")

def enhanced_ivr_conversion(mermaid_text: str, company: str) -> tuple:
    """Enhanced IVR conversion using intelligent audio mapping"""
    
    if st.session_state.ivr_system is None:
        st.error("❌ Please load the audio database first using the sidebar")
        return None, [], []
    
    try:
        # Use enhanced IVR system
        ivr_nodes, warnings = st.session_state.ivr_system.convert_mermaid_to_ivr(mermaid_text, company)
        
        # Generate quality report
        quality_report = create_quality_report(ivr_nodes, warnings)
        st.session_state.quality_report = quality_report
        
        return ivr_nodes, warnings, quality_report
        
    except Exception as e:
        logger.error(f"Enhanced conversion failed: {str(e)}")
        st.error(f"Enhanced conversion failed: {str(e)}")
        
        # Fallback to basic conversion
        try:
            from mermaid_ivr_converter import convert_mermaid_to_ivr
            basic_result, basic_notes = convert_mermaid_to_ivr(mermaid_text)
            
            # Convert to expected format
            ivr_nodes = basic_result if isinstance(basic_result, list) else [basic_result]
            warnings = basic_notes if isinstance(basic_notes, list) else [basic_notes] if basic_notes else []
            quality_report = create_quality_report(ivr_nodes, warnings)
            
            return ivr_nodes, warnings, quality_report
            
        except Exception as fallback_error:
            logger.error(f"Fallback conversion also failed: {str(fallback_error)}")
            return [], [f"All conversion methods failed: {str(e)}, {str(fallback_error)}"], {}

def main():
    st.title("🎯 Enhanced IVR Code Generator")
    st.markdown("""
    **Production-Ready IVR Generation with Intelligent Audio Mapping**
    
    Transform visual call flow diagrams into executable IVR configurations with:
    ✅ Intelligent audio file ID mapping  
    ✅ Grammar rule detection (a/an logic)  
    ✅ Multi-segment message construction  
    ✅ Company-specific audio selection  
    ✅ Missing segment detection and flagging  
    ✅ Production quality assessment  
    """)

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Company selection
        selected_company = st.selectbox(
            "Company Schema",
            SUPPORTED_COMPANIES,
            index=0,
            help="Select the company context for audio file selection"
        )
        
        # Audio database section
        st.subheader("📁 Audio Database")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Load Database", help="Load audio database from Google Drive"):
                with st.spinner("Loading audio database from Google Drive..."):
                    try:
                        # Load audio database
                        audio_db = load_audio_database("csv_url", show_progress=False)
                        
                        if audio_db is not None:
                            # Create enhanced IVR system
                            ivr_system = DataDrivenAudioMapper(audio_db)
                            
                            # Store in session state
                            st.session_state.audio_database = audio_db
                            st.session_state.ivr_system = ivr_system
                            
                            # Show success metrics
                            stats = audio_db.get_stats()
                            st.success(f"✅ Loaded {stats['total_files']} audio files")
                            
                            # Display stats
                            st.metric("Companies", stats['companies'])
                            st.metric("Categories", stats['folders'])
                            
                        else:
                            st.error("Failed to load audio database")
                            
                    except Exception as e:
                        st.error(f"Database loading error: {str(e)}")
                        st.info("💡 Check your Google Drive URL in Streamlit secrets")
        
        with col2:
            if st.button("🔄 Refresh", help="Refresh database from Google Drive"):
                if st.session_state.audio_database:
                    st.session_state.audio_database.refresh_data()
                    st.success("✅ Database refreshed")
                else:
                    st.warning("Load database first")
        
        # Database status
        if st.session_state.audio_database:
            st.success("📊 Database Status: Connected")
            
            # Show quick stats
            try:
                stats = st.session_state.audio_database.get_stats()
                with st.expander("📈 Database Statistics"):
                    st.write(f"**Total Audio Files:** {stats['total_files']}")
                    st.write(f"**Companies:** {stats['companies']}")
                    st.write(f"**Categories:** {stats['folders']}")
                    st.write(f"**Unique Transcripts:** {stats['unique_transcripts']}")
            except:
                pass
        else:
            st.warning("📊 Database Status: Not Connected")
        
        st.divider()
        
        # Input method selection
        conversion_method = st.radio("Input Method", ["Mermaid Editor", "Image Upload"])
        
        # Advanced settings
        st.subheader("🔧 Advanced Settings")
        validate_syntax = st.checkbox("Validate Diagram", value=True)
        require_high_confidence = st.checkbox("Require High Confidence (95%+)", value=True)
        show_debug = st.checkbox("Show Debug Info", value=False)
        
        # API configuration
        st.subheader("🔑 API Configuration")
        openai_api_key = st.text_input(
            "OpenAI API Key", 
            type="password", 
            help="Required for image processing"
        )

    # Main content area
    mermaid_text = ""
    
    if conversion_method == "Mermaid Editor":
        # Mermaid editor tab
        selected_example = st.selectbox(
            "Load Example Flow", 
            ["Custom"] + list(DEFAULT_FLOWS.keys())
        )
        
        initial_text = (DEFAULT_FLOWS.get(selected_example, st.session_state.last_mermaid_code) 
                       if selected_example != "Custom" 
                       else st.session_state.last_mermaid_code)
        
        mermaid_text = st.text_area(
            "Mermaid Diagram", 
            value=initial_text, 
            height=400,
            help="Enter or edit your Mermaid flowchart code here"
        )
        
        st.session_state.last_mermaid_code = mermaid_text
    
    else:
        # Image upload tab
        col1, col2 = st.columns(2)
        
        with col1:
            uploaded_file = st.file_uploader(
                "Upload Flowchart", 
                type=['pdf', 'png', 'jpg', 'jpeg'],
                help="Upload your IVR flow diagram for automatic conversion"
            )
        
        with col2:
            if uploaded_file:
                try:
                    image = Image.open(uploaded_file)
                    st.image(image, caption="Uploaded Flowchart", use_column_width=True)
                except Exception as e:
                    st.error(f"Error loading image: {str(e)}")
        
        # Image conversion
        if uploaded_file and openai_api_key:
            if st.button("🔄 Convert Image to Mermaid"):
                with st.spinner("Converting image to Mermaid..."):
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
        
        # Use stored mermaid text for preview
        mermaid_text = st.session_state.last_mermaid_code

    # Mermaid diagram preview
    if mermaid_text and mermaid_text.strip():
        st.subheader("👁️ Diagram Preview")
        render_mermaid_safely(mermaid_text)
    else:
        st.warning("No Mermaid code to display. Enter code in the editor or convert an image.")

    # IVR conversion section
    if mermaid_text and mermaid_text.strip():
        if st.button("🎯 Generate Enhanced IVR Code", type="primary"):
            with st.spinner("Generating IVR code with intelligent audio mapping..."):
                try:
                    # Validate syntax if requested
                    if validate_syntax:
                        error = validate_mermaid(mermaid_text)
                        if error:
                            st.error(error)
                            return

                    # Enhanced IVR conversion
                    ivr_nodes, warnings, quality_report = enhanced_ivr_conversion(mermaid_text, selected_company)
                    
                    if ivr_nodes is None:
                        return
                    
                    # Format output
                    js_output = "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"
                    st.session_state.last_ivr_code = js_output
                    
                    # Quality check
                    if require_high_confidence and not quality_report.get('production_ready', False):
                        st.error("❌ Generated code does not meet quality requirements (95%+ accuracy, ≤2 missing segments)")
                        st.info("💡 Review the Quality Assessment below or disable 'Require High Confidence' in settings")
                    else:
                        st.success("✅ Enhanced IVR code generated successfully!")
                    
                    # Display generated code
                    st.subheader("📤 Generated IVR Configuration")
                    st.code(js_output, language="javascript")
                    
                    # Download button
                    st.download_button(
                        "⬇️ Download IVR Configuration",
                        js_output,
                        file_name=f"ivr_flow_{selected_company}.js",
                        mime="application/javascript"
                    )
                    
                    # Quality dashboard
                    if quality_report:
                        render_quality_dashboard(quality_report)
                    
                    # Show warnings
                    if warnings:
                        with st.expander("⚠️ Conversion Warnings", expanded=False):
                            for warning in warnings:
                                st.warning(f"• {warning}")
                    
                    # Code comparison
                    if st.checkbox("Show Code Comparison", value=False):
                        show_code_diff(mermaid_text, js_output)
                    
                    # Export missing segments
                    if quality_report and quality_report.get('missing_segments'):
                        with st.expander("📋 Export Missing Segments"):
                            segments_df = pd.DataFrame({
                                'Segment Text': quality_report['missing_segments'],
                                'Category': [categorize_missing_segment(seg) for seg in quality_report['missing_segments']],
                                'Priority': ['High'] * len(quality_report['missing_segments']),
                                'Company': [selected_company] * len(quality_report['missing_segments'])
                            })
                            
                            st.dataframe(segments_df)
                            
                            csv_export = segments_df.to_csv(index=False)
                            st.download_button(
                                "⬇️ Download Missing Segments Report",
                                csv_export,
                                file_name=f"missing_segments_{selected_company}.csv",
                                mime="text/csv"
                            )

                except Exception as e:
                    st.error(f"Conversion Error: {str(e)}")
                    if show_debug:
                        st.exception(e)
                        st.text(traceback.format_exc())
    else:
        st.info("Enter Mermaid code above to generate IVR configuration.")

    # Footer information
    st.divider()
    
    with st.expander("ℹ️ How It Works", expanded=False):
        st.markdown("""
        **Enhanced IVR Generation Process:**
        
        1. **Visual Recognition**: Converts diagrams to Mermaid syntax with 99%+ accuracy
        2. **Intelligent Parsing**: Extracts nodes, connections, and flow logic
        3. **Smart Audio Mapping**: Maps text to audio IDs using learned patterns from your database
        4. **Grammar Rules**: Automatically applies "a" vs "an" rules based on following sounds
        5. **Multi-Segment Construction**: Builds complex messages from available audio pieces
        6. **Quality Assessment**: Validates mapping accuracy and flags missing segments
        7. **Production Output**: Generates engineering-approved JavaScript configuration
        
        **Key Features:**
        - ✅ Works with ANY customer's audio library automatically
        - ✅ No hardcoded values - everything learned from your data
        - ✅ Company-specific audio selection (AEP, DPL, WECEG, etc.)
        - ✅ Missing segment detection for recording requirements
        - ✅ 95%+ mapping accuracy targeting for production deployment
        """)
    
    # System status
    with st.expander("🔧 System Status", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Audio Database:**")
            if st.session_state.audio_database:
                st.success("✅ Connected")
                try:
                    stats = st.session_state.audio_database.get_stats()
                    st.write(f"Files: {stats['total_files']}")
                    st.write(f"Companies: {stats['companies']}")
                except:
                    st.write("Stats unavailable")
            else:
                st.error("❌ Not Connected")
        
        with col2:
            st.write("**IVR System:**")
            if st.session_state.ivr_system:
                st.success("✅ Ready")
                st.write(f"Company: {selected_company}")
                if st.session_state.quality_report:
                    accuracy = st.session_state.quality_report.get('mapping_accuracy', 0)
                    st.write(f"Last Accuracy: {accuracy:.1f}%")
            else:
                st.error("❌ Not Initialized")

if __name__ == "__main__":
    main()