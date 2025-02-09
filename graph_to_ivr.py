"""
Enhanced IVR transformation module with complete state and prompt handling
"""
import re
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from parse_mermaid import Node, Edge, NodeType

class PromptType(Enum):
    """Types of IVR prompts"""
    WELCOME = auto()
    MENU = auto()
    INPUT = auto()
    ERROR = auto()
    RESPONSE = auto()
    TRANSFER = auto()
    CUSTOM = auto()

@dataclass
class AudioPrompt:
    """Structured audio prompt configuration"""
    id: str
    description: str
    category: PromptType
    text: Optional[str] = None
    variables: List[str] = field(default_factory=list)

class AudioPromptLibrary:
    """Comprehensive IVR audio prompt mapping"""
    
    PROMPTS = {
        # System prompts
        "welcome": AudioPrompt("1001", "Welcome message", PromptType.WELCOME),
        "pin_entry": AudioPrompt("1008", "PIN entry request", PromptType.INPUT),
        "invalid_input": AudioPrompt("1009", "Invalid input", PromptType.ERROR),
        "timeout": AudioPrompt("1010", "Input timeout", PromptType.ERROR),
        "error": AudioPrompt("1351", "General error", PromptType.ERROR),
        
        # Response prompts
        "accept": AudioPrompt("1167", "Accept response", PromptType.RESPONSE),
        "decline": AudioPrompt("1021", "Decline response", PromptType.RESPONSE),
        "qualified_no": AudioPrompt("1266", "Qualified no", PromptType.RESPONSE),
        
        # Menu prompts
        "main_menu": AudioPrompt("1677", "Main menu options", PromptType.MENU),
        "transfer": AudioPrompt("1645", "Transfer request", PromptType.TRANSFER),
        "goodbye": AudioPrompt("1029", "Goodbye message", PromptType.RESPONSE),
        
        # Callout prompts
        "callout": AudioPrompt("1274", "Callout information", PromptType.MENU),
        "location": AudioPrompt("1232", "Location information", PromptType.MENU),
        "reason": AudioPrompt("1019", "Callout reason", PromptType.MENU),
        
        # Custom messages
        "custom": AudioPrompt("2000", "Custom message", PromptType.CUSTOM)
    }
    
    @classmethod
    def get_prompt(cls, key: str) -> str:
        """Get prompt ID by key"""
        return f"callflow:{cls.PROMPTS.get(key, cls.PROMPTS['custom']).id}"

@dataclass
class IVRState:
    """Represents an IVR call state"""
    label: str
    prompt_id: str
    description: str
    next_states: List[str] = field(default_factory=list)
    input_required: bool = False
    max_retries: int = 3
    timeout: int = 5
    branch_logic: Dict[str, str] = field(default_factory=dict)

class IVRTransformer:
    """Enhanced IVR transformation engine"""
    
    def __init__(self):
        self.audio_library = AudioPromptLibrary()
        self.processed_nodes: Set[str] = set()
        self.node_map: Dict[str, Dict] = {}
        self.current_state: Optional[IVRState] = None
    
    def transform(self, graph: Dict) -> List[Dict[str, Any]]:
        """
        Transform Mermaid graph into IVR configuration
        
        Args:
            graph: Parsed Mermaid graph structure
            
        Returns:
            List of IVR node configurations
        """
        try:
            nodes = graph['nodes']
            edges = graph['edges']
            
            # Reset state
            self.processed_nodes.clear()
            self.node_map = self._build_node_map(nodes, edges)
            
            # Generate IVR nodes
            ivr_nodes = []
            
            # Start with entry points
            entry_nodes = [n for n in nodes.values() if n.node_type == NodeType.START]
            if not entry_nodes:
                ivr_nodes.append(self._create_default_entry())
            
            # Process all nodes
            for node_id, node in nodes.items():
                if node_id not in self.processed_nodes:
                    ivr_node = self._transform_node(node)
                    if ivr_node:
                        ivr_nodes.append(ivr_node)
                        self.processed_nodes.add(node_id)
            
            # Add standard handlers
            ivr_nodes.extend(self._create_standard_handlers())
            
            return ivr_nodes
            
        except Exception as e:
            raise RuntimeError(f"IVR transformation failed: {str(e)}")

    def _build_node_map(self, nodes: Dict[str, Node], edges: List[Edge]) -> Dict:
        """Build node relationship map"""
        node_map = {}
        for node_id, node in nodes.items():
            outgoing = [e for e in edges if e.from_id == node_id]
            incoming = [e for e in edges if e.to_id == node_id]
            node_map[node_id] = {
                'node': node,
                'outgoing': outgoing,
                'incoming': incoming
            }
        return node_map

    def _transform_node(self, node: Node) -> Optional[Dict]:
        """Transform individual node based on type and context"""
        try:
            base_config = {
                'label': self._format_label(node.raw_text),
                'log': node.raw_text
            }

            if node.node_type == NodeType.START:
                return self._handle_start_node(base_config)
            elif node.node_type == NodeType.DECISION:
                return self._handle_decision_node(base_config, node)
            elif "PIN" in node.raw_text:
                return self._handle_pin_node(base_config)
            elif "Available" in node.raw_text:
                return self._handle_availability_node(base_config)
            elif any(x in node.raw_text for x in ["Accept", "Decline", "Qualified"]):
                return self._handle_response_node(base_config, node)
            elif "Goodbye" in node.raw_text:
                return self._handle_goodbye_node(base_config)
            elif "Error" in node.raw_text or "Invalid" in node.raw_text:
                return self._handle_error_node(base_config)
            else:
                return self._handle_message_node(base_config, node)
                
        except Exception as e:
            raise ValueError(f"Node transformation failed for {node.id}: {str(e)}")

    def _handle_start_node(self, base_config: Dict) -> Dict:
        """Handle initial welcome/start node"""
        base_config.update({
            'playPrompt': [self.audio_library.get_prompt('welcome')],
            'getDigits': {
                'numDigits': 1,
                'maxTries': 3,
                'validChoices': "1|3|7|9",
                'timeout': 5,
                'errorPrompt': self.audio_library.get_prompt('invalid_input'),
                'timeoutPrompt': self.audio_library.get_prompt('timeout')
            }
        })
        return base_config

    def _handle_decision_node(self, base_config: Dict, node: Node) -> Dict:
        """Handle decision/menu nodes"""
        outgoing = self.node_map[node.id]['outgoing']
        branches = {}
        valid_choices = []
        
        for edge in outgoing:
            if edge.label:
                digit_match = re.search(r'(\d+)', edge.label)
                if digit_match:
                    digit = digit_match.group(1)
                    valid_choices.append(digit)
                    branches[digit] = self._format_label(
                        self.node_map[edge.to_id]['node'].raw_text
                    )

        base_config.update({
            'getDigits': {
                'numDigits': 1,
                'maxTries': 3,
                'validChoices': "|".join(valid_choices),
                'timeout': 5,
                'errorPrompt': self.audio_library.get_prompt('invalid_input'),
                'timeoutPrompt': self.audio_library.get_prompt('timeout')
            },
            'branch': branches
        })
        return base_config

    def _handle_pin_node(self, base_config: Dict) -> Dict:
        """Handle PIN entry nodes"""
        base_config.update({
            'playPrompt': [self.audio_library.get_prompt('pin_entry')],
            'getDigits': {
                'numDigits': 4,
                'maxTries': 3,
                'terminator': '#',
                'timeout': 10,
                'errorPrompt': self.audio_library.get_prompt('invalid_input'),
                'timeoutPrompt': self.audio_library.get_prompt('timeout')
            }
        })
        return base_config

    def _handle_availability_node(self, base_config: Dict) -> Dict:
        """Handle availability check nodes"""
        base_config.update({
            'playPrompt': [self.audio_library.get_prompt('callout')],
            'getDigits': {
                'numDigits': 1,
                'maxTries': 3,
                'validChoices': "1|3|9",
                'timeout': 5,
                'errorPrompt': self.audio_library.get_prompt('invalid_input'),
                'timeoutPrompt': self.audio_library.get_prompt('timeout')
            },
            'branch': {
                '1': 'AcceptedResponse',
                '3': 'CalloutDecline',
                '9': 'QualifiedNo'
            }
        })
        return base_config

    def _handle_response_node(self, base_config: Dict, node: Node) -> Dict:
        """Handle response recording nodes"""
        if "Accept" in node.raw_text:
            prompt_key = 'accept'
        elif "Decline" in node.raw_text:
            prompt_key = 'decline'
        elif "Qualified" in node.raw_text:
            prompt_key = 'qualified_no'
        else:
            prompt_key = 'custom'
        
        base_config.update({
            'playPrompt': [self.audio_library.get_prompt(prompt_key)],
            'goto': 'Goodbye'
        })
        return base_config

    def _handle_goodbye_node(self, base_config: Dict) -> Dict:
        """Handle goodbye/exit nodes"""
        base_config.update({
            'playPrompt': [self.audio_library.get_prompt('goodbye')],
            'goto': 'Disconnect'
        })
        return base_config

    def _handle_error_node(self, base_config: Dict) -> Dict:
        """Handle error and retry nodes"""
        base_config.update({
            'playPrompt': [self.audio_library.get_prompt('error')],
            'maxRetries': 3
        })
        return base_config

    def _handle_message_node(self, base_config: Dict, node: Node) -> Dict:
        """Handle general message nodes"""
        if "custom" in node.raw_text.lower():
            prompt_key = 'custom'
        else:
            prompt_key = self._determine_prompt_key(node.raw_text)
        
        base_config.update({
            'playPrompt': [self.audio_library.get_prompt(prompt_key)]
        })
        
        # Add next state if there's a single outgoing edge
        outgoing = self.node_map[node.id]['outgoing']
        if len(outgoing) == 1:
            base_config['goto'] = self._format_label(
                self.node_map[outgoing[0].to_id]['node'].raw_text
            )
            
        return base_config

    def _create_default_entry(self) -> Dict:
        """Create default entry point"""
        return {
            'label': 'Start',
            'log': 'Call flow entry point',
            'playPrompt': [self.audio_library.get_prompt('welcome')]
        }

    def _create_standard_handlers(self) -> List[Dict]:
        """Create standard error and exit handlers"""
        handlers = []
        
        # Error handler
        handlers.append({
            'label': 'Problems',
            'log': 'Error handler',
            'playPrompt': [self.audio_library.get_prompt('error')],
            'goto': 'Goodbye'
        })
        
        # Standard goodbye
        handlers.append({
            'label': 'Goodbye',
            'log': 'Call completion',
            'playPrompt': [self.audio_library.get_prompt('goodbye')],
            'goto': 'Disconnect'
        })
        
        return handlers

    @staticmethod
    def _format_label(text: str) -> str:
        """Format text into a valid IVR label"""
        # Remove special characters and convert to title case
        cleaned = re.sub(r'[^\w\s-]', '', text)
        words = cleaned.split()
        if not words:
            return "Unknown"
        return ''.join(word.capitalize() for word in words)

    def _determine_prompt_key(self, text: str) -> str:
        """Determine appropriate prompt key based on text content"""
        text_lower = text.lower()
        
        # Map common text patterns to prompt keys
        prompt_patterns = {
            'welcome': ['welcome', 'hello', 'greeting'],
            'callout': ['callout', 'dispatch'],
            'location': ['location', 'trouble'],
            'reason': ['reason', 'cause'],
            'transfer': ['transfer', 'forward'],
            'goodbye': ['goodbye', 'end', 'disconnect']
        }
        
        for key, patterns in prompt_patterns.items():
            if any(pattern in text_lower for pattern in patterns):
                return key
        
        return 'custom'

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """Convert Mermaid graph to IVR configuration"""
    transformer = IVRTransformer()
    return transformer.transform(graph)