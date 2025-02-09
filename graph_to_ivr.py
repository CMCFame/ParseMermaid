from typing import Dict, List, Optional, Any
import re
from parse_mermaid import Node, Edge, NodeType

class AudioPrompts:
    """Comprehensive audio prompt mapping"""
    PROMPTS = {
        # Generic prompts
        'default': "callflow:1009",
        
        # Specific node type prompts
        NodeType.START: "callflow:1001",
        NodeType.END: "callflow:1029",
        NodeType.DECISION: "callflow:1010",
        NodeType.INPUT: "callflow:1008",
        NodeType.TRANSFER: "callflow:1645",
        
        # Action-specific prompts
        'availability': "callflow:1677",
        'pin_change': "callflow:1051",
        'test_number': "callflow:1678",
        'message_admin': "callflow:1053"
    }

class IVRTransformer:
    def __init__(self):
        # Configurable standard nodes
        self.standard_nodes = {
            "start": {
                "label": "Start",
                "log": "Call flow entry point",
                "playPrompt": [AudioPrompts.PROMPTS[NodeType.START]],
                "nobarge": "1"
            },
            "problems": {
                "label": "Problems",
                "log": "Handling unexpected issues",
                "playPrompt": [AudioPrompts.PROMPTS['default']],
                "goto": "Goodbye"
            },
            "goodbye": {
                "label": "Goodbye",
                "log": "Ending call",
                "playPrompt": [AudioPrompts.PROMPTS[NodeType.END]],
                "goto": "hangup"
            }
        }

        # Result code mapping for different scenarios
        self.result_codes = {
            'accept': (1001, "Accept"),
            'decline': (1002, "Decline"),
            'not_home': (1006, "Not Home"),
            'error': (1198, "Error Out")
        }

    def transform(self, graph: Dict) -> List[Dict[str, Any]]:
        """
        Transform parsed graph into IVR flow
        
        Args:
            graph (Dict): Parsed Mermaid graph structure
        
        Returns:
            List[Dict]: Transformed IVR nodes
        """
        nodes = graph['nodes']
        edges = graph['edges']
        
        # Initialize IVR nodes
        ivr_nodes = []
        
        # Add standard start node if not present
        if not any(node.node_type == NodeType.START for node in nodes.values()):
            ivr_nodes.append(self.standard_nodes['start'])
        
        # Transform each node
        for node_id, node in nodes.items():
            ivr_node = self._transform_node(node, edges)
            if ivr_node:
                ivr_nodes.append(ivr_node)
        
        # Add standard problem and goodbye nodes
        if not any(node.get('label') == 'Problems' for node in ivr_nodes):
            ivr_nodes.append(self.standard_nodes['problems'])
        
        if not any(node.get('label') == 'Goodbye' for node in ivr_nodes):
            ivr_nodes.append(self.standard_nodes['goodbye'])
        
        return ivr_nodes

    def _transform_node(self, node: Node, edges: List[Edge]) -> Optional[Dict]:
        """
        Transform individual node to IVR format
        
        Args:
            node (Node): Source node
            edges (List[Edge]): All graph edges
        
        Returns:
            Optional[Dict]: Transformed node configuration
        """
        ivr_node = {
            'label': self._format_label(node.id),
            'log': node.raw_text
        }
        
        # Node type-specific transformations
        if node.node_type == NodeType.DECISION:
            self._handle_decision_node(ivr_node, node, edges)
        elif node.node_type == NodeType.INPUT:
            self._handle_input_node(ivr_node, node)
        elif node.node_type == NodeType.TRANSFER:
            self._handle_transfer_node(ivr_node)
        else:
            self._handle_action_node(ivr_node, node, edges)
        
        return ivr_node

    def _handle_decision_node(self, ivr_node: Dict, node: Node, edges: List[Edge]):
        """Configure decision/input node with branching logic"""
        out_edges = [e for e in edges if e.from_id == node.id]
        
        ivr_node.update({
            'playPrompt': [AudioPrompts.PROMPTS[NodeType.DECISION]],
            'getDigits': {
                'numDigits': 1,
                'maxTries': 3,
                'errorPrompt': AudioPrompts.PROMPTS['default']
            }
        })
        
        branch_map = {}
        for edge in out_edges:
            if edge.label:
                # Use edge label as digit choice
                digit_match = re.match(r'^(\d+)\s*-\s*(.+)', edge.label)
                if digit_match:
                    digit, action = digit_match.groups()
                    branch_map[digit] = self._format_label(edge.to_id)
        
        if branch_map:
            ivr_node['branch'] = branch_map

    def _handle_input_node(self, ivr_node: Dict, node: Node):
        """Configure input/PIN entry node"""
        ivr_node.update({
            'playPrompt': [AudioPrompts.PROMPTS[NodeType.INPUT]],
            'getDigits': {
                'numDigits': 4,  # Typical PIN length
                'maxTries': 3,
                'errorPrompt': AudioPrompts.PROMPTS['default']
            }
        })

    def _handle_transfer_node(self, ivr_node: Dict):
        """Configure transfer/dispatch node"""
        ivr_node.update({
            'playPrompt': [AudioPrompts.PROMPTS[NodeType.TRANSFER]],
            'include': "../../util/xfer.js",
            'gosub': "XferCall"
        })

    def _handle_action_node(self, ivr_node: Dict, node: Node, edges: List[Edge]):
        """Handle standard action/message nodes"""
        # Select appropriate audio prompt
        audio_prompt = self._select_audio_prompt(node.raw_text)
        if audio_prompt:
            ivr_node['playPrompt'] = [audio_prompt]
        
        # Connect to next node if single outgoing edge
        out_edges = [e for e in edges if e.from_id == node.id]
        if len(out_edges) == 1:
            ivr_node['goto'] = self._format_label(out_edges[0].to_id)

    def _select_audio_prompt(self, text: str) -> Optional[str]:
        """Intelligently select audio prompt based on text content"""
        text_lower = text.lower()
        
        for key, prompt in AudioPrompts.PROMPTS.items():
            if isinstance(key, str) and key in text_lower:
                return prompt
        
        return AudioPrompts.PROMPTS['default']

    @staticmethod
    def _format_label(label: str) -> str:
        """Convert node ID to title case label"""
        return ' '.join(word.capitalize() for word in label.replace('_', ' ').split())

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """Wrapper function for transformation"""
    transformer = IVRTransformer()
    return transformer.transform(graph)