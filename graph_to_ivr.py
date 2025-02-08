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
    "Electric callout": "callflow:1274",
    "Press any key": "callflow:1265",
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
            "qualified": (1145, "QualNo"),
            "error": (1198, "Error Out")
        }

    def transform(self, graph: Dict) -> List[Dict[str, Any]]:
        """Transforms the parsed graph into a list of IVR nodes."""
        nodes_dict = graph.get('nodes', {})
        edges = graph.get('edges', [])
        ivr_nodes = []

        # First pass: Create all nodes
        for node_id, node in nodes_dict.items():
            ivr_node = self._transform_node(node, edges)
            if ivr_node:
                ivr_nodes.append(ivr_node)

        # Second pass: Update node connections
        for node_id, node in nodes_dict.items():
            self._update_node_connections(node_id, edges, ivr_nodes)

        # Add standard nodes if needed
        if not any(n.get("label") == "Problems" for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes["problems"])
        if not any(n.get("label") == "Goodbye" for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes["goodbye"])

        return ivr_nodes

    def _transform_node(self, node: Node, edges: List[Edge]) -> Optional[Dict]:
        """Creates initial IVR node structure."""
        ivr_node = {
            "label": node.id,
            "log": node.raw_text
        }

        # Add audio prompt
        audio_prompt = self._find_audio_prompt(node.raw_text)
        if audio_prompt:
            ivr_node["playPrompt"] = [audio_prompt]
        else:
            ivr_node["playPrompt"] = [f"tts:{node.raw_text}"]

        # Add nobarge for certain messages
        if any(keyword in node.raw_text.lower() for keyword in 
               ["welcome", "message", "please", "goodbye", "recorded"]):
            ivr_node["nobarge"] = "1"

        # Handle special node types
        if "pin" in node.raw_text.lower():
            self._add_pin_node_config(ivr_node)
        elif "accept" in node.raw_text.lower():
            self._add_accept_node_config(ivr_node)
        elif "decline" in node.raw_text.lower():
            self._add_decline_node_config(ivr_node)
        elif "qualified" in node.raw_text.lower():
            self._add_qualified_no_config(ivr_node)
        elif "disconnect" in node.raw_text.lower():
            ivr_node["goto"] = "hangup"

        return ivr_node

    def _update_node_connections(self, node_id: str, edges: List[Edge], ivr_nodes: List[Dict]):
        """Updates node connections based on edges."""
        node_edges = [e for e in edges if e.from_id == node_id]
        
        # Find the current node in ivr_nodes
        current_node = next((n for n in ivr_nodes if n["label"] == node_id), None)
        if not current_node:
            return

        # Handle decision node edges
        if len(node_edges) > 1:
            if not current_node.get("getDigits"):
                current_node["getDigits"] = {
                    "numDigits": 1,
                    "maxTries": 3,
                    "maxTime": 7,
                    "validChoices": "",
                    "errorPrompt": "callflow:1009",
                    "nonePrompt": "callflow:1009"
                }

            branch_map = {}
            digit_choices = []

            for edge in node_edges:
                if edge.label:
                    # Handle retry logic
                    if "retry" in str(edge.label).lower():
                        continue

                    # Extract digit choices
                    digit_match = re.match(r'.*?(\d+)\s*-\s*(.*)', str(edge.label))
                    if digit_match:
                        digit, action = digit_match.groups()
                        branch_map[digit] = edge.to_id
                        digit_choices.append(digit)
                    elif re.search(r'invalid|no input', str(edge.label), re.IGNORECASE):
                        branch_map["error"] = edge.to_id
                        branch_map["none"] = edge.to_id
                    else:
                        branch_map[edge.label] = edge.to_id

            if digit_choices:
                current_node["getDigits"]["validChoices"] = "|".join(digit_choices)
            current_node["branch"] = branch_map

        # Handle single connection
        elif len(node_edges) == 1 and not current_node.get("goto"):
            current_node["goto"] = node_edges[0].to_id

    def _add_pin_node_config(self, ivr_node: Dict):
        """Adds PIN entry node configuration."""
        ivr_node.update({
            "getDigits": {
                "numDigits": 5,
                "maxTries": 3,
                "maxTime": 7,
                "validChoices": "{{pin}}",
                "errorPrompt": "callflow:1009",
                "nonePrompt": "callflow:1009"
            },
            "branch": {
                "error": "Problems",
                "none": "Problems"
            }
        })

    def _add_accept_node_config(self, ivr_node: Dict):
        """Adds accept node configuration."""
        ivr_node["gosub"] = ["SaveCallResult", 1001, "Accept"]
        ivr_node["nobarge"] = "1"

    def _add_decline_node_config(self, ivr_node: Dict):
        """Adds decline node configuration."""
        ivr_node["gosub"] = ["SaveCallResult", 1002, "Decline"]
        ivr_node["nobarge"] = "1"

    def _add_qualified_no_config(self, ivr_node: Dict):
        """Adds qualified no node configuration."""
        ivr_node["gosub"] = ["SaveCallResult", 1145, "QualNo"]
        ivr_node["nobarge"] = "1"

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

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """Wrapper function to maintain compatibility with existing code."""
    transformer = IVRTransformer()
    return transformer.transform(graph)