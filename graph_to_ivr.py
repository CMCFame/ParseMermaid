"""
Enhanced IVR transformation module with complete flow handling
"""
import re
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from parse_mermaid import Node, Edge, NodeType

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@dataclass
class IVRState:
    """Track processing state"""
    current_node: Optional[str] = None
    processed_nodes: Set[str] = field(default_factory=set)
    branch_map: Dict[str, Dict] = field(default_factory=dict)

class IVRTransformer:
    """Transform Mermaid diagrams to IVR configurations"""
    
    def __init__(self):
        self.state = IVRState()
        self.node_map = {}
        self.nodes = []

    def transform(self, graph: Dict) -> List[Dict[str, Any]]:
        """Transform graph into IVR nodes"""
        try:
            # Reset state
            self.nodes = []
            self.state = IVRState()
            
            # Extract components
            nodes_dict = graph['nodes']
            edges = graph['edges']
            
            # Build node relationships
            self.node_map = self._build_node_map(nodes_dict, edges)
            
            # Process nodes
            for node_id, node in nodes_dict.items():
                if node_id not in self.state.processed_nodes:
                    node_config = self._process_node(node, edges)
                    if node_config:
                        self.nodes.append(node_config)
                        logger.debug(f"Added node: {node_config['label']}")
            
            # Add standard handlers
            if not any(n.get('label') == 'Problems' for n in self.nodes):
                self.nodes.append(self._create_error_handler())
            if not any(n.get('label') == 'Goodbye' for n in self.nodes):
                self.nodes.append(self._create_goodbye_handler())
            
            return self.nodes
        
        except Exception as e:
            logger.error(f"Transform error: {str(e)}")
            return [self._create_error_handler()]

    def _build_node_map(self, nodes: Dict[str, Node], edges: List[Edge]) -> Dict:
        """Build node relationship map"""
        return {
            node_id: {
                'node': node,
                'outgoing': [e for e in edges if e.from_id == node_id],
                'incoming': [e for e in edges if e.to_id == node_id]
            }
            for node_id, node in nodes.items()
        }

    def _process_node(self, node: Node, edges: List[Edge]) -> Optional[Dict]:
        """Process individual node with complete flow handling"""
        try:
            # Skip if already processed
            if node.id in self.state.processed_nodes:
                return None
                
            self.state.processed_nodes.add(node.id)
            text = node.raw_text
            node_config = {
                "label": self._format_label(node.id),
                "log": text
            }

            # Handle initial welcome node
            if "This is an electric callout" in text and "Press" in text:
                return {
                    "label": "Welcome",
                    "log": text,
                    "playPrompt": ["callflow:1001"],
                    "getDigits": {
                        "numDigits": 1,
                        "maxTries": 3,
                        "validChoices": "1|3|7|9",
                        "errorPrompt": "callflow:1009",
                        "timeoutPrompt": "callflow:1010"
                    },
                    "branch": {
                        "1": "EnterPin",
                        "3": "NeedMoreTime",
                        "7": "NotHome",
                        "9": "Welcome"
                    }
                }

            # Handle 30-second message
            elif "30-second message" in text:
                return {
                    "label": "NeedMoreTime",
                    "log": text,
                    "playPrompt": ["callflow:1265"],
                    "goto": "Welcome"
                }

            # Handle PIN entry
            elif "Enter" in text and "PIN" in text:
                return {
                    "label": "EnterPin",
                    "log": text,
                    "playPrompt": ["callflow:1008"],
                    "getDigits": {
                        "numDigits": 4,
                        "maxTries": 3,
                        "terminator": "#",
                        "errorPrompt": "callflow:1009"
                    },
                    "branch": {
                        "valid": "ElectricCallout",
                        "invalid": "InvalidEntry"
                    }
                }

            # Handle invalid entry
            elif "Invalid" in text:
                return {
                    "label": "InvalidEntry",
                    "log": text,
                    "playPrompt": ["callflow:1009"],
                    "goto": "Welcome"
                }

            # Handle Electric Callout
            elif "Electric Callout" in text and "This is an electric callout" in text:
                return {
                    "label": "ElectricCallout",
                    "log": text,
                    "playPrompt": ["callflow:1274"],
                    "goto": "CalloutReason"
                }

            # Handle Callout Reason
            elif "Callout Reason" in text:
                return {
                    "label": "CalloutReason",
                    "log": text,
                    "playPrompt": ["callflow:1019"],
                    "goto": "TroubleLocation"
                }

            # Handle Trouble Location
            elif "Trouble Location" in text:
                return {
                    "label": "TroubleLocation",
                    "log": text,
                    "playPrompt": ["callflow:1232"],
                    "goto": "CustomMessage"
                }

            # Handle Custom Message
            elif "Custom Message" in text:
                return {
                    "label": "CustomMessage",
                    "log": text,
                    "playPrompt": ["callflow:2000"],
                    "goto": "AvailableForCallout"
                }

            # Handle Available For Callout
            elif "Available For Callout" in text:
                return {
                    "label": "AvailableForCallout",
                    "log": text,
                    "playPrompt": ["callflow:1316"],
                    "getDigits": {
                        "numDigits": 1,
                        "maxTries": 3,
                        "validChoices": "1|3|9",
                        "errorPrompt": "callflow:1009"
                    },
                    "branch": {
                        "1": "AcceptedResponse",
                        "3": "CalloutDecline",
                        "9": "QualifiedNo"
                    }
                }

            # Handle Accepted Response
            elif "Accepted Response" in text:
                return {
                    "label": "AcceptedResponse",
                    "log": text,
                    "playPrompt": ["callflow:1167"],
                    "gosub": ["SaveCallResult", 1001, "Accept"],
                    "goto": "Goodbye"
                }

            # Handle Callout Decline
            elif "Callout Decline" in text:
                return {
                    "label": "CalloutDecline",
                    "log": text,
                    "playPrompt": ["callflow:1021"],
                    "gosub": ["SaveCallResult", 1002, "Decline"],
                    "goto": "Goodbye"
                }

            # Handle Qualified No
            elif "Qualified No" in text:
                return {
                    "label": "QualifiedNo",
                    "log": text,
                    "playPrompt": ["callflow:1266"],
                    "gosub": ["SaveCallResult", 1145, "QualNo"],
                    "goto": "Goodbye"
                }

            # Handle Not Home
            elif "Employee Not Home" in text:
                return {
                    "label": "NotHome",
                    "log": text,
                    "playPrompt": ["callflow:1017"],
                    "gosub": ["SaveCallResult", 1006, "NotHome"],
                    "goto": "Goodbye"
                }

            # Handle Goodbye
            elif "Goodbye" in text:
                return {
                    "label": "Goodbye",
                    "log": text,
                    "playPrompt": ["callflow:1029"],
                    "nobarge": "1",
                    "goto": "Disconnect"
                }

            # Handle decision points
            elif node.node_type == NodeType.RHOMBUS:
                out_edges = [e for e in edges if e.from_id == node.id]
                branches = {}
                valid_choices = []
                
                for edge in out_edges:
                    if edge.label:
                        if edge.label == "yes":
                            branches["1"] = self._format_label(edge.to_id)
                            valid_choices.append("1")
                        elif edge.label == "no":
                            branches["2"] = self._format_label(edge.to_id)
                            valid_choices.append("2")
                        elif "retry" in edge.label.lower():
                            branches["error"] = self._format_label(edge.to_id)
                        elif "-" in edge.label:
                            digit = edge.label.split("-")[0].strip()
                            branches[digit] = self._format_label(edge.to_id)
                            valid_choices.append(digit)
                
                if branches:
                    node_config["getDigits"] = {
                        "numDigits": 1,
                        "maxTries": 3,
                        "validChoices": "|".join(valid_choices) if valid_choices else None,
                        "errorPrompt": "callflow:1009",
                        "timeoutPrompt": "callflow:1010"
                    }
                    node_config["branch"] = branches
                    
                return node_config

            return node_config

        except Exception as e:
            logger.error(f"Error processing node {node.id}: {str(e)}")
            return None

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