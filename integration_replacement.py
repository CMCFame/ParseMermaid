"""
Fixed Drop-in Replacement for mermaid_ivr_converter.py
FIXED VERSION - Handles missing components gracefully for Streamlit Cloud
"""

import os
import json
from typing import List, Dict, Any, Tuple, Optional

# Try to import enhanced components with graceful fallback
try:
    from enhanced_ivr_converter import EnhancedMermaidIVRConverter, validate_ivr_output
    ENHANCED_MODE_AVAILABLE = True
    print("✅ Enhanced converter loaded successfully")
except ImportError as e:
    ENHANCED_MODE_AVAILABLE = False
    print(f"ℹ️ Enhanced mapping not available: {str(e)}")

# Import the original converter as fallback
try:
    from mermaid_ivr_converter import MermaidIVRConverter as BasicMermaidIVRConverter
    BASIC_CONVERTER_AVAILABLE = True
    print("✅ Basic converter available as fallback")
except ImportError as e:
    BASIC_CONVERTER_AVAILABLE = False
    print(f"⚠️ Basic converter not available: {str(e)}")

class IntelligentMermaidIVRConverter:
    """
    Intelligent drop-in replacement for the basic MermaidIVRConverter
    Maintains same interface while adding smart mapping capabilities
    """
    
    def __init__(self, csv_file_path: str = "cf_general_structure.csv", 
                 config: Optional[Dict[str, Any]] = None):
        self.csv_file_path = csv_file_path
        self.config = config or {}
        self.enhanced_available = ENHANCED_MODE_AVAILABLE and os.path.exists(csv_file_path)
        self.last_conversion_report = None
        
        # Initialize the appropriate converter
        if self.enhanced_available:
            try:
                self.enhanced_converter = EnhancedMermaidIVRConverter(csv_file_path, config)
                print("✅ Enhanced converter initialized successfully")
            except Exception as e:
                print(f"⚠️ Enhanced converter failed to initialize: {str(e)}")
                self.enhanced_available = False
        
        # Fallback to basic converter if enhanced not available
        if not self.enhanced_available and BASIC_CONVERTER_AVAILABLE:
            try:
                self.basic_converter = BasicMermaidIVRConverter(config)
                print("ℹ️ Using basic converter as fallback")
            except Exception as e:
                print(f"⚠️ Basic converter initialization failed: {str(e)}")
    
    def convert(self, mermaid_code: str, company: str = None) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Convert Mermaid code to IVR configuration
        Returns: (ivr_flow, notes) - same interface as original
        """
        if self.enhanced_available:
            return self._convert_enhanced(mermaid_code, company)
        elif BASIC_CONVERTER_AVAILABLE:
            return self._convert_basic(mermaid_code)
        else:
            return self._convert_emergency(mermaid_code)
    
    def _convert_enhanced(self, mermaid_code: str, company: str = None) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Convert using enhanced intelligent mapping"""
        try:
            ivr_flow, conversion_report = self.enhanced_converter.convert(mermaid_code, company)
            self.last_conversion_report = conversion_report
            
            # Extract notes for compatibility with original interface
            notes = conversion_report.get('notes_found', [])
            
            # Add quality information as notes
            summary = conversion_report['conversion_summary']
            if summary['nodes_requiring_review'] > 0:
                notes.append(f"⚠️ {summary['nodes_requiring_review']} nodes require manual review")
            
            if conversion_report['missing_audio_files']:
                missing_count = len(conversion_report['missing_audio_files'])
                notes.append(f"🎤 {missing_count} missing audio segments detected")
            
            # Add success rate note
            success_rate = summary['overall_success_rate']
            if success_rate >= 95:
                notes.append(f"✅ High quality: {success_rate}% success rate")
            elif success_rate >= 80:
                notes.append(f"⚠️ Good quality: {success_rate}% success rate - review recommended")
            else:
                notes.append(f"❌ Low quality: {success_rate}% success rate - manual review required")
            
            return ivr_flow, notes
            
        except Exception as e:
            print(f"❌ Enhanced conversion failed: {str(e)}")
            print("🔄 Falling back to basic conversion...")
            return self._convert_basic(mermaid_code)
    
    def _convert_basic(self, mermaid_code: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Convert using basic converter"""
        if BASIC_CONVERTER_AVAILABLE:
            try:
                return self.basic_converter.convert(mermaid_code)
            except Exception as e:
                print(f"❌ Basic conversion failed: {str(e)}")
                return self._convert_emergency(mermaid_code)
        else:
            return self._convert_emergency(mermaid_code)
    
    def _convert_emergency(self, mermaid_code: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Emergency fallback converter"""
        print("⚠️ Using emergency fallback converter")
        
        # Extract basic node information
        nodes = []
        lines = [line.strip() for line in mermaid_code.split('\n') if line.strip()]
        
        node_count = 0
        for line in lines:
            if '-->' not in line and any(bracket in line for bracket in ['[', '{', '(']):
                node_count += 1
                
                # Extract node ID and text
                import re
                match = re.match(r'^(\w+)\s*[\[\{\(]([^}]*)', line)
                if match:
                    node_id, content = match.groups()
                    
                    # Clean content
                    content = re.sub(r'<br\s*/?>', ' ', content)
                    content = content.replace('"', '').strip()
                    
                    # Create basic node
                    node = {
                        "label": node_id,
                        "log": content,
                        "playPrompt": [f"callflow:{node_id}"],
                    }
                    
                    # Add goto for simple flow
                    if node_count > 1:
                        node["goto"] = "hangup"
                    
                    nodes.append(node)
        
        # Add basic error handler
        if nodes:
            nodes.append({
                "label": "Problems",
                "playLog": "I'm sorry you are having problems.",
                "playPrompt": ["callflow:1351"],
                "goto": "hangup"
            })
        
        notes = [
            "⚠️ Emergency conversion used - limited functionality",
            "💡 Install enhanced components for intelligent mapping",
            "🔧 Audio file IDs may need manual adjustment"
        ]
        
        return nodes, notes
    
    def get_conversion_report(self) -> Optional[Dict]:
        """Get detailed conversion report (enhanced mode only)"""
        return self.last_conversion_report
    
    def validate_output(self, ivr_flow: List[Dict]) -> Dict:
        """Validate the generated IVR output"""
        if self.enhanced_available and 'validate_ivr_output' in globals():
            try:
                return validate_ivr_output(ivr_flow)
            except Exception as e:
                print(f"⚠️ Enhanced validation failed: {str(e)}")
        
        # Basic validation fallback
        errors = []
        warnings = []
        
        labels = set()
        for i, node in enumerate(ivr_flow):
            if 'label' not in node:
                errors.append(f"Node {i}: Missing label")
            elif node['label'] in labels:
                errors.append(f"Node {i}: Duplicate label '{node['label']}'")
            else:
                labels.add(node['label'])
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'node_count': len(ivr_flow),
            'validation_mode': 'basic'
        }

# Global instance for backward compatibility
_global_converter = None

def get_converter(csv_file_path: str = "cf_general_structure.csv", 
                 config: Optional[Dict[str, Any]] = None) -> IntelligentMermaidIVRConverter:
    """Get a converter instance"""
    global _global_converter
    
    # Reuse global instance if parameters haven't changed
    if (_global_converter is None or 
        _global_converter.csv_file_path != csv_file_path or
        _global_converter.config != config):
        _global_converter = IntelligentMermaidIVRConverter(csv_file_path, config)
    
    return _global_converter

def convert_mermaid_to_ivr(mermaid_code: str, company: str = None, 
                          csv_file_path: str = "cf_general_structure.csv",
                          config: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Main conversion function - drop-in replacement for the original
    
    Args:
        mermaid_code: The Mermaid diagram code
        company: Company context for intelligent mapping (new parameter)
        csv_file_path: Path to audio database CSV (new parameter)
        config: Configuration options
    
    Returns:
        Tuple of (ivr_flow, notes) - same as original interface
    """
    try:
        converter = get_converter(csv_file_path, config)
        return converter.convert(mermaid_code, company)
    except Exception as e:
        print(f"❌ Conversion completely failed: {str(e)}")
        # Return minimal fallback
        return [{
            "label": "Error", 
            "log": "Conversion failed", 
            "playPrompt": ["callflow:1351"],
            "goto": "hangup"
        }], [f"❌ Conversion error: {str(e)}"]

def convert_mermaid_to_ivr_with_report(mermaid_code: str, company: str = None,
                                     csv_file_path: str = "cf_general_structure.csv",
                                     config: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], List[str], Optional[Dict]]:
    """
    Enhanced conversion function that also returns detailed report
    
    Returns:
        Tuple of (ivr_flow, notes, conversion_report)
    """
    try:
        converter = get_converter(csv_file_path, config)
        ivr_flow, notes = converter.convert(mermaid_code, company)
        report = converter.get_conversion_report()
        
        return ivr_flow, notes, report
    except Exception as e:
        print(f"❌ Enhanced conversion failed: {str(e)}")
        # Return basic conversion without report
        ivr_flow, notes = convert_mermaid_to_ivr(mermaid_code, company, csv_file_path, config)
        return ivr_flow, notes, None

def validate_ivr_configuration(ivr_flow: List[Dict], 
                             csv_file_path: str = "cf_general_structure.csv") -> Dict:
    """
    Validate an IVR configuration
    
    Args:
        ivr_flow: The IVR flow to validate
        csv_file_path: Path to audio database for reference checking
    
    Returns:
        Validation result dictionary
    """
    try:
        converter = get_converter(csv_file_path)
        return converter.validate_output(ivr_flow)
    except Exception as e:
        print(f"❌ Validation failed: {str(e)}")
        return {
            'is_valid': False,
            'errors': [f"Validation error: {str(e)}"],
            'warnings': [],
            'node_count': len(ivr_flow)
        }

# Utility functions for integration
def check_system_status() -> Dict[str, Any]:
    """Check the status of the IVR conversion system"""
    status = {
        'enhanced_mapping_available': ENHANCED_MODE_AVAILABLE,
        'basic_converter_available': BASIC_CONVERTER_AVAILABLE,
        'csv_database_found': os.path.exists("cf_general_structure.csv"),
        'system_ready': False,
        'recommended_setup': []
    }
    
    # Determine system readiness
    if ENHANCED_MODE_AVAILABLE or BASIC_CONVERTER_AVAILABLE:
        status['system_ready'] = True
    
    # Generate recommendations
    if not status['enhanced_mapping_available']:
        status['recommended_setup'].append("Install segment_analyzer.py and enhanced_ivr_converter.py for intelligent mapping")
    
    if not status['csv_database_found']:
        status['recommended_setup'].append("Add cf_general_structure.csv with audio transcription data")
    
    if not status['basic_converter_available']:
        status['recommended_setup'].append("Ensure mermaid_ivr_converter.py is available as fallback")
    
    return status

def setup_intelligent_conversion(csv_file_path: str) -> bool:
    """
    Setup intelligent conversion with a specific CSV file
    
    Args:
        csv_file_path: Path to the audio database CSV
    
    Returns:
        True if setup successful, False otherwise
    """
    try:
        if not os.path.exists(csv_file_path):
            print(f"❌ CSV file not found: {csv_file_path}")
            return False
        
        # Test the converter
        converter = IntelligentMermaidIVRConverter(csv_file_path)
        
        # Test with a simple diagram
        test_mermaid = 'flowchart TD\nA["Test"] --> B["End"]'
        ivr_flow, notes = converter.convert(test_mermaid)
        
        if ivr_flow:
            print(f"✅ Intelligent conversion setup successful")
            print(f"   Mode: {'Enhanced' if converter.enhanced_available else 'Basic'}")
            print(f"   CSV: {csv_file_path}")
            return True
        else:
            print(f"❌ Setup test failed")
            return False
            
    except Exception as e:
        print(f"❌ Setup failed: {str(e)}")
        return False

# Example usage and testing
if __name__ == "__main__":
    print("🧪 Testing Fixed Intelligent Mermaid IVR Converter")
    print("="*60)
    
    # Check system status
    status = check_system_status()
    print("System Status:")
    for key, value in status.items():
        if key != 'recommended_setup':
            icon = "✅" if value else "❌"
            print(f"  {icon} {key.replace('_', ' ').title()}: {value}")
    
    if status['recommended_setup']:
        print("\nRecommendations:")
        for rec in status['recommended_setup']:
            print(f"  💡 {rec}")
    
    # Test conversion
    print(f"\n🧪 Testing Conversion:")
    test_mermaid = '''flowchart TD
    A["Welcome<br/>This is an electric callout from North Dayton.<br/>Press 1 if this is employee."] -->|"1"| B{"Employee?"}
    A -->|"9"| A
    B -->|"yes"| C["Enter PIN"]
    B -->|"no"| D["Invalid Entry"]
    '''
    
    try:
        ivr_flow, notes = convert_mermaid_to_ivr(test_mermaid, company='dpl')
        print(f"✅ Conversion successful!")
        print(f"   Nodes generated: {len(ivr_flow)}")
        print(f"   Notes: {len(notes)}")
        
        if notes:
            print("   Notes found:")
            for note in notes[:3]:  # Show first 3 notes
                print(f"     • {note}")
        
        # Test validation
        validation = validate_ivr_configuration(ivr_flow)
        if validation['is_valid']:
            print(f"✅ Generated IVR is valid")
        else:
            print(f"⚠️ Validation issues found: {len(validation['errors'])}")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
    
    print(f"\n🎯 Integration Notes:")
    print(f"   • This version handles missing components gracefully")
    print(f"   • Works with or without enhanced mapping")
    print(f"   • Provides multiple fallback levels")
    print(f"   • Ready for Streamlit Cloud deployment")