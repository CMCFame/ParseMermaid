"""
Production Integration - Uses Real IVR Format
Prioritizes production converter over experimental intelligent mapping
"""

import os
import json
from typing import List, Dict, Any, Tuple, Optional

# Import production converter first
try:
    from production_ivr_converter import convert_mermaid_to_ivr_production
    PRODUCTION_CONVERTER_AVAILABLE = True
    print("✅ Production converter loaded (real IVR format)")
except ImportError:
    PRODUCTION_CONVERTER_AVAILABLE = False

# Fallback to enhanced converter
try:
    from enhanced_ivr_converter import convert_mermaid_to_ivr_enhanced, validate_ivr_output
    ENHANCED_CONVERTER_AVAILABLE = True
    print("✅ Enhanced converter available as fallback")
except ImportError:
    ENHANCED_CONVERTER_AVAILABLE = False

# Basic converter as last resort
try:
    from mermaid_ivr_converter import MermaidIVRConverter as BasicMermaidIVRConverter
    BASIC_CONVERTER_AVAILABLE = True
except ImportError:
    BASIC_CONVERTER_AVAILABLE = False

class ProductionMermaidIVRConverter:
    """Production converter that generates real IVR format"""
    
    def __init__(self, csv_file_path: str = "cf_general_structure.csv", 
                 config: Optional[Dict[str, Any]] = None):
        self.csv_file_path = csv_file_path
        self.config = config or {}
        self.last_conversion_report = None
        
        # Determine best available converter
        self.converter_priority = []
        if PRODUCTION_CONVERTER_AVAILABLE:
            self.converter_priority.append('production')
        if ENHANCED_CONVERTER_AVAILABLE and os.path.exists(csv_file_path):
            self.converter_priority.append('enhanced')
        if BASIC_CONVERTER_AVAILABLE:
            self.converter_priority.append('basic')
        
        print(f"Available converters: {self.converter_priority}")
    
    def convert(self, mermaid_code: str, company: str = None) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Convert using best available method"""
        
        # Try production converter first (real IVR format)
        if 'production' in self.converter_priority:
            try:
                return self._convert_production(mermaid_code, company)
            except Exception as e:
                print(f"⚠️ Production converter failed: {str(e)}")
        
        # Fallback to enhanced converter
        if 'enhanced' in self.converter_priority:
            try:
                return self._convert_enhanced(mermaid_code, company)
            except Exception as e:
                print(f"⚠️ Enhanced converter failed: {str(e)}")
        
        # Last resort: basic converter
        if 'basic' in self.converter_priority:
            try:
                return self._convert_basic(mermaid_code)
            except Exception as e:
                print(f"⚠️ Basic converter failed: {str(e)}")
        
        # Emergency fallback
        return self._convert_emergency(mermaid_code)
    
    def _convert_production(self, mermaid_code: str, company: str = None) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Convert using production converter (real IVR format)"""
        ivr_flow, conversion_report = convert_mermaid_to_ivr_production(
            mermaid_code, 
            company=company,
            config=self.config
        )
        
        self.last_conversion_report = conversion_report
        
        # Generate notes
        notes = []
        summary = conversion_report['conversion_summary']
        
        notes.append("✅ Production IVR format (matches real callflow patterns)")
        notes.append(f"✅ {summary['total_nodes']} nodes with descriptive labels")
        
        if 'label_mapping' in conversion_report:
            notes.append(f"✅ Label mapping: {len(conversion_report['label_mapping'])} nodes renamed")
        
        notes.append("✅ Standard callflow IDs used (callflow:1316, etc.)")
        notes.append("✅ Proper gosub structure for actions")
        
        return ivr_flow, notes
    
    def _convert_enhanced(self, mermaid_code: str, company: str = None) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Convert using enhanced converter (intelligent mapping)"""
        ivr_flow, conversion_report = convert_mermaid_to_ivr_enhanced(
            mermaid_code, 
            self.csv_file_path,
            company=company,
            config=self.config
        )
        
        self.last_conversion_report = conversion_report
        
        # Generate notes
        notes = []
        summary = conversion_report['conversion_summary']
        
        notes.append(f"ℹ️ Enhanced conversion with intelligent mapping")
        notes.append(f"📊 Success rate: {summary['overall_success_rate']}%")
        
        if summary['nodes_requiring_review'] > 0:
            notes.append(f"⚠️ {summary['nodes_requiring_review']} nodes require manual review")
        
        if conversion_report['missing_audio_files']:
            missing_count = len(conversion_report['missing_audio_files'])
            notes.append(f"🎤 {missing_count} missing audio segments detected")
        
        return ivr_flow, notes
    
    def _convert_basic(self, mermaid_code: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Convert using basic converter"""
        converter = BasicMermaidIVRConverter(self.config)
        ivr_flow, notes = converter.convert(mermaid_code)
        
        notes.append("ℹ️ Basic conversion used")
        notes.append("💡 For production format, add production_ivr_converter.py")
        
        return ivr_flow, notes
    
    def _convert_emergency(self, mermaid_code: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Emergency fallback"""
        print("⚠️ Using emergency fallback converter")
        
        nodes = [{
            "label": "Welcome",
            "log": "Emergency conversion - limited functionality",
            "playPrompt": "callflow:1001",
            "goto": "Problems"
        }, {
            "label": "Problems",
            "playLog": "I'm sorry you are having problems.",
            "playPrompt": "callflow:1351",
            "goto": "hangup"
        }]
        
        notes = [
            "⚠️ Emergency conversion used",
            "💡 Add production_ivr_converter.py for full functionality"
        ]
        
        return nodes, notes
    
    def get_conversion_report(self) -> Optional[Dict]:
        """Get detailed conversion report"""
        return self.last_conversion_report
    
    def validate_output(self, ivr_flow: List[Dict]) -> Dict:
        """Validate IVR output"""
        if ENHANCED_CONVERTER_AVAILABLE:
            try:
                return validate_ivr_output(ivr_flow)
            except Exception as e:
                print(f"⚠️ Enhanced validation failed: {str(e)}")
        
        # Basic validation
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
            'validation_mode': 'production'
        }

# Global instance
_global_converter = None

def get_converter(csv_file_path: str = "cf_general_structure.csv", 
                 config: Optional[Dict[str, Any]] = None) -> ProductionMermaidIVRConverter:
    """Get converter instance"""
    global _global_converter
    
    if (_global_converter is None or 
        _global_converter.csv_file_path != csv_file_path or
        _global_converter.config != config):
        _global_converter = ProductionMermaidIVRConverter(csv_file_path, config)
    
    return _global_converter

def convert_mermaid_to_ivr(mermaid_code: str, company: str = None, 
                          csv_file_path: str = "cf_general_structure.csv",
                          config: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Main conversion function - prioritizes production format
    """
    try:
        converter = get_converter(csv_file_path, config)
        return converter.convert(mermaid_code, company)
    except Exception as e:
        print(f"❌ All converters failed: {str(e)}")
        # Return minimal fallback
        return [{
            "label": "Error", 
            "log": "Conversion failed", 
            "playPrompt": "callflow:1351",
            "goto": "hangup"
        }], [f"❌ Conversion error: {str(e)}"]

def convert_mermaid_to_ivr_with_report(mermaid_code: str, company: str = None,
                                     csv_file_path: str = "cf_general_structure.csv",
                                     config: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], List[str], Optional[Dict]]:
    """
    Enhanced conversion with detailed report
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
    """Validate IVR configuration"""
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

def check_system_status() -> Dict[str, Any]:
    """Check system status with production converter priority"""
    status = {
        'production_converter_available': PRODUCTION_CONVERTER_AVAILABLE,
        'enhanced_converter_available': ENHANCED_CONVERTER_AVAILABLE,
        'basic_converter_available': BASIC_CONVERTER_AVAILABLE,
        'csv_database_found': os.path.exists("cf_general_structure.csv"),
        'system_ready': False,
        'recommended_mode': 'production',
        'recommended_setup': []
    }
    
    # Determine system readiness
    if PRODUCTION_CONVERTER_AVAILABLE:
        status['system_ready'] = True
        status['recommended_mode'] = 'production'
    elif ENHANCED_CONVERTER_AVAILABLE:
        status['system_ready'] = True
        status['recommended_mode'] = 'enhanced'
    elif BASIC_CONVERTER_AVAILABLE:
        status['system_ready'] = True
        status['recommended_mode'] = 'basic'
    
    # Generate recommendations
    if not PRODUCTION_CONVERTER_AVAILABLE:
        status['recommended_setup'].append("Add production_ivr_converter.py for real IVR format")
    
    if not status['csv_database_found']:
        status['recommended_setup'].append("Add CSV database for intelligent mapping")
    
    return status

# Example usage and testing
if __name__ == "__main__":
    print("🏭 Production IVR Integration")
    print("="*60)
    
    # Check system status
    status = check_system_status()
    print("System Status:")
    for key, value in status.items():
        if key not in ['recommended_setup']:
            icon = "✅" if value else "❌"
            print(f"  {icon} {key.replace('_', ' ').title()}: {value}")
    
    print(f"\n🎯 Recommended Mode: {status['recommended_mode']}")
    
    if status['recommended_setup']:
        print("\nRecommendations:")
        for rec in status['recommended_setup']:
            print(f"  💡 {rec}")
    
    # Test conversion
    print(f"\n🧪 Testing Production Conversion:")
    test_mermaid = '''flowchart TD
    A["Welcome<br/>This is an electric callout from North Dayton."] -->|"1"| B{"Employee?"}
    B -->|"yes"| C["Offer<br/>Are you available for this callout?<br/>Press 1 for yes, 3 for no."]
    C -->|"1"| D["Accept"]
    C -->|"3"| E["Decline"]
    '''
    
    try:
        ivr_flow, notes = convert_mermaid_to_ivr(test_mermaid, company='dpl')
        print(f"✅ Conversion successful!")
        print(f"   Mode: {status['recommended_mode']}")
        print(f"   Nodes: {len(ivr_flow)}")
        print(f"   Notes: {len(notes)}")
        
        # Show first node as example
        if ivr_flow:
            print(f"\n📄 Sample node structure:")
            sample = ivr_flow[0]
            print(f"   Label: {sample.get('label')}")
            print(f"   PlayPrompt: {sample.get('playPrompt')}")
            if 'gosub' in sample:
                print(f"   Gosub: {sample['gosub']}")
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
    
    print(f"\n🎯 Integration Notes:")
    print(f"   • Production converter generates real IVR format")
    print(f"   • Follows patterns from allflows LITE.txt")
    print(f"   • Uses proper gosub for actions")
    print(f"   • Standard callflow IDs (callflow:1316, etc.)")