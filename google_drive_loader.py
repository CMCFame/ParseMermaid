"""
Google Drive CSV Loader for Streamlit Cloud
Handles loading CSV files from Google Drive using Streamlit secrets

Add this as: google_drive_loader.py
"""

import streamlit as st
import pandas as pd
import requests
from io import StringIO
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class CloudAudioDatabase:
    """Audio database that loads CSV from Google Drive using Streamlit secrets"""
    
    def __init__(self, secret_key: str = "csv_url"):
        self.secret_key = secret_key
        self._df = None
        self._indexes_built = False
        self._cache_key = None
        
    def _get_drive_url(self) -> str:
        """Get Google Drive URL from Streamlit secrets"""
        if self.secret_key not in st.secrets:
            raise ValueError(f"Secret key '{self.secret_key}' not found in Streamlit secrets")
        
        url = st.secrets[self.secret_key]
        
        # Convert Google Drive sharing URL to direct download URL
        if "drive.google.com" in url:
            if "/file/d/" in url:
                file_id = url.split("/file/d/")[1].split("/")[0]
            elif "id=" in url:
                file_id = url.split("id=")[1].split("&")[0]
            else:
                raise ValueError("Unable to extract file ID from Google Drive URL")
            
            # Create direct download URL
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        
        return url
    
    def _load_data(self):
        """Load data from Google Drive if not already loaded"""
        if self._df is not None:
            return
            
        try:
            csv_url = self._get_drive_url()
            
            # Check if we need to reload (URL changed)
            if self._cache_key != csv_url:
                self._df = None
                self._indexes_built = False
                self._cache_key = csv_url
            
            if self._df is None:
                logger.info("Downloading CSV from Google Drive...")
                
                response = requests.get(csv_url, timeout=30)
                response.raise_for_status()
                
                # Parse CSV
                csv_content = StringIO(response.text)
                self._df = pd.read_csv(csv_content)
                
                # Validate required columns
                required_columns = ['Company', 'Folder', 'File Name', 'Transcript']
                missing_columns = [col for col in required_columns if col not in self._df.columns]
                
                if missing_columns:
                    raise ValueError(f"CSV missing required columns: {missing_columns}")
                
                # Clean data
                self._df['Transcript'] = self._df['Transcript'].astype(str).str.strip()
                self._df['Company'] = self._df['Company'].astype(str).str.strip().str.lower()
                self._df['Folder'] = self._df['Folder'].astype(str).str.strip()
                self._df['File Name'] = self._df['File Name'].astype(str).str.strip()
                
                # Remove empty rows
                self._df = self._df.dropna(subset=['Transcript'])
                self._df = self._df[self._df['Transcript'] != '']
                
                logger.info(f"Successfully loaded {len(self._df)} records from Google Drive")
                
                # Build search indexes
                self._build_indexes()
                
        except Exception as e:
            logger.error(f"Failed to load CSV from Google Drive: {str(e)}")
            raise RuntimeError(f"Could not load audio database: {str(e)}")
    
    def _build_indexes(self):
        """Build search indexes for efficient lookups"""
        if self._indexes_built or self._df is None:
            return
            
        self.phrase_index = {}
        self.company_index = {}
        self.folder_index = {}
        
        for _, row in self._df.iterrows():
            transcript = row['Transcript'].lower().strip()
            company = row['Company'].lower().strip()
            folder = row['Folder'].strip()
            file_name = row['File Name']
            
            # Create audio ID (remove .ulaw extension if present)
            audio_id = file_name.replace('.ulaw', '') if file_name.endswith('.ulaw') else file_name
            
            # Build phrase index (global)
            if transcript not in self.phrase_index:
                self.phrase_index[transcript] = []
            self.phrase_index[transcript].append({
                'audio_id': audio_id,
                'company': company,
                'folder': folder,
                'full_path': f"{folder}:{audio_id}"
            })
            
            # Build company index
            if company not in self.company_index:
                self.company_index[company] = {}
            if transcript not in self.company_index[company]:
                self.company_index[company][transcript] = []
            self.company_index[company][transcript].append({
                'audio_id': audio_id,
                'folder': folder,
                'full_path': f"{folder}:{audio_id}"
            })
            
            # Build folder index
            if folder not in self.folder_index:
                self.folder_index[folder] = {}
            if transcript not in self.folder_index[folder]:
                self.folder_index[folder][transcript] = []
            self.folder_index[folder][transcript].append({
                'audio_id': audio_id,
                'company': company,
                'full_path': f"{folder}:{audio_id}"
            })
        
        self._indexes_built = True
        logger.info("Audio database indexes built successfully")
    
    def get_dataframe(self) -> pd.DataFrame:
        """Get the underlying DataFrame"""
        self._load_data()
        return self._df.copy()  # Return copy to prevent modification
    
    def find_exact_match(self, text: str, company: str = None, folder: str = None) -> List[Dict]:
        """Find exact matches with schema hierarchy: company > folder > global"""
        self._load_data()
        
        text_lower = text.lower().strip()
        company_lower = company.lower().strip() if company else None
        
        # Try company-specific first (highest priority)
        if company_lower and company_lower in self.company_index:
            if text_lower in self.company_index[company_lower]:
                return self.company_index[company_lower][text_lower]
        
        # Try folder-specific
        if folder and folder in self.folder_index:
            if text_lower in self.folder_index[folder]:
                return self.folder_index[folder][text_lower]
        
        # Fall back to global search
        return self.phrase_index.get(text_lower, [])
    
    def search_partial(self, text: str, company: str = None, max_results: int = 10) -> List[Dict]:
        """Search for partial matches (for building segments)"""
        self._load_data()
        
        text_lower = text.lower().strip()
        results = []
        
        # Search in company-specific first if provided
        search_space = (self.company_index.get(company.lower(), {}) 
                       if company else self.phrase_index)
        
        for phrase, audio_list in search_space.items():
            if text_lower in phrase or phrase in text_lower:
                for audio_info in audio_list:
                    audio_info['matched_phrase'] = phrase
                    results.append(audio_info)
                    
                if len(results) >= max_results:
                    break
        
        return results[:max_results]
    
    def get_companies(self) -> List[str]:
        """Get list of available companies"""
        self._load_data()
        return sorted(self._df['Company'].unique())
    
    def get_folders(self) -> List[str]:
        """Get list of available folders/categories"""
        self._load_data()
        return sorted(self._df['Folder'].unique())
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics"""
        self._load_data()
        
        return {
            'total_files': len(self._df),
            'companies': len(self._df['Company'].unique()),
            'folders': len(self._df['Folder'].unique()),
            'unique_transcripts': len(self._df['Transcript'].unique())
        }
    
    def refresh_data(self):
        """Force reload data from Google Drive"""
        self._df = None
        self._indexes_built = False
        self._cache_key = None
        logger.info("Audio database cache cleared - will reload on next access")

# Utility function for easy initialization in Streamlit
def load_audio_database(secret_key: str = "csv_url", 
                       show_progress: bool = True) -> Optional[CloudAudioDatabase]:
    """
    Load audio database from Google Drive with Streamlit integration
    
    Args:
        secret_key: Key in st.secrets containing the Google Drive URL
        show_progress: Whether to show loading progress in Streamlit
    
    Returns:
        CloudAudioDatabase instance or None if loading failed
    """
    try:
        if show_progress:
            with st.spinner("Loading audio database from Google Drive..."):
                db = CloudAudioDatabase(secret_key)
                df = db.get_dataframe()
                
                if len(df) == 0:
                    st.warning("⚠️ Audio database is empty")
                    return None
                
                stats = db.get_stats()
                st.success(f"✅ Loaded {stats['total_files']} audio files")
                
                # Show quick stats
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Companies", stats['companies'])
                with col2:
                    st.metric("Categories", stats['folders'])
                with col3:
                    st.metric("Unique Phrases", stats['unique_transcripts'])
                
                return db
        else:
            return CloudAudioDatabase(secret_key)
            
    except Exception as e:
        if show_progress:
            st.error(f"Failed to load audio database: {str(e)}")
            
            # Help with common issues
            if "Secret key" in str(e):
                st.info("💡 **Fix**: Add your Google Drive CSV URL to Streamlit secrets")
                st.code(f'{secret_key} = "https://drive.google.com/file/d/YOUR_FILE_ID/view"')
            elif "extract file ID" in str(e):
                st.info("💡 **Fix**: Make sure your Google Drive URL is a shareable link")
            elif "Missing required columns" in str(e):
                st.info("💡 **Fix**: Your CSV needs these columns: Company, Folder, File Name, Transcript")
        
        return None

# Example usage and testing
if __name__ == "__main__":
    # This would be used for testing the module
    print("Google Drive Audio Database Loader")
    print("Add this file to your Streamlit app and import as:")
    print("from google_drive_loader import load_audio_database")