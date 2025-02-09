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
        
        ivr_nodes = []
        
        # Add standard "start" node if not present
        has_start = any(n.node_type == NodeType.START for n in nodes.values())
        if not has_start:
            ivr_nodes.append(self.standard_nodes['start'])
        
        # Transform each node
        for node_id, node in nodes.items():
            ivr_node = self._transform_node(node, edges)
            if ivr_node:
                ivr_nodes.append(ivr_node)
        
        # Add standard "Problems" and "Goodbye" if missing
        if not any(n.get('label') == 'Problems' for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes['problems'])
        if not any(n.get('label') == 'Goodbye' for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes['goodbye'])
        
        return ivr_nodes

    def _transform_node(self, node: Node, edges: List[Edge]) -> Optional[Dict]:
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
        elif node.node_type == NodeType.END:
            # We might skip if we rely on a standard "Goodbye" node, but let's keep a minimal config
            ivr_node['playPrompt'] = [AudioPrompts.PROMPTS[NodeType.END]]
            ivr_node['goto'] = "Goodbye"
        else:
            self._handle_action_node(ivr_node, node, edges)

        return ivr_node

    def _handle_decision_node(self, ivr_node: Dict, node: Node, edges: List[Edge]):
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
            label = edge.label.strip() if edge.label else ""
            # ### CHANGE: More robust digit extraction
            # E.g. "1 - Yes", "Press 1 - Transfer", "1) Accept"
            digit_match = re.match(r'(?:press\s*)?(\d+)', label, re.IGNORECASE)
            if digit_match:
                digit = digit_match.group(1)
                branch_map[digit] = self._format_label(edge.to_id)
            else:
                # If no digit found, handle "error" or skip
                # but let's add a fallback if label says "no" or "yes" without a number
                # This is optional logic you can refine
                if "yes" in label.lower():
                    branch_map["1"] = self._format_label(edge.to_id)
                elif "no" in label.lower():
                    branch_map["2"] = self._format_label(edge.to_id)
                else:
                    # Fallback to error or put the entire label as a single digit?
                    branch_map["error"] = self._format_label(edge.to_id)

        if branch_map:
            ivr_node['branch'] = branch_map

    def _handle_input_node(self, ivr_node: Dict, node: Node):
        ivr_node.update({
            'playPrompt': [AudioPrompts.PROMPTS[NodeType.INPUT]],
            'getDigits': {
                'numDigits': 4,  # typical for PIN
                'maxTries': 3,
                'errorPrompt': AudioPrompts.PROMPTS['default']
            }
        })

    def _handle_transfer_node(self, ivr_node: Dict):
        ivr_node.update({
            'playPrompt': [AudioPrompts.PROMPTS[NodeType.TRANSFER]],
            'include': "../../util/xfer.js",
            'gosub': "XferCall"
        })

    def _handle_action_node(self, ivr_node: Dict, node: Node, edges: List[Edge]):
        audio_prompt = self._select_audio_prompt(node.raw_text)
        if audio_prompt:
            ivr_node['playPrompt'] = [audio_prompt]
        
        # Connect to next node if single outgoing edge
        out_edges = [e for e in edges if e.from_id == node.id]
        if len(out_edges) == 1:
            ivr_node['goto'] = self._format_label(out_edges[0].to_id)

    def _select_audio_prompt(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        
        for key, prompt in AudioPrompts.PROMPTS.items():
            if isinstance(key, str) and key in text_lower:
                return prompt
        
        return AudioPrompts.PROMPTS['default']

    @staticmethod
    def _format_label(label: str) -> str:
        """Convert node ID to a more readable label"""
        return ' '.join(word.capitalize() for word in label.replace('_', ' ').split())

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    transformer = IVRTransformer()
    return transformer.transform(graph)
