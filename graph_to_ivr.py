from typing import Dict, List, Optional, Any
import re
from parse_mermaid import Node, Edge, NodeType

AUDIO_PROMPTS = {
    "Invalid entry": "callflow:1009",
    "Enter PIN": "callflow:1008",
    "Accepted response": "callflow:1167",
    "Decline response": "callflow:1021",
    "Please have": "callflow:1017",
    "Goodbye": "callflow:1029",
    "Problems": "callflow:1351",
    "Welcome": "callflow:1210",
    "Transfer": "callflow:2223"
}

class IVRTransformer:
    def __init__(self):
        self.standard_nodes = {
            "problems": {
                "label": "Problems",
                "gosub": ["SaveCallResult", 1198, "Error Out"],
                "goto": "Goodbye"
            },
            "goodbye": {
                "label": "Goodbye",
                "log": "Goodbye(1029)",
                "playPrompt": ["callflow:1029"],
                "nobarge": "1",
                "goto": "hangup"
            }
        }
        
        self.result_codes = {
            "accept": (1001, "Accept"),
            "decline": (1002, "Decline"),
            "not_home": (1006, "Not Home"),
            "error": (1198, "Error Out")
        }

    def transform(self, graph: Dict) -> List[Dict[str, Any]]:
        """Transforms the parsed graph into a list of IVR nodes."""
        nodes_dict = graph.get('nodes', {})
        edges = graph.get('edges', [])
        ivr_nodes = []

        # Process each node
        for node_id, node in nodes_dict.items():
            ivr_node = self._transform_node(node, edges)
            if ivr_node:
                ivr_nodes.append(ivr_node)

        # Add standard nodes if needed
        if not any(n.get("label") == "Problems" for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes["problems"])
        if not any(n.get("label") == "Goodbye" for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes["goodbye"])

        return ivr_nodes

    def _transform_node(self, node: Node, edges: List[Edge]) -> Optional[Dict]:
        """Transforms an individual node to IVR format."""
        # Build base node
        ivr_node = {
            "label": self._to_title_case(node.id),
            "log": node.raw_text
        }

        # Handle different node types
        if getattr(node, 'node_type', None) == NodeType.RHOMBUS:
            self._handle_decision_node(ivr_node, node, edges)
        else:
            self._handle_action_node(ivr_node, node, edges)

        # Add special commands based on node content
        self._add_special_commands(ivr_node, node.raw_text)

        return ivr_node

    def _handle_decision_node(self, ivr_node: Dict, node: Node, edges: List[Edge]):
        """Sets up a decision node with getDigits and branch."""
        out_edges = [e for e in edges if e.from_id == node.id]
        
        ivr_node["getDigits"] = {
            "numDigits": 1,
            "maxTries": 3,
            "maxTime": 7,
            "validChoices": "",
            "errorPrompt": "callflow:1009",
            "nonePrompt": "callflow:1009"
        }

        branch_map = {}
        digit_choices = []

        for edge in out_edges:
            if edge.label:
                # Handle retry logic
                if "retry" in str(edge.label).lower():
                    continue
                
                # Extract digit choices
                digit_match = re.match(r'^(\d+)\s*-\s*(.*)', str(edge.label))
                if digit_match:
                    digit, action = digit_match.groups()
                    branch_map[digit] = self._to_title_case(edge.to_id)
                    digit_choices.append(digit)
                elif re.search(r'invalid|no input', str(edge.label), re.IGNORECASE):
                    branch_map["error"] = self._to_title_case(edge.to_id)
                    branch_map["none"] = self._to_title_case(edge.to_id)
                else:
                    clean_label = edge.label.strip('"') if edge.label else ""
                    branch_map[clean_label] = self._to_title_case(edge.to_id)

        if digit_choices:
            ivr_node["getDigits"]["validChoices"] = "|".join(digit_choices)
        ivr_node["branch"] = branch_map

    def _handle_action_node(self, ivr_node: Dict, node: Node, edges: List[Edge]):
        """Sets up an action node with playPrompt and other commands."""
        out_edges = [e for e in edges if e.from_id == node.id]
        
        # Set audio prompt
        audio_prompt = self._find_audio_prompt(node.raw_text)
        if audio_prompt:
            ivr_node["playPrompt"] = [audio_prompt]
        else:
            ivr_node["playPrompt"] = [f"tts:{node.raw_text}"]

        # Add nobarge for messages that shouldn't be interrupted
        if any(keyword in node.raw_text.lower() for keyword in ["welcome", "message", "please", "goodbye"]):
            ivr_node["nobarge"] = "1"

        # Handle single output
        if len(out_edges) == 1:
            ivr_node["goto"] = self._to_title_case(out_edges[0].to_id)

    def _add_special_commands(self, ivr_node: Dict, raw_text: str):
        """Adds special commands based on node text."""
        text_lower = raw_text.lower()
        
        # Handle result codes
        for key, (code, name) in self.result_codes.items():
            if key in text_lower:
                ivr_node["gosub"] = ["SaveCallResult", code, name]
                break

        # Handle PIN entry
        if "pin" in text_lower:
            ivr_node["getDigits"] = {
                "numDigits": 5,
                "maxTries": 3,
                "maxTime": 7,
                "validChoices": "{{pin}}",
                "errorPrompt": "callflow:1009",
                "nonePrompt": "callflow:1009"
            }
            ivr_node["branch"] = {
                "error": "Problems",
                "none": "Problems"
            }

        # Handle disconnect nodes
        if "disconnect" in text_lower:
            ivr_node["goto"] = "hangup"

    def _find_audio_prompt(self, text: str) -> Optional[str]:
        """Finds matching audio prompt for the text."""
        if not text:
            return None
            
        text_lower = text.lower()
        
        # Try exact matches first
        for key, prompt in AUDIO_PROMPTS.items():
            if key.lower() in text_lower:
                return prompt

        return None

    @staticmethod
    def _to_title_case(s: str) -> str:
        """Converts strings like 'node_id' to 'Node Id'."""
        return ' '.join(word.capitalize() for word in s.replace('_', ' ').split())

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """Wrapper function to maintain compatibility with existing code."""
    transformer = IVRTransformer()
    return transformer.transform(graph)