from typing import Dict, List, Optional, Any
import re
from parse_mermaid import Node, Edge, NodeType

# Extended mapping of common phrases to audio prompts
AUDIO_PROMPTS = {
    "Invalid entry. Please try again": "callflow:1009",
    "Goodbye message": "callflow:1029",
    "Please enter your PIN": "callflow:1008",
    "An accepted response has been recorded": "callflow:1167",
    "Your response is being recorded as a decline": "callflow:1021",
    "Please contact your local control center": "callflow:1705",
    "To speak to a dispatcher": "callflow:1645",
    "We were not able to complete the transfer": "callflow:1353",
}

class IVRTransformer:
    def __init__(self):
        self.standard_nodes = {
            "start": {
                "label": "Start",
                "maxLoop": ["Main", 3, "Problems"],
                "nobarge": "1",
                "log": "Entry point to call flow"
            },
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
            "qualified_no": (1145, "QualNo"),
            "error": (1198, "Error Out")
        }

    def transform(self, graph: Dict) -> List[Dict[str, Any]]:
        """Transforms the parsed graph into a list of IVR nodes."""
        nodes_dict = graph['nodes']
        edges = graph['edges']
        styles = graph.get('styles', {})

        ivr_nodes = []

        # Process each node
        for node_id, node in nodes_dict.items():
            ivr_node = self._transform_node(node, edges, styles)
            if ivr_node:
                ivr_nodes.append(ivr_node)

        # Add standard nodes only if needed
        if not any(n.get("label", "").lower() == "goodbye" for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes["goodbye"])

        return ivr_nodes

    def _transform_node(self, node: Node, edges: List[Edge], styles: Dict) -> Optional[Dict]:
        """Transforms an individual node to IVR format."""
        node_id = node.id
        raw_text = node.raw_text
        node_type = node.node_type
        
        # Build base node
        ivr_node = {
            "label": self._to_title_case(node_id),
            "log": raw_text
        }

        # Handle decision nodes (rhombus)
        if node_type == NodeType.RHOMBUS:
            self._handle_decision_node(ivr_node, node, edges)
        else:
            self._handle_action_node(ivr_node, node, edges)

        # Add special commands based on text
        self._add_special_commands(ivr_node, raw_text)

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
                    
                # Detect patterns in labels
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
        
        # Look for known audio prompt or use TTS
        audio_prompt = self._find_audio_prompt(node.raw_text)
        if audio_prompt:
            ivr_node["playPrompt"] = [audio_prompt]
        else:
            ivr_node["playPrompt"] = [f"tts:{node.raw_text}"]

        # Handle incoming retry edges
        in_edges = [e for e in edges if e.to_id == node.id]
        has_retry = any("retry" in str(e.label).lower() for e in in_edges)
        if has_retry:
            if "maxLoop" not in ivr_node:
                ivr_node["maxLoop"] = ["Retry", 3, "Problems"]

        # If there's a single non-retry output, add goto
        regular_out_edges = [e for e in out_edges if not (e.label and "retry" in str(e.label).lower())]
        if len(regular_out_edges) == 1:
            ivr_node["goto"] = self._to_title_case(regular_out_edges[0].to_id)

    def _add_special_commands(self, ivr_node: Dict, raw_text: str):
        """Adds special commands based on node text."""
        text_lower = raw_text.lower()
        
        # Handle result codes
        for key, (code, name) in self.result_codes.items():
            if key in text_lower:
                ivr_node["gosub"] = ["SaveCallResult", code, name]
                break

        # Add nobarge for certain message types
        if any(keyword in text_lower for keyword in ["goodbye", "recorded", "message", "please", "welcome"]):
            ivr_node["nobarge"] = "1"

        # Handle PIN entry
        if "pin" in text_lower:
            ivr_node["getDigits"] = {
                "numDigits": 4,
                "terminator": "#",
                "maxTries": 3,
                "maxTime": 7,
                "errorPrompt": "callflow:1009",
                "nonePrompt": "callflow:1009"
            }

        # Handle disconnect nodes
        if "disconnect" in text_lower or node_type == NodeType.CIRCLE:
            ivr_node["goto"] = "hangup"

    def _find_audio_prompt(self, text: str) -> Optional[str]:
        """Searches for a matching audio prompt."""
        if not text:
            return None

        # Try exact match first
        if text in AUDIO_PROMPTS:
            return AUDIO_PROMPTS[text]

        # Then try partial match
        text_lower = text.lower()
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