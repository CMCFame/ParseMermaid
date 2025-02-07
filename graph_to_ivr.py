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
        """
        Transforms the parsed graph into a list of IVR nodes.
        """
        nodes_dict = graph['nodes']
        edges = graph['edges']
        styles = graph.get('styles', {})
        subgraphs = graph.get('subgraphs', {})

        ivr_nodes = []
        
        # Add initial node if needed
        if not any(n.raw_text.lower().startswith('start') for n in nodes_dict.values()):
            ivr_nodes.append(self.standard_nodes["start"])

        # Process each node
        for node_id, node in nodes_dict.items():
            ivr_node = self._transform_node(node, edges, styles)
            if ivr_node:
                ivr_nodes.append(ivr_node)

        # Add standard nodes if they don't exist
        if not any(n["label"] == "Problems" for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes["problems"])
        if not any(n["label"] == "Goodbye" for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes["goodbye"])

        return ivr_nodes

    def _transform_node(self, node: Node, edges: List[Edge], styles: Dict) -> Optional[Dict]:
        """
        Transforms an individual node to IVR format.
        """
        node_id = node.id
        raw_text = node.raw_text
        node_type = node.node_type
        
        # Build base node
        ivr_node = {
            "label": self._to_title_case(node_id),
            "log": raw_text
        }

        # Apply styles
        for style_class in node.style_classes:
            if style_class in styles:
                self._apply_style(ivr_node, styles[style_class])

        # Handle decision nodes (rhombus)
        if node_type == NodeType.RHOMBUS:
            self._handle_decision_node(ivr_node, node, edges)
        else:
            self._handle_action_node(ivr_node, node, edges)

        # Add special commands based on text or type
        self._add_special_commands(ivr_node, raw_text)

        return ivr_node

    def _handle_decision_node(self, ivr_node: Dict, node: Node, edges: List[Edge]):
        """
        Sets up a decision node with getDigits and branch.
        """
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
                # Detect patterns in labels
                digit_match = re.match(r'^(\d+)\s*-\s*(.*)', edge.label)
                if digit_match:
                    digit, action = digit_match.groups()
                    branch_map[digit] = self._to_title_case(edge.to_id)
                    digit_choices.append(digit)
                elif re.search(r'invalid|no input', edge.label, re.IGNORECASE):
                    branch_map["error"] = self._to_title_case(edge.to_id)
                    branch_map["none"] = self._to_title_case(edge.to_id)
                else:
                    branch_map[edge.label] = self._to_title_case(edge.to_id)

        if digit_choices:
            ivr_node["getDigits"]["validChoices"] = "|".join(digit_choices)
        ivr_node["branch"] = branch_map

    def _handle_action_node(self, ivr_node: Dict, node: Node, edges: List[Edge]):
        """
        Sets up an action node with playPrompt and other commands.
        """
        out_edges = [e for e in edges if e.from_id == node.id]
        
        # Look for known audio prompt or use TTS
        audio_prompt = self._find_audio_prompt(node.raw_text)
        if audio_prompt:
            ivr_node["playPrompt"] = [audio_prompt]
        else:
            ivr_node["playPrompt"] = [f"tts:{node.raw_text}"]

        # If there's a single output, add goto
        if len(out_edges) == 1:
            ivr_node["goto"] = self._to_title_case(out_edges[0].to_id)

    def _add_special_commands(self, ivr_node: Dict, raw_text: str):
        """
        Adds special commands based on node text.
        """
        # Detect gosub commands based on text
        text_lower = raw_text.lower()
        
        for key, (code, name) in self.result_codes.items():
            if key in text_lower:
                ivr_node["gosub"] = ["SaveCallResult", code, name]
                break

        # Add nobarge for certain message types
        if any(keyword in text_lower for keyword in ["goodbye", "recorded", "message", "please"]):
            ivr_node["nobarge"] = "1"

        # Detect transfers
        if "transfer" in text_lower:
            ivr_node.update({
                "setvar": {"transfer_ringback": "callflow:2223"},
                "include": "../../util/xfer.js",
                "gosub": "XferCall"
            })

    def _find_audio_prompt(self, text: str) -> Optional[str]:
        """
        Searches for a matching audio prompt.
        """
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
    def _apply_style(ivr_node: Dict, style: str):
        """
        Applies Mermaid styles to IVR node.
        """
        style_parts = style.split(',')
        for part in style_parts:
            if 'fill' in part:
                # Fill styles could map to different behaviors
                pass
            if 'stroke' in part:
                # Border styles could map to different behaviors
                pass

    @staticmethod
    def _to_title_case(s: str) -> str:
        """
        Converts strings like 'node_id' to 'Node Id'.
        """
        return ' '.join(word.capitalize() for word in s.replace('_', ' ').split())

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """
    Wrapper function to maintain compatibility with existing code.
    """
    transformer = IVRTransformer()
    return transformer.transform(graph)