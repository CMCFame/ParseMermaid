"""
Enhanced IVR transformation module with comprehensive audio mapping and flow control
"""
from typing import Dict, List, Optional, Any, Tuple
import re
from dataclasses import dataclass
from parse_mermaid import Node, Edge, NodeType

@dataclass
class AudioPrompt:
    """Structured audio prompt configuration"""
    id: str
    description: str
    category: str

class AudioPromptLibrary:
    """Comprehensive IVR audio prompt mapping"""
    
    # Standard system prompts
    SYSTEM = {
        'default_error': AudioPrompt("1009", "Standard error message", "system"),
        'welcome': AudioPrompt("1001", "Welcome message", "system"),
        'goodbye': AudioPrompt("1029", "Goodbye message", "system"),
        'invalid_input': AudioPrompt("1010", "Invalid input message", "system"),
        'try_again': AudioPrompt("1011", "Please try again", "system"),
        'timeout': AudioPrompt("1012", "Input timeout", "system")
    }
    
    # Menu and input prompts
    MENU = {
        'main_menu': AudioPrompt("1677", "Main menu options", "menu"),
        'pin_entry': AudioPrompt("1008", "Enter PIN", "input"),
        'confirm_choice': AudioPrompt("1316", "Confirm selection", "input")
    }
    
    # Response handling
    RESPONSE = {
        'accept': AudioPrompt("1167", "Response accepted", "response"),
        'decline': AudioPrompt("1021", "Response declined", "response"),
        'transfer': AudioPrompt("1645", "Transfer request", "response")
    }
    
    # Status messages
    STATUS = {
        'processing': AudioPrompt("1232", "Processing request", "status"),
        'completed': AudioPrompt("1233", "Process complete", "status"),
        'please_wait': AudioPrompt("2223", "Please wait", "status")
    }

class IVRNodeBuilder:
    """Builder class for IVR node configuration"""
    
    def __init__(self):
        self.node = {}
    
    def set_base(self, label: str, log_message: str) -> 'IVRNodeBuilder':
        """Set base node properties"""
        self.node.update({
            'label': label,
            'log': log_message
        })
        return self
    
    def add_prompt(self, prompt_id: str) -> 'IVRNodeBuilder':
        """Add audio prompt"""
        self.node['playPrompt'] = [f"callflow:{prompt_id}"]
        return self
    
    def add_digit_collection(self, num_digits: int, choices: str = None) -> 'IVRNodeBuilder':
        """Configure digit collection"""
        digit_config = {
            'numDigits': num_digits,
            'maxTries': 3,
            'maxTime': 7,
            'errorPrompt': f"callflow:{AudioPromptLibrary.SYSTEM['default_error'].id}"
        }
        if choices:
            digit_config['validChoices'] = choices
        
        self.node['getDigits'] = digit_config
        return self
    
    def add_branch(self, branches: Dict[str, str]) -> 'IVRNodeBuilder':
        """Add branching logic"""
        self.node['branch'] = branches
        return self
    
    def build(self) -> Dict:
        """Return completed node configuration"""
        return self.node

class IVRTransformer:
    """Enhanced IVR transformation engine"""
    
    def __init__(self):
        self.audio_library = AudioPromptLibrary()
        self.node_builder = IVRNodeBuilder()
        
        # Track node relationships for flow control
        self.node_map = {}
        self.processed_nodes = set()
        
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
            
            # Reset tracking
            self.node_map = {}
            self.processed_nodes = set()
            
            # Build node map for relationship tracking
            self._build_node_map(nodes, edges)
            
            # Transform nodes
            ivr_nodes = []
            
            # Start with entry points
            entry_nodes = [n for n in nodes.values() if n.node_type == NodeType.START]
            if not entry_nodes:
                # Create default entry if none exists
                ivr_nodes.append(self._create_default_entry())
            
            # Process all nodes
            for node_id, node in nodes.items():
                if node_id not in self.processed_nodes:
                    ivr_node = self._transform_node(node, edges)
                    if ivr_node:
                        ivr_nodes.append(ivr_node)
                        self.processed_nodes.add(node_id)
            
            # Add standard handlers
            ivr_nodes.extend(self._create_standard_handlers())
            
            return ivr_nodes
            
        except Exception as e:
            raise RuntimeError(f"IVR transformation failed: {str(e)}")

    def _build_node_map(self, nodes: Dict[str, Node], edges: List[Edge]):
        """Build node relationship map"""
        self.node_map = {node_id: {'node': node, 'incoming': [], 'outgoing': []} 
                        for node_id, node in nodes.items()}
        
        for edge in edges:
            if edge.from_id in self.node_map:
                self.node_map[edge.from_id]['outgoing'].append(edge)
            if edge.to_id in self.node_map:
                self.node_map[edge.to_id]['incoming'].append(edge)

    def _transform_node(self, node: Node, edges: List[Edge]) -> Optional[Dict]:
        """Transform individual node based on type and context"""
        try:
            if node.node_type == NodeType.DECISION:
                return self._handle_decision_node(node)
            elif node.node_type == NodeType.INPUT:
                return self._handle_input_node(node)
            elif node.node_type == NodeType.MENU:
                return self._handle_menu_node(node)
            elif node.node_type == NodeType.TRANSFER:
                return self._handle_transfer_node(node)
            elif node.node_type == NodeType.ERROR:
                return self._handle_error_node(node)
            else:
                return self._handle_action_node(node)
                
        except Exception as e:
            raise ValueError(f"Node transformation failed for {node.id}: {str(e)}")

    def _handle_decision_node(self, node: Node) -> Dict:
        """Handle decision/branch nodes"""
        outgoing = self.node_map[node.id]['outgoing']
        
        branches = {}
        for edge in outgoing:
            if edge.label:
                # Extract digit from label (e.g., "Press 1" -> "1")
                digit_match = re.search(r'(\d+)', edge.label)
                if digit_match:
                    digit = digit_match.group(1)
                    branches[digit] = self._format_label(edge.to_id)
        
        return self.node_builder \
            .set_base(self._format_label(node.id), node.raw_text) \
            .add_prompt(AudioPromptLibrary.SYSTEM['default_error'].id) \
            .add_digit_collection(1, '|'.join(branches.keys())) \
            .add_branch(branches) \
            .build()

    def _handle_input_node(self, node: Node) -> Dict:
        """Handle input collection nodes"""
        is_pin = 'pin' in node.raw_text.lower()
        num_digits = 4 if is_pin else 1
        
        return self.node_builder \
            .set_base(self._format_label(node.id), node.raw_text) \
            .add_prompt(AudioPromptLibrary.MENU['pin_entry'].id if is_pin 
                       else AudioPromptLibrary.SYSTEM['default_error'].id) \
            .add_digit_collection(num_digits) \
            .build()

    def _handle_menu_node(self, node: Node) -> Dict:
        """Handle menu option nodes"""
        outgoing = self.node_map[node.id]['outgoing']
        
        menu_options = {}
        for edge in outgoing:
            if edge.label:
                menu_options[edge.label] = self._format_label(edge.to_id)
        
        return self.node_builder \
            .set_base(self._format_label(node.id), node.raw_text) \
            .add_prompt(AudioPromptLibrary.MENU['main_menu'].id) \
            .add_digit_collection(1) \
            .add_branch(menu_options) \
            .build()

    def _handle_transfer_node(self, node: Node) -> Dict:
        """Handle call transfer nodes"""
        return self.node_builder \
            .set_base(self._format_label(node.id), node.raw_text) \
            .add_prompt(AudioPromptLibrary.RESPONSE['transfer'].id) \
            .build()

    def _handle_error_node(self, node: Node) -> Dict:
        """Handle error and retry nodes"""
        return self.node_builder \
            .set_base(self._format_label(node.id), node.raw_text) \
            .add_prompt(AudioPromptLibrary.SYSTEM['default_error'].id) \
            .build()

    def _handle_action_node(self, node: Node) -> Dict:
        """Handle standard action nodes"""
        outgoing = self.node_map[node.id]['outgoing']
        
        builder = self.node_builder \
            .set_base(self._format_label(node.id), node.raw_text)
        
        # Add appropriate prompt based on node content
        if 'accept' in node.raw_text.lower():
            builder.add_prompt(AudioPromptLibrary.RESPONSE['accept'].id)
        elif 'decline' in node.raw_text.lower():
            builder.add_prompt(AudioPromptLibrary.RESPONSE['decline'].id)
        else:
            builder.add_prompt(AudioPromptLibrary.SYSTEM['default_error'].id)
        
        # Add next node if single path
        if len(outgoing) == 1:
            builder.add_branch({'next': self._format_label(outgoing[0].to_id)})
        
        return builder.build()

    def _create_default_entry(self) -> Dict:
        """Create default entry point"""
        return self.node_builder \
            .set_base("Start", "Call flow entry point") \
            .add_prompt(AudioPromptLibrary.SYSTEM['welcome'].id) \
            .build()

    def _create_standard_handlers(self) -> List[Dict]:
        """Create standard error and exit handlers"""
        handlers = []
        
        # Error handler
        handlers.append(self.node_builder \
            .set_base("Problems", "Error handler") \
            .add_prompt(AudioPromptLibrary.SYSTEM['default_error'].id) \
            .build())
        
        # Exit handler
        handlers.append(self.node_builder \
            .set_base("Goodbye", "Call completion") \
            .add_prompt(AudioPromptLibrary.SYSTEM['goodbye'].id) \
            .build())
        
        return handlers

    @staticmethod
    def _format_label(label: str) -> str:
        """Format node label for IVR compatibility"""
        return ' '.join(word.capitalize() for word in label.replace('_', ' ').split())

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """Convenience wrapper for graph transformation"""
    transformer = IVRTransformer()
    return transformer.transform(graph)