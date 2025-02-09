"""
Enhanced IVR transformation module with state tracking
"""
from typing import Dict, List, Optional, Any
import re
import logging
from dataclasses import dataclass, field
from parse_mermaid import Node, Edge, NodeType

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@dataclass
class AudioPrompt:
    """Audio prompt configuration"""
    id: str
    description: str
    patterns: List[str]

class AudioPrompts:
    """Audio prompt mapping"""
    # System prompts
    WELCOME = AudioPrompt("1001", "Welcome message", ["welcome", "start"])
    PIN_ENTRY = AudioPrompt("1008", "PIN entry", ["pin", "enter your"])
    INVALID = AudioPrompt("1009", "Invalid input", ["invalid", "try again"])
    TIMEOUT = AudioPrompt("1010", "Timeout message", ["timeout"])
    ERROR = AudioPrompt("1351", "Error message", ["error"])
    
    # Response prompts
    ACCEPT = AudioPrompt("1167", "Accept response", ["accepted", "accept"])
    DECLINE = AudioPrompt("1021", "Decline response", ["decline", "declined"])
    QUALIFIED = AudioPrompt("1266", "Qualified no", ["qualified no", "qualified 'no'"])
    GOODBYE = AudioPrompt("1029", "Goodbye message", ["goodbye", "end"])
    
    # Callout prompts
    CALLOUT = AudioPrompt("1274", "Callout information", ["callout", "electric callout"])
    REASON = AudioPrompt("1019", "Callout reason", ["reason"])
    LOCATION = AudioPrompt("1232", "Location information", ["location", "trouble location"])
    WAIT = AudioPrompt("1265", "Wait message", ["30-second", "wait"])
    NOT_HOME = AudioPrompt("1017", "Not home message", ["not home"])
    AVAILABLE = AudioPrompt("1316", "Availability check", ["available"])

    @classmethod
    def find_prompt(cls, text: str) -> Optional[str]:
        """Find matching audio prompt for text"""
        text_lower = text.lower()
        for attr_name in dir(cls):
            if not attr_name.startswith('_'):
                prompt = getattr(cls, attr_name)
                if isinstance(prompt, AudioPrompt):
                    if any(pattern in text_lower for pattern in prompt.patterns):
                        return f"callflow:{prompt.id}"
        return None

@dataclass
class IVRState:
    """IVR state tracking"""
    current_node: Optional[str] = None
    processed_nodes: set = field(default_factory=set)
    goto_map: Dict[str, str] = field(default_factory=dict)
    branch_map: Dict[str, Dict] = field(default_factory=dict)

class IVRTransformer:
    """Enhanced IVR transformer with state tracking"""
    
    def __init__(self):
        self.state = IVRState()
        self.node_map = {}
        self.nodes = []

    def transform(self, graph: Dict) -> List[Dict[str, Any]]:
        """Transform Mermaid graph to IVR nodes"""
        try:
            self.nodes = []
            self.state = IVRState()
            
            # Process nodes
            nodes_dict = graph['nodes']
            edges = graph['edges']
            
            # Build node relationships
            self.node_map = self._build_node_map(nodes_dict, edges)
            
            # Start with welcome/initial node
            start_node = self._find_start_node(nodes_dict)
            if start_node:
                self._process_flow(start_node, edges)
            
            # Process any remaining nodes
            for node_id, node in nodes_dict.items():
                if node_id not in self.state.processed_nodes:
                    self._process_node(node, edges)
            
            # Add standard handlers if not present
            if not any(node.get('label') == 'Problems' for node in self.nodes):
                self.nodes.append(self._create_error_handler())
            if not any(node.get('label') == 'Goodbye' for node in self.nodes):
                self.nodes.append(self._create_goodbye_handler())
            
            return self.nodes
            
        except Exception as e:
            logger.error(f"Transform error: {str(e)}")
            return [self._create_error_handler()]
    
    def _find_start_node(self, nodes: Dict[str, Node]) -> Optional[Node]:
        """Find the starting node of the flow"""
        for node in nodes.values():
            if ("welcome" in node.raw_text.lower() or 
                "start" in node.raw_text.lower() or
                "this is an electric callout" in node.raw_text.lower()):
                return node
        return next(iter(nodes.values())) if nodes else None

    def _process_flow(self, node: Node, edges: List[Edge]):
        """Process flow starting from a node"""
        if node.id in self.state.processed_nodes:
            return
            
        self.state.processed_nodes.add(node.id)
        node_config = self._create_node_config(node, edges)
        
        if node_config:
            self.nodes.append(node_config)
            logger.debug(f"Added node: {node_config['label']}")
            
            # Process outgoing edges
            out_edges = [e for e in edges if e.from_id == node.id]
            for edge in out_edges:
                if edge.to_id not in self.state.processed_nodes:
                    next_node = self.node_map[edge.to_id]['node']
                    self._process_flow(next_node, edges)

    def _create_node_config(self, node: Node, edges: List[Edge]) -> Dict:
        """Create IVR node configuration"""
        config = {
            "label": self._format_label(node.id),
            "log": node.raw_text
        }
        
        # Handle node types
        if node.node_type == NodeType.RHOMBUS:
            self._handle_decision_config(config, node, edges)
        else:
            self._handle_action_config(config, node, edges)
            
        return config

    def _handle_decision_config(self, config: Dict, node: Node, edges: List[Edge]):
        """Handle decision node configuration"""
        out_edges = [e for e in edges if e.from_id == node.id]
        
        config["getDigits"] = {
            "numDigits": 1,
            "maxTries": 3,
            "timeout": 5,
            "errorPrompt": "callflow:1009",
            "timeoutPrompt": "callflow:1010"
        }
        
        branches = {}
        valid_choices = []
        
        for edge in out_edges:
            if edge.label:
                # Extract digit from label
                digit_match = re.search(r'(\d+)(?:\s*-\s*|\s+)(.+)', edge.label)
                if digit_match:
                    digit, action = digit_match.groups()
                    branches[digit] = self._format_label(edge.to_id)
                    valid_choices.append(digit)
                # Handle retry/error cases
                elif any(x in edge.label.lower() for x in ['retry', 'invalid', 'no input']):
                    branches["error"] = self._format_label(edge.to_id)
                    branches["timeout"] = self._format_label(edge.to_id)
                # Handle yes/no cases
                elif edge.label.lower() == "yes":
                    branches["1"] = self._format_label(edge.to_id)
                    valid_choices.append("1")
                elif edge.label.lower() == "no":
                    branches["2"] = self._format_label(edge.to_id)
                    valid_choices.append("2")
        
        if valid_choices:
            config["getDigits"]["validChoices"] = "|".join(valid_choices)
        if branches:
            config["branch"] = branches

    def _handle_action_config(self, config: Dict, node: Node, edges: List[Edge]):
        """Handle action node configuration"""
        # Find matching audio prompt
        prompt_id = AudioPrompts.find_prompt(node.raw_text)
        if prompt_id:
            config["playPrompt"] = [prompt_id]
        else:
            config["playPrompt"] = ["tts:" + node.raw_text]
        
        # Add goto for single outgoing edge
        out_edges = [e for e in edges if e.from_id == node.id]
        if len(out_edges) == 1:
            config["goto"] = self._format_label(out_edges[0].to_id)
        
        # Add special flags
        text_lower = node.raw_text.lower()
        if any(x in text_lower for x in ['goodbye', 'thank you', 'recorded', 'message']):
            config["nobarge"] = "1"
        
        # Handle response types
        if "accept" in text_lower:
            config["gosub"] = ["SaveCallResult", 1001, "Accept"]
        elif "decline" in text_lower:
            config["gosub"] = ["SaveCallResult", 1002, "Decline"]
        elif "qualified no" in text_lower:
            config["gosub"] = ["SaveCallResult", 1145, "QualNo"]
        elif "not home" in text_lower:
            config["gosub"] = ["SaveCallResult", 1006, "NotHome"]

    def _build_node_map(self, nodes: Dict[str, Node], edges: List[Edge]) -> Dict:
        """Build node relationship map"""
        return {node_id: {
            'node': node,
            'outgoing': [e for e in edges if e.from_id == node_id],
            'incoming': [e for e in edges if e.to_id == node_id]
        } for node_id, node in nodes.items()}

    def _create_error_handler(self) -> Dict:
        """Create standard error handler"""
        return {
            "label": "Problems",
            "log": "Error handler",
            "playPrompt": ["callflow:1351"],
            "goto": "Goodbye"
        }

    def _create_goodbye_handler(self) -> Dict:
        """Create standard goodbye handler"""
        return {
            "label": "Goodbye",
            "log": "Call completion",
            "playPrompt": ["callflow:1029"],
            "nobarge": "1",
            "goto": "Disconnect"
        }

    @staticmethod
    def _format_label(node_id: str) -> str:
        """Format node ID into label"""
        words = re.findall(r'[A-Z][a-z]*|[a-z]+|\d+', node_id)
        return ''.join(word.capitalize() for word in words)

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """Convert Mermaid graph to IVR configuration"""
    transformer = IVRTransformer()
    return transformer.transform(graph)