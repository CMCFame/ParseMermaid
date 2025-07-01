"""
Configurable IVR System - Data-Driven Audio Mapping
Eliminates hardcoded values and learns patterns from audio database

Add this as: configurable_ivr_system.py
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import json

from google_drive_loader import CloudAudioDatabase
from intelligent_audio_mapper import IntelligentAudioMapper, MappingResult

logger = logging.getLogger(__name__)

@dataclass
class QualityReport:
    """Quality assessment report for generated IVR code"""
    total_nodes: int
    nodes_with_warnings: int
    mapping_accuracy: float
    total_missing_segments: int
    missing_segments: List[str]
    warnings: List[str]
    production_ready: bool

class DataDrivenAudioMapper:
    """Main class that provides production-ready IVR generation with quality assessment"""
    
    def __init__(self, audio_database: CloudAudioDatabase):
        self.audio_db = audio_database
        self.mapper = IntelligentAudioMapper(audio_database)
        
    def convert_mermaid_to_ivr(self, mermaid_code: str, company: str = 'aep') -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Convert Mermaid diagram to IVR configuration with intelligent audio mapping
        
        Args:
            mermaid_code: Mermaid flowchart code
            company: Company context for audio selection
            
        Returns:
            Tuple of (IVR node list, warnings list)
        """
        
        ivr_nodes = []
        warnings = []
        
        try:
            # Parse Mermaid to extract content nodes
            content_nodes = self._extract_content_nodes(mermaid_code)
            
            # Convert each content node to IVR
            for i, node_info in enumerate(content_nodes):
                ivr_node = self._convert_node_to_ivr(node_info, i, company)
                ivr_nodes.append(ivr_node)
                
                # Collect warnings
                if '_warnings' in ivr_node:
                    for segment in ivr_node['_warnings'].get('missing_audio_segments', []):
                        warnings.append(f"{ivr_node['label']}: Missing audio for '{segment}'")
            
            # Add connections and logic
            self._add_ivr_logic(ivr_nodes, mermaid_code, company)
            
            # Add standard error handler
            ivr_nodes.append(self._create_error_handler(company))
            
        except Exception as e:
            logger.error(f"IVR conversion failed: {str(e)}")
            warnings.append(f"Conversion error: {str(e)}")
            
            # Return minimal fallback
            ivr_nodes = [self._create_error_handler(company)]
        
        return ivr_nodes, warnings
    
    def _extract_content_nodes(self, mermaid_code: str) -> List[Dict[str, str]]:
        """Extract content nodes from Mermaid diagram"""
        import re
        
        lines = [line.strip() for line in mermaid_code.splitlines() if line.strip()]
        content_nodes = []
        
        for line in lines:
            # Skip flowchart declaration and connections
            if line.startswith('flowchart') or '-->' in line:
                continue
            
            # Extract node content
            node_match = re.search(r'(\w+)\s*[\[\(\{]"?(.*?)"?[\]\)\}]', line)
            if node_match:
                node_id = node_match.group(1)
                node_text = node_match.group(2)
                
                # Clean up HTML breaks and quotes
                node_text = re.sub(r'<br\s*/?>', ' ', node_text)
                node_text = node_text.replace('"', '').replace("'", "").strip()
                
                # Determine node type from brackets
                if '{' in line:
                    node_type = 'decision'
                elif '(' in line:
                    node_type = 'process'
                else:
                    node_type = 'prompt'
                
                content_nodes.append({
                    'id': node_id,
                    'text': node_text,
                    'type': node_type
                })
        
        return content_nodes
    
    def _convert_node_to_ivr(self, node_info: Dict[str, str], index: int, company: str) -> Dict[str, Any]:
        """Convert a single node to IVR format with intelligent audio mapping"""
        
        node_text = node_info['text']
        node_type = node_info['type']
        node_id = node_info['id']
        
        # Use intelligent audio mapping
        mapping_result = self.mapper.map_text_to_audio(node_text, company)
        
        # Build base IVR node
        ivr_node = {
            'label': f'Node{index+1}' if node_id.startswith(('A', 'B', 'C')) else node_id,
            'log': mapping_result.play_log,
            'playPrompt': mapping_result.play_prompt
        }
        
        # Add warnings for missing segments
        if mapping_result.missing_segments:
            ivr_node['_warnings'] = {
                'missing_audio_segments': mapping_result.missing_segments,
                'confidence_score': mapping_result.confidence_score
            }
        
        # Add node-specific properties based on content
        self._add_node_properties(ivr_node, node_text, node_type, company)
        
        return ivr_node
    
    def _add_node_properties(self, ivr_node: Dict[str, Any], node_text: str, 
                           node_type: str, company: str):
        """Add node-specific properties based on content analysis"""
        
        text_lower = node_text.lower()
        
        # Check for menu/input patterns
        if 'press' in text_lower and any(digit in text_lower for digit in '123456789'):
            # This is a menu node
            choices = self._extract_menu_choices(node_text)
            if choices:
                error_prompt = self.mapper.get_company_error_prompt(company)
                
                ivr_node.update({
                    'getDigits': {
                        'numDigits': 1,
                        'maxTries': 3,
                        'maxTime': 7,
                        'validChoices': '|'.join(choices),
                        'errorPrompt': error_prompt,
                        'nonePrompt': error_prompt
                    },
                    'branch': {
                        **{choice: f'Option{choice}' for choice in choices},
                        'error': 'Problems',
                        'none': 'Problems'
                    }
                })
        
        elif 'pin' in text_lower or 'enter' in text_lower:
            # This is PIN entry or input collection
            error_prompt = self.mapper.get_company_error_prompt(company)
            
            ivr_node.update({
                'getDigits': {
                    'numDigits': 5 if 'pin' in text_lower else 1,
                    'maxTries': 3,
                    'maxTime': 7,
                    'validChoices': '{{pin}}' if 'pin' in text_lower else None,
                    'errorPrompt': error_prompt,
                    'nonePrompt': error_prompt
                },
                'branch': {
                    'error': 'Problems',
                    'none': 'Problems'
                }
            })
        
        elif node_type == 'decision':
            # This is a decision node
            ivr_node.update({
                'getDigits': {
                    'numDigits': 1,
                    'maxTries': 3,
                    'maxTime': 7,
                    'validChoices': '1|3',
                    'errorPrompt': self.mapper.get_company_error_prompt(company)
                },
                'branch': {
                    '1': 'NextStep',
                    '3': 'AlternateStep',
                    'error': 'Problems',
                    'none': 'Problems'
                }
            })
    
    def _extract_menu_choices(self, text: str) -> List[str]:
        """Extract menu choices from text like 'Press 1 for X, Press 2 for Y'"""
        import re
        
        # Find all "Press X" patterns
        press_pattern = r'press\s+(\d+)'
        matches = re.findall(press_pattern, text.lower())
        
        return sorted(list(set(matches)))  # Remove duplicates and sort
    
    def _add_ivr_logic(self, ivr_nodes: List[Dict[str, Any]], mermaid_code: str, company: str):
        """Add IVR-specific logic and connections"""
        
        # Add loop protection to first node
        if ivr_nodes:
            first_node = ivr_nodes[0]
            if 'maxLoop' not in first_node:
                first_node['maxLoop'] = ['Main', 3, 'Problems']
        
        # Add goto logic for simple nodes
        for i, node in enumerate(ivr_nodes):
            if 'getDigits' not in node and 'goto' not in node and 'gosub' not in node:
                # Simple prompt node - add goto to next node or hangup
                if i < len(ivr_nodes) - 1:
                    node['goto'] = ivr_nodes[i + 1]['label']
                else:
                    node['goto'] = 'hangup'
    
    def _create_error_handler(self, company: str) -> Dict[str, Any]:
        """Create company-specific error handler"""
        error_prompt = self.mapper.get_company_error_prompt(company)
        
        return {
            'label': 'Problems',
            'nobarge': '1',
            'log': "I'm sorry you are having problems.",
            'playPrompt': error_prompt,
            'goto': 'hangup'
        }
    
    def generate_quality_report(self, ivr_nodes: List[Dict[str, Any]], 
                              warnings: List[str]) -> QualityReport:
        """Generate quality assessment report for the IVR configuration"""
        
        total_nodes = len([node for node in ivr_nodes if node['label'] != 'Problems'])
        nodes_with_warnings = sum(1 for node in ivr_nodes if '_warnings' in node)
        
        # Calculate mapping accuracy
        mapping_accuracy = ((total_nodes - nodes_with_warnings) / total_nodes * 100) if total_nodes > 0 else 0
        
        # Collect all missing segments
        missing_segments = []
        for node in ivr_nodes:
            if '_warnings' in node:
                missing_segments.extend(node['_warnings'].get('missing_audio_segments', []))
        
        # Remove duplicates
        missing_segments = list(set(missing_segments))
        total_missing = len(missing_segments)
        
        # Determine production readiness
        production_ready = mapping_accuracy >= 95 and total_missing <= 2
        
        return QualityReport(
            total_nodes=total_nodes,
            nodes_with_warnings=nodes_with_warnings,
            mapping_accuracy=mapping_accuracy,
            total_missing_segments=total_missing,
            missing_segments=missing_segments,
            warnings=warnings,
            production_ready=production_ready
        )
    
    def categorize_missing_segment(self, segment: str) -> str:
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
    
    def export_missing_segments_report(self, quality_report: QualityReport) -> str:
        """Export missing segments as CSV for recording team"""
        import pandas as pd
        
        if not quality_report.missing_segments:
            return ""
        
        segments_data = []
        for segment in quality_report.missing_segments:
            segments_data.append({
                'Segment Text': segment,
                'Category': self.categorize_missing_segment(segment),
                'Priority': 'High',
                'Notes': 'Required for production deployment'
            })
        
        df = pd.DataFrame(segments_data)
        return df.to_csv(index=False)
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        mapper_stats = self.mapper.get_mapping_stats()
        db_stats = self.audio_db.get_stats()
        
        return {
            **mapper_stats,
            **db_stats,
            'companies_configured': len(self.audio_db.get_companies()),
            'audio_categories': len(self.audio_db.get_folders())
        }

# Convenience function for easy integration
def create_enhanced_ivr_system(secret_key: str = "csv_url") -> Optional[DataDrivenAudioMapper]:
    """
    Create enhanced IVR system with Google Drive integration
    
    Args:
        secret_key: Streamlit secret key containing Google Drive CSV URL
        
    Returns:
        DataDrivenAudioMapper instance or None if initialization failed
    """
    try:
        # Load audio database from Google Drive
        audio_db = CloudAudioDatabase(secret_key)
        
        # Test connectivity
        df = audio_db.get_dataframe()
        if len(df) == 0:
            logger.error("Audio database is empty")
            return None
        
        # Create enhanced system
        system = DataDrivenAudioMapper(audio_db)
        
        logger.info(f"Enhanced IVR system initialized with {len(df)} audio files")
        return system
        
    except Exception as e:
        logger.error(f"Failed to create enhanced IVR system: {str(e)}")
        return None

# Example usage
if __name__ == "__main__":
    print("Configurable IVR System - Production Ready")
    print("Usage in your Streamlit app:")
    print("""
    from configurable_ivr_system import create_enhanced_ivr_system
    
    # Initialize system
    ivr_system = create_enhanced_ivr_system("csv_url")
    
    # Convert Mermaid to IVR
    ivr_nodes, warnings = ivr_system.convert_mermaid_to_ivr(mermaid_code, company='aep')
    
    # Generate quality report
    quality_report = ivr_system.generate_quality_report(ivr_nodes, warnings)
    
    # Check production readiness
    if quality_report.production_ready:
        print("✅ Production Ready!")
    else:
        print("⚠️ Needs review")
    """)