from typing import Dict, List, Optional, Any
import re

class IVRTransformer:
    def __init__(self):
        self.audio_prompts = {
            "Invalid entry": "callflow:1009",
            "Goodbye": "callflow:1029",
            "Enter your PIN": "callflow:1008",
            "accepted response": "callflow:1167",
            "recorded as a decline": "callflow:1021",
            "Please try again": "callflow:1009"
        }
        
        self.result_codes = {
            "accept": (1001, "Accept"),
            "decline": (1002, "Decline"),
            "not_home": (1006, "Not Home"),
            "qualified_no": (1145, "QualNo"),
            "error": (1198, "Error Out")
        }

    def transform(self, graph: Dict) -> List[Dict[str, Any]]:
        """Transform parsed Mermaid graph into IVR nodes."""
        nodes = []
        edges = graph['edges']
        node_data = graph['nodes']

        # Process each node
        for node_id, node in node_data.items():
            ivr_node = self._create_ivr_node(node, edges)
            if ivr_node:
                nodes.append(ivr_node)

        return nodes

    def _create_ivr_node(self, node: Dict, edges: List[Dict]) -> Dict:
        """Create an IVR node from a Mermaid node."""
        node_text = node.get('raw_text', '').replace('\n', ' ')
        
        ivr_node = {
            "label": self._generate_label(node_text),
            "log": node_text
        }

        # Handle node types
        if "input" in node_text.lower() or "press" in node_text.lower():
            ivr_node.update(self._create_input_node(node, edges))
        elif "invalid" in node_text.lower():
            ivr_node.update(self._create_error_node())
        elif any(key in node_text.lower() for key in ["accept", "decline", "qualified"]):
            ivr_node.update(self._create_response_node(node_text))
        elif "disconnect" in node_text.lower():
            ivr_node.update(self._create_end_node())

        # Add audio prompts
        play_prompt = self._find_audio_prompt(node_text)
        if play_prompt:
            ivr_node["playPrompt"] = [play_prompt]

        # Add connections
        outgoing_edges = [e for e in edges if e['from'] == node['id']]
        if outgoing_edges:
            ivr_node.update(self._create_connections(outgoing_edges))

        return ivr_node

    def _create_input_node(self, node: Dict, edges: List[Dict]) -> Dict:
        """Create an input node configuration."""
        valid_choices = []
        branches = {}
        
        for edge in edges:
            if edge['from'] == node['id'] and edge.get('label'):
                choice = edge['label'].split('-')[0].strip()
                if choice.isdigit():
                    valid_choices.append(choice)
                    branches[choice] = self._generate_label(edge['to'])

        if valid_choices:
            return {
                "getDigits": {
                    "numDigits": 1,
                    "maxTries": 3,
                    "maxTime": 7,
                    "validChoices": "|".join(valid_choices),
                    "errorPrompt": "callflow:1009",
                    "nonePrompt": "callflow:1009"
                },
                "branch": branches
            }
        return {}

    def _create_error_node(self) -> Dict:
        """Create an error node configuration."""
        return {
            "nobarge": "1",
            "goto": "Problems"
        }

    def _create_response_node(self, text: str) -> Dict:
        """Create a response node configuration."""
        for key, (code, name) in self.result_codes.items():
            if key in text.lower():
                return {
                    "gosub": ["SaveCallResult", code, name],
                    "nobarge": "1"
                }
        return {}

    def _create_end_node(self) -> Dict:
        """Create an end node configuration."""
        return {
            "nobarge": "1",
            "goto": "hangup"
        }

    def _create_connections(self, edges: List[Dict]) -> Dict:
        """Create connection configuration."""
        if len(edges) == 1 and not edges[0].get('label'):
            return {"goto": self._generate_label(edges[0]['to'])}
        return {}

    def _find_audio_prompt(self, text: str) -> Optional[str]:
        """Find matching audio prompt for text."""
        text_lower = text.lower()
        for key, prompt in self.audio_prompts.items():
            if key.lower() in text_lower:
                return prompt
        return None

    def _generate_label(self, text: str) -> str:
        """Generate a valid label from text."""
        # Remove special characters and spaces
        label = re.sub(r'[^\w\s]', '', text)
        # Convert to title case and remove spaces
        return ''.join(word.capitalize() for word in label.split())

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """Convert Mermaid graph to IVR configuration."""
    transformer = IVRTransformer()
    return transformer.transform(graph)