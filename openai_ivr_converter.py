"""
Enhanced OpenAI-powered IVR conversion with improved prompt engineering and pattern matching
"""
from typing import Dict, List, Any, Optional
from openai import OpenAI
import json
import logging
import traceback
import re
import copy
from parse_mermaid import MermaidParser, NodeType

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class IVRFlowTemplate:
    """Templates for IVR flow conversion"""
    
    NODE_PATTERNS = {
        'WELCOME': {
            'detect': r'welcome|start|begin',
            'template': {
                'label': 'Welcome',
                'playPrompt': ['callflow:1001'],
                'log': 'Initial greeting'
            }
        },
        'PIN_ENTRY': {
            'detect': r'input|enter\s+digits|pin',
            'template': {
                'label': 'GetPin',
                'playPrompt': ['callflow:1008'],
                'getDigits': {
                    'numDigits': 4,
                    'maxTries': 3,
                    'errorPrompt': 'callflow:1009',
                    'timeoutPrompt': 'callflow:1010'
                }
            }
        },
        'DECISION': {
            'detect': r'(yes|no|press|option|invalid|retry)',
            'template': {
                'label': 'MenuChoice',
                'getDigits': {
                    'numDigits': 1,
                    'maxTries': 3,
                    'validChoices': None,  # To be filled based on edges
                    'errorPrompt': 'callflow:1009'
                }
            }
        },
        'TRANSFER': {
            'detect': r'transfer|connect|forward',
            'template': {
                'label': 'Transfer',
                'setvar': {
                    'transfer_ringback': 'callflow:2223'
                },
                'gosub': 'XferCall'
            }
        },
        'ERROR': {
            'detect': r'error|invalid|failed',
            'template': {
                'label': 'ErrorHandler',
                'playPrompt': ['callflow:1351'],
                'goto': 'MainMenu'
            }
        }
    }

    EDGE_PATTERNS = {
        'DTMF': r'(\d+)\s*-\s*([^"]+)',  # Matches "1 - accept", "2 - decline", etc.
        'YES_NO': r'(yes|no)\s*-?\s*([^"]+)',  # Matches "yes - continue", "no - exit"
        'RETRY': r'(retry|invalid|timeout)',  # Matches retry conditions
        'ERROR': r'(error|failed|invalid)'  # Matches error conditions
    }

    @classmethod
    def create_ivr_node(cls, node_id: str, node_text: str, edges: list) -> dict:
        """Create IVR node configuration from Mermaid node and edges"""
        
        # Determine node type and base template
        node_type = None
        for type_name, pattern in cls.NODE_PATTERNS.items():
            if re.search(pattern['detect'], node_text.lower()):
                node_type = type_name
                template = copy.deepcopy(pattern['template'])
                break
        
        if not node_type:
            # Default to menu node if type can't be determined
            template = copy.deepcopy(cls.NODE_PATTERNS['DECISION']['template'])
        
        # Add node identification
        template['id'] = node_id
        template['log'] = node_text
        
        # Process edges to determine branch logic
        template['branch'] = cls._process_edges(edges)
        
        # Add appropriate playPrompt if missing
        if 'playPrompt' not in template:
            template['playPrompt'] = [f'callflow:{cls._get_prompt_id(node_text)}']
        
        # Update template based on specific node content
        cls._customize_template(template, node_text, edges)
        
        return template

    @classmethod
    def _process_edges(cls, edges: list) -> dict:
        """Process edges to create branch logic"""
        branch = {}
        
        for edge in edges:
            edge_text = edge.get('label', '')
            
            # Check for DTMF pattern
            dtmf_match = re.search(cls.EDGE_PATTERNS['DTMF'], edge_text)
            if dtmf_match:
                key = dtmf_match.group(1)
                branch[key] = edge['to_id']
                continue
            
            # Check for Yes/No pattern
            yes_no_match = re.search(cls.EDGE_PATTERNS['YES_NO'], edge_text)
            if yes_no_match:
                key = '1' if yes_no_match.group(1).lower() == 'yes' else '2'
                branch[key] = edge['to_id']
                continue
            
            # Check for retry/error conditions
            if re.search(cls.EDGE_PATTERNS['RETRY'], edge_text):
                branch['retry'] = edge['to_id']
            elif re.search(cls.EDGE_PATTERNS['ERROR'], edge_text):
                branch['error'] = edge['to_id']
        
        # Add default error handling if missing
        if 'error' not in branch:
            branch['error'] = 'ErrorHandler'
        
        return branch

    @classmethod
    def _customize_template(cls, template: dict, node_text: str, edges: list):
        """Customize template based on specific node content"""
        
        # Extract valid choices from edges
        if 'getDigits' in template:
            valid_choices = []
            for edge in edges:
                dtmf_match = re.search(cls.EDGE_PATTERNS['DTMF'], edge.get('label', ''))
                if dtmf_match:
                    valid_choices.append(dtmf_match.group(1))
            
            if valid_choices:
                template['getDigits']['validChoices'] = '|'.join(valid_choices)
        
        # Customize timeouts
        if 'timeout' in node_text.lower():
            template['maxTime'] = 5
        
        # Add retry logic if needed
        retry_edges = [e for e in edges if re.search(cls.EDGE_PATTERNS['RETRY'], e.get('label', ''))]
        if retry_edges:
            template['maxLoop'] = ['RetryLoop', 3, 'ErrorHandler']

    @staticmethod
    def _get_prompt_id(text: str) -> str:
        """Map node text to appropriate prompt ID"""
        text_lower = text.lower()
        
        # Common prompt mappings
        prompts = {
            'welcome': '1001',
            'pin': '1008',
            'error': '1009',
            'timeout': '1010',
            'invalid': '1009',
            'transfer': '2223',
            'goodbye': '1029'
        }
        
        for key, id in prompts.items():
            if key in text_lower:
                return id
        
        # Default prompt if no match found
        return '1001'  # Default welcome prompt

    @classmethod
    def generate_ivr_code(cls, nodes: list, edges: list) -> str:
        """Generate complete IVR code from nodes and edges"""
        ivr_nodes = []
        
        for node in nodes:
            node_edges = [e for e in edges if e['from_id'] == node['id']]
            ivr_node = cls.create_ivr_node(node['id'], node['text'], node_edges)
            ivr_nodes.append(ivr_node)
        
        # Add error handler if not present
        if not any(n.get('label') == 'ErrorHandler' for n in ivr_nodes):
            ivr_nodes.append(cls.NODE_PATTERNS['ERROR']['template'])
        
        return f'module.exports = {json.dumps(ivr_nodes, indent=2)};'

class IVRNodeValidator:
    """Validates IVR node structures"""
    
    REQUIRED_FIELDS = {
        'label': str,
        'log': str
    }
    
    @classmethod
    def validate_node(cls, node: dict) -> bool:
        """Validate node structure"""
        try:
            # Check required fields
            for field, field_type in cls.REQUIRED_FIELDS.items():
                if field not in node:
                    raise ValueError(f"Missing required field: {field}")
                if not isinstance(node[field], field_type):
                    raise ValueError(f"Invalid type for {field}: expected {field_type}")
            
            # Validate getDigits if present
            if 'getDigits' in node:
                cls._validate_get_digits(node['getDigits'])
            
            # Validate playPrompt if present
            if 'playPrompt' in node:
                cls._validate_prompts(node['playPrompt'])
            
            return True
            
        except Exception as e:
            logger.error(f"Node validation failed: {str(e)}")
            raise

    @staticmethod
    def _validate_get_digits(get_digits: dict):
        """Validate getDigits configuration"""
        required = {'numDigits', 'maxTries', 'errorPrompt'}
        if not all(field in get_digits for field in required):
            raise ValueError(f"Invalid getDigits configuration: missing {required - set(get_digits.keys())}")

    @staticmethod
    def _validate_prompts(prompts):
        """Validate prompt IDs"""
        if isinstance(prompts, str):
            prompts = [prompts]
        
        for prompt in prompts:
            if not isinstance(prompt, str) or not prompt.startswith('callflow:'):
                raise ValueError(f"Invalid prompt format: {prompt}")

class OpenAIIVRConverter:
    """Enhanced OpenAI-powered IVR converter with improved template handling"""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OpenAI API key is required")
        self.client = OpenAI(api_key=api_key)
        self.template = IVRFlowTemplate()
        self.validator = IVRNodeValidator()
        logger.info("OpenAI IVR converter initialized")

    def convert_to_ivr(self, mermaid_code: str) -> str:
        """Convert Mermaid diagram to IVR configuration with improved parsing"""
        try:
            # Parse Mermaid code
            parser = MermaidParser()
            parsed = parser.parse(mermaid_code)
            
            # Extract nodes and edges
            nodes = []
            for node_id, node in parsed['nodes'].items():
                nodes.append({
                    'id': node_id,
                    'text': node.raw_text,
                    'type': node.node_type
                })
            
            edges = []
            for edge in parsed['edges']:
                edges.append({
                    'from_id': edge.from_id,
                    'to_id': edge.to_id,
                    'label': edge.label
                })
            
            # Generate IVR code using templates
            ivr_code = self.template.generate_ivr_code(nodes, edges)
            
            # Validate generated code
            self._validate_ivr_code(ivr_code)
            
            return ivr_code
            
        except Exception as e:
            logger.error(f"Conversion failed: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

    def _validate_ivr_code(self, ivr_code: str):
        """Validate generated IVR code structure"""
        try:
            # Extract node array
            nodes_str = ivr_code.split('module.exports = ')[1].rstrip(';')
            nodes = json.loads(nodes_str)
            
            for node in nodes:
                self.validator.validate_node(node)
                
        except Exception as e:
            raise ValueError(f"Invalid IVR code structure: {str(e)}")

def convert_mermaid_to_ivr(mermaid_code: str, api_key: str) -> str:
    """Convenience wrapper for Mermaid to IVR conversion"""
    try:
        converter = OpenAIIVRConverter(api_key)
        return converter.convert_to_ivr(mermaid_code)
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        return '''module.exports = [
    {
        "label": "ErrorHandler",
        "log": "Conversion failed - using error handler",
        "playPrompt": ["callflow:1351"],
        "goto": "Goodbye"
    }
];'''