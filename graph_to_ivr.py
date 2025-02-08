from typing import Dict, List, Optional, Any
import re
from parse_mermaid import Node, Edge, NodeType

AUDIO_PROMPTS = {
    "Welcome": "callflow:1210",
    "Invalid entry": "callflow:1009",
    "Enter PIN": "callflow:1008",
    "accepted": "callflow:1167",
    "decline": "callflow:1021",
    "Please have": "callflow:1017",
    "goodbye": "callflow:1029",
    "electric callout": "callflow:1274"
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
                "log": "Goodbye message",
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
        nodes_dict = graph.get('nodes', {})
        edges = graph.get('edges', [])
        ivr_nodes = []

        print(f"Found {len(nodes_dict)} nodes and {len(edges)} edges")
        
        # Convert each node
        for node_id, node in nodes_dict.items():
            ivr_node = self._create_base_node(node)
            self._add_audio_prompts(ivr_node, node)
            self._add_special_commands(ivr_node, node)
            self._handle_edges(ivr_node, node, edges)
            ivr_nodes.append(ivr_node)
            print(f"Processed node {node_id}")

        # Add standard nodes
        if not any(n.get("label") == "Problems" for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes["problems"])
        if not any(n.get("label") == "Goodbye" for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes["goodbye"])

        return ivr_nodes

    def _create_base_node(self, node: Node) -> Dict:
        """Creates the basic node structure."""
        return {
            "label": node.id,
            "log": node.raw_text,
            "nobarge": "1" if any(kw in node.raw_text.lower() 
                                for kw in ["welcome", "please", "message"]) else None
        }

    def _add_audio_prompts(self, ivr_node: Dict, node: Node):
        """Adds appropriate audio prompts."""
        prompts = []
        text_lower = node.raw_text.lower()
        
        for key, prompt in AUDIO_PROMPTS.items():
            if key.lower() in text_lower:
                prompts.append(prompt)
                break
        
        if not prompts:
            prompts.append(f"tts:{node.raw_text}")
            
        ivr_node["playPrompt"] = prompts

    def _add_special_commands(self, ivr_node: Dict, node: Node):
        """Adds special commands based on node content."""
        text_lower = node.raw_text.lower()
        
        # Handle PIN entry
        if "pin" in text_lower:
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
        
        # Handle result codes
        for key, (code, name) in self.result_codes.items():
            if key in text_lower:
                ivr_node["gosub"] = ["SaveCallResult", code, name]
                break

        # Handle disconnect
        if "disconnect" in text_lower:
            ivr_node["goto"] = "hangup"

    def _handle_edges(self, ivr_node: Dict, node: Node, edges: List[Edge]):
        """Handles edge connections and branch logic."""
        out_edges = [e for e in edges if e.from_id == node.id]
        
        if not out_edges:
            return
            
        # Single edge case
        if len(out_edges) == 1 and not ivr_node.get("goto"):
            ivr_node["goto"] = out_edges[0].to_id
            return
            
        # Multiple edges case
        branch_map = {}
        digit_choices = []
        
        # Set up getDigits if not already present
        if len(out_edges) > 1 and not ivr_node.get("getDigits"):
            ivr_node["getDigits"] = {
                "numDigits": 1,
                "maxTries": 3,
                "maxTime": 7,
                "validChoices": "",
                "errorPrompt": "callflow:1009",
                "nonePrompt": "callflow:1009"
            }
        
        for edge in out_edges:
            if not edge.label:
                continue
                
            label = str(edge.label)
            
            # Extract digit if present
            digit_match = re.search(r'(\d+)\s*-', label)
            if digit_match:
                digit = digit_match.group(1)
                branch_map[digit] = edge.to_id
                digit_choices.append(digit)
            elif "invalid" in label.lower() or "no input" in label.lower():
                branch_map["error"] = edge.to_id
                branch_map["none"] = edge.to_id
            else:
                clean_label = label.strip('"').strip()
                if clean_label:
                    branch_map[clean_label] = edge.to_id

        if digit_choices:
            ivr_node["getDigits"]["validChoices"] = "|".join(digit_choices)
        if branch_map:
            ivr_node["branch"] = branch_map

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """Wrapper function to maintain compatibility with existing code."""
    transformer = IVRTransformer()
    return transformer.transform(graph)