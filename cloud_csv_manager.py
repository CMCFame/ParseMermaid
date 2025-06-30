"""
Cloud CSV Database Manager for Streamlit Cloud Deployment
Handles audio database loading from various sources without committing to GitHub
"""

import streamlit as st
import pandas as pd
import io
import os
import json
import tempfile
import base64
from typing import Optional, Dict, Any
import requests
from pathlib import Path

class CloudCSVManager:
    """Manages CSV database loading for cloud deployment"""
    
    def __init__(self):
        self.csv_data = None
        self.csv_source = None
        self.temp_file_path = None
        
    def load_csv_data(self) -> Optional[str]:
        """
        Load CSV data from various sources based on environment and configuration
        Returns the temporary file path if successful
        """
        # Try different loading methods in priority order
        loading_methods = [
            self._load_from_secrets,
            self._load_from_url,
            self._load_from_upload,
            self._load_sample_data
        ]
        
        for method in loading_methods:
            try:
                result = method()
                if result:
                    st.success(f"✅ Audio database loaded from: {self.csv_source}")
                    return result
            except Exception as e:
                st.warning(f"⚠️ {method.__name__} failed: {str(e)}")
                continue
        
        st.error("❌ Could not load audio database from any source")
        return None
    
    def _load_from_secrets(self) -> Optional[str]:
        """Load CSV from Streamlit secrets (for smaller databases)"""
        if "csv_data" in st.secrets:
            # Decode base64 encoded CSV data
            csv_base64 = st.secrets["csv_data"]
            csv_content = base64.b64decode(csv_base64).decode('utf-8')
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
            temp_file.write(csv_content)
            temp_file.close()
            
            self.temp_file_path = temp_file.name
            self.csv_source = "Streamlit Secrets"
            return temp_file.name
            
        elif "csv_url" in st.secrets:
            # Load from URL specified in secrets
            return self._load_from_url(st.secrets["csv_url"])
        
        return None
    
    def _load_from_url(self, url: str = None) -> Optional[str]:
        """Load CSV from a URL (S3, Google Drive, etc.)"""
        if not url and "csv_url" in st.secrets:
            url = st.secrets["csv_url"]
        
        if not url:
            return None
        
        # Add authentication headers if provided
        headers = {}
        if "csv_auth_header" in st.secrets:
            auth_header = st.secrets["csv_auth_header"]
            if isinstance(auth_header, dict):
                headers.update(auth_header)
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        temp_file.write(response.text)
        temp_file.close()
        
        self.temp_file_path = temp_file.name
        self.csv_source = f"URL ({url[:50]}...)"
        return temp_file.name
    
    def _load_from_upload(self) -> Optional[str]:
        """Load CSV from user upload"""
        st.subheader("📁 Upload Audio Database")
        st.info("""
        **For testing and development**: Upload your `cf_general_structure.csv` file.
        
        **Required format:**
        - Columns: Company, Folder, File Name, Transcript
        - CSV format with proper encoding
        """)
        
        uploaded_file = st.file_uploader(
            "Choose CSV file", 
            type=['csv'],
            help="Upload your audio transcription database"
        )
        
        if uploaded_file is not None:
            # Validate CSV format
            try:
                df = pd.read_csv(uploaded_file)
                required_columns = ['Company', 'Folder', 'File Name', 'Transcript']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    st.error(f"❌ Missing required columns: {', '.join(missing_columns)}")
                    return None
                
                # Save to temporary file
                temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
                df.to_csv(temp_file.name, index=False)
                temp_file.close()
                
                self.temp_file_path = temp_file.name
                self.csv_source = f"User Upload ({uploaded_file.name})"
                
                # Show database stats
                st.success(f"✅ CSV validated successfully!")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Records", f"{len(df):,}")
                with col2:
                    st.metric("Companies", df['Company'].nunique())
                with col3:
                    st.metric("Folders", df['Folder'].nunique())
                
                return temp_file.name
                
            except Exception as e:
                st.error(f"❌ Error reading CSV: {str(e)}")
                return None
        
        return None
    
    def _load_sample_data(self) -> Optional[str]:
        """Load sample data for demonstration"""
        st.warning("🧪 Using sample data for demonstration")
        st.info("""
        **Demo Mode**: This sample database contains representative audio file mappings.
        For production use, please provide your actual audio database.
        """)
        
        # Create comprehensive sample data
        sample_data = self._create_sample_database()
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        sample_data.to_csv(temp_file.name, index=False)
        temp_file.close()
        
        self.temp_file_path = temp_file.name
        self.csv_source = "Sample Data (Demo Mode)"
        
        # Show sample stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Sample Records", f"{len(sample_data):,}")
        with col2:
            st.metric("Sample Companies", sample_data['Company'].nunique())
        with col3:
            st.metric("Sample Folders", sample_data['Folder'].nunique())
        
        return temp_file.name
    
    def _create_sample_database(self) -> pd.DataFrame:
        """Create a comprehensive sample database"""
        sample_data = [
            # DPL Company - Comprehensive callflow segments
            {"Company": "dpl", "Folder": "callflow", "File Name": "1191.ulaw", "Transcript": "This is an"},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1190.ulaw", "Transcript": "This is a"},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1274.ulaw", "Transcript": "callout from"},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1002.ulaw", "Transcript": "Press 1 if this is"},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1005.ulaw", "Transcript": "if you need more time to get"},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1006.ulaw", "Transcript": "to the phone"},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1004.ulaw", "Transcript": "is not home"},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1643.ulaw", "Transcript": "to repeat this message"},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1009.ulaw", "Transcript": "Invalid entry. Please try again."},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1010.ulaw", "Transcript": "We did not receive your response."},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1008.ulaw", "Transcript": "Enter your PIN"},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1316.ulaw", "Transcript": "Are you available for this callout?"},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1167.ulaw", "Transcript": "An accepted response has been recorded."},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1021.ulaw", "Transcript": "A declined response has been recorded."},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1029.ulaw", "Transcript": "Thank you. Goodbye."},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1351.ulaw", "Transcript": "I'm sorry you are having problems."},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1290.ulaw", "Transcript": "Press"},
            {"Company": "dpl", "Folder": "callflow", "File Name": "1019.ulaw", "Transcript": "callout"},
            
            # DPL Locations
            {"Company": "dpl", "Folder": "location", "File Name": "4000.ulaw", "Transcript": "North Dayton"},
            {"Company": "dpl", "Folder": "location", "File Name": "4001.ulaw", "Transcript": "South Dayton"},
            {"Company": "dpl", "Folder": "location", "File Name": "4002.ulaw", "Transcript": "Level 2"},
            {"Company": "dpl", "Folder": "location", "File Name": "4003.ulaw", "Transcript": "Downtown"},
            {"Company": "dpl", "Folder": "location", "File Name": "4004.ulaw", "Transcript": "West Side"},
            {"Company": "dpl", "Folder": "location", "File Name": "4005.ulaw", "Transcript": "East Side"},
            
            # DPL Callout Types
            {"Company": "dpl", "Folder": "callout_type", "File Name": "1001.ulaw", "Transcript": "electric"},
            {"Company": "dpl", "Folder": "callout_type", "File Name": "1002.ulaw", "Transcript": "emergency"},
            {"Company": "dpl", "Folder": "callout_type", "File Name": "1003.ulaw", "Transcript": "normal"},
            {"Company": "dpl", "Folder": "callout_type", "File Name": "1004.ulaw", "Transcript": "maintenance"},
            {"Company": "dpl", "Folder": "callout_type", "File Name": "1005.ulaw", "Transcript": "urgent"},
            
            # AEP Company
            {"Company": "aep", "Folder": "callflow", "File Name": "1191.ulaw", "Transcript": "This is an"},
            {"Company": "aep", "Folder": "callflow", "File Name": "1190.ulaw", "Transcript": "This is a"},
            {"Company": "aep", "Folder": "callflow", "File Name": "1274.ulaw", "Transcript": "callout from"},
            {"Company": "aep", "Folder": "callflow", "File Name": "1009.ulaw", "Transcript": "Invalid entry. Please try again."},
            {"Company": "aep", "Folder": "company", "File Name": "1201.ulaw", "Transcript": "AEP"},
            {"Company": "aep", "Folder": "location", "File Name": "5000.ulaw", "Transcript": "Columbus"},
            {"Company": "aep", "Folder": "location", "File Name": "5001.ulaw", "Transcript": "Cleveland"},
            {"Company": "aep", "Folder": "callout_type", "File Name": "1001.ulaw", "Transcript": "electric"},
            {"Company": "aep", "Folder": "callout_type", "File Name": "1002.ulaw", "Transcript": "emergency"},
            
            # General/Standard segments
            {"Company": "general", "Folder": "standard", "File Name": "PRS1.ulaw", "Transcript": "Press 1"},
            {"Company": "general", "Folder": "standard", "File Name": "PRS3.ulaw", "Transcript": "Press 3"},
            {"Company": "general", "Folder": "standard", "File Name": "PRS7.ulaw", "Transcript": "Press 7"},
            {"Company": "general", "Folder": "standard", "File Name": "PRS9.ulaw", "Transcript": "Press 9"},
            {"Company": "general", "Folder": "digits", "File Name": "1.ulaw", "Transcript": "1"},
            {"Company": "general", "Folder": "digits", "File Name": "3.ulaw", "Transcript": "3"},
            {"Company": "general", "Folder": "digits", "File Name": "7.ulaw", "Transcript": "7"},
            {"Company": "general", "Folder": "digits", "File Name": "9.ulaw", "Transcript": "9"},
            
            # WECEG Company (additional)
            {"Company": "weceg", "Folder": "callflow", "File Name": "1191.ulaw", "Transcript": "This is an"},
            {"Company": "weceg", "Folder": "callflow", "File Name": "1274.ulaw", "Transcript": "callout from"},
            {"Company": "weceg", "Folder": "company", "File Name": "1301.ulaw", "Transcript": "WECEG"},
            {"Company": "weceg", "Folder": "location", "File Name": "6000.ulaw", "Transcript": "Wisconsin"},
            {"Company": "weceg", "Folder": "callout_type", "File Name": "1001.ulaw", "Transcript": "electric"},
            
            # Job Classifications
            {"Company": "general", "Folder": "job_classification", "File Name": "2001.ulaw", "Transcript": "lineman"},
            {"Company": "general", "Folder": "job_classification", "File Name": "2002.ulaw", "Transcript": "technician"},
            {"Company": "general", "Folder": "job_classification", "File Name": "2003.ulaw", "Transcript": "engineer"},
            {"Company": "general", "Folder": "job_classification", "File Name": "2004.ulaw", "Transcript": "supervisor"},
            
            # Custom Messages
            {"Company": "general", "Folder": "custom_message", "File Name": "3001.ulaw", "Transcript": "Please report to your designated location"},
            {"Company": "general", "Folder": "custom_message", "File Name": "3002.ulaw", "Transcript": "Bring safety equipment"},
            {"Company": "general", "Folder": "custom_message", "File Name": "3003.ulaw", "Transcript": "Weather conditions may be hazardous"},
        ]
        
        return pd.DataFrame(sample_data)
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get information about the currently loaded database"""
        if not self.temp_file_path:
            return {"status": "No database loaded"}
        
        try:
            df = pd.read_csv(self.temp_file_path)
            return {
                "status": "Loaded",
                "source": self.csv_source,
                "total_records": len(df),
                "companies": list(df['Company'].unique()),
                "folders": list(df['Folder'].unique()),
                "file_path": self.temp_file_path
            }
        except Exception as e:
            return {"status": "Error", "error": str(e)}
    
    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_file_path and os.path.exists(self.temp_file_path):
            try:
                os.unlink(self.temp_file_path)
            except:
                pass  # File might be in use

# Streamlit Cloud Configuration Helper
class StreamlitCloudConfig:
    """Helper for managing Streamlit Cloud configuration"""
    
    @staticmethod
    def setup_secrets_example():
        """Show example secrets.toml configuration"""
        return """
# Example .streamlit/secrets.toml for Streamlit Cloud
# Add this to your repository's .streamlit/secrets.toml (this file is not committed to GitHub)

# Method 1: Store CSV data directly (for smaller files)
csv_data = "Q29tcGFueSwgRm9sZGVyLCBGaWxlIE5hbWUsIFRyYW5zY3JpcHQ..."  # Base64 encoded CSV

# Method 2: Store URL to CSV file (recommended for larger files)
csv_url = "https://your-storage.amazonaws.com/audio-database.csv"

# Optional: Authentication headers for private URLs
[csv_auth_header]
Authorization = "Bearer your-token"
X-API-Key = "your-api-key"

# Alternative: Google Drive public sharing URL
# csv_url = "https://drive.google.com/uc?id=YOUR_FILE_ID&export=download"

# Alternative: AWS S3 presigned URL
# csv_url = "https://bucket-name.s3.region.amazonaws.com/file.csv?X-Amz-Algorithm=..."
"""
    
    @staticmethod
    def encode_csv_for_secrets(csv_file_path: str) -> str:
        """Encode CSV file to base64 for secrets storage"""
        with open(csv_file_path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
        return encoded

# Integration with existing app
def get_csv_database_path() -> Optional[str]:
    """
    Main function to get CSV database path for the IVR app
    Returns None if no database is available
    """
    # Initialize CSV manager if not in session state
    if 'csv_manager' not in st.session_state:
        st.session_state.csv_manager = CloudCSVManager()
    
    manager = st.session_state.csv_manager
    
    # Try to load CSV if not already loaded
    if not manager.temp_file_path:
        csv_path = manager.load_csv_data()
        return csv_path
    else:
        return manager.temp_file_path

def show_database_status():
    """Show current database status in sidebar"""
    if 'csv_manager' in st.session_state:
        info = st.session_state.csv_manager.get_database_info()
        
        if info["status"] == "Loaded":
            st.sidebar.success(f"✅ Database: {info['source']}")
            with st.sidebar.expander("📊 Database Info"):
                st.write(f"**Records**: {info['total_records']:,}")
                st.write(f"**Companies**: {', '.join(info['companies'])}")
                st.write(f"**Folders**: {len(info['folders'])}")
        else:
            st.sidebar.warning("⚠️ No database loaded")

# Example usage in your main app
def integrate_with_existing_app():
    """Example of how to integrate with your existing app.py"""
    example_code = """
# Add this to the top of your app.py

from cloud_csv_manager import get_csv_database_path, show_database_status

# In your sidebar or main area
show_database_status()

# When you need the CSV path for the converter
csv_path = get_csv_database_path()

if csv_path:
    # Use the enhanced converter with the CSV path
    from integration_replacement import convert_mermaid_to_ivr_with_report
    
    ivr_flow, notes, report = convert_mermaid_to_ivr_with_report(
        mermaid_text,
        company=selected_company,
        csv_file_path=csv_path  # Use the dynamically loaded CSV
    )
else:
    st.error("❌ Audio database not available. Please upload CSV or configure external source.")
"""
    
    return example_code

if __name__ == "__main__":
    st.title("🔧 Cloud CSV Database Manager Test")
    
    # Test the CSV manager
    manager = CloudCSVManager()
    csv_path = manager.load_csv_data()
    
    if csv_path:
        st.success("✅ CSV Manager working correctly!")
        info = manager.get_database_info()
        st.json(info)
        
        # Show configuration examples
        with st.expander("⚙️ Streamlit Cloud Configuration"):
            st.code(StreamlitCloudConfig.setup_secrets_example(), language="toml")
        
        # Show integration example
        with st.expander("🔗 Integration Example"):
            st.code(integrate_with_existing_app(), language="python")
    else:
        st.error("❌ CSV Manager test failed")