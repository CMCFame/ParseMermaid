"""
Enhanced IVR transformation module for exact flow reproduction
"""
import re
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from parse_mermaid import Node, Edge, NodeType

@dataclass
class AudioPrompt:
    """Audio prompt configuration"""
    id: str
    description: str
    category: str = "system"

class AudioPrompts:
    """Centralized audio prompt management"""
    
    # System prompts
    WELCOME = "1001"      # Welcome message
    PIN_ENTRY = "1008"    # PIN entry request
    INVALID = "1009"      # Invalid input
    TIMEOUT = "1010"      # Input timeout
    ERROR = "1351"        # General error
    
    # Response prompts
    ACCEPT = "1167"       # Accept response
    DECLINE = "1021"      # Decline response
    QUALIFIED = "1266"    # Qualified no response
    GOODBYE = "1029"      # Goodbye message
    
    # Callout prompts
    CALLOUT = "1274"      # Callout information
    REASON = "1019"       # Callout reason
    LOCATION = "1232"     # Location information
    WAIT = "1265"         # Wait message
    NOT_HOME = "1017"     # Not home message
    AVAILABLE = "1316"    # Availability check
    
    @classmethod
    def get_prompt(cls, name: str) -> str:
        """Get prompt ID by name"""
        return f"callflow:{getattr(cls, name.upper(), '1009')}"

class IVRNodeBuilder:
    """Builder for IVR node configurations"""
    
    @staticmethod
    def create_node(label: str, log: str, prompt_id: str, **kwargs) -> Dict:
        """Create basic IVR node"""
        node = {
            "label": label,
            "log": log,
            "playPrompt": [f"callflow:{prompt_id}"]
        }
        node.update(kwargs)
        return node

    @staticmethod
    def add_digit_collection(node: Dict, num_digits: int, valid_choices: str = None, 
                           max_tries: int = 3) -> Dict:
        """Add digit collection configuration"""
        digit_config = {
            "numDigits": num_digits,
            "maxTries": max_tries,
            "errorPrompt": "callflow:1009"
        }
        if valid_choices:
            digit_config["validChoices"] = valid_choices
        node["getDigits"] = digit_config
        return node

class IVRTransformer:
    """Enhanced IVR transformation engine"""
    
    def __init__(self):
        self.node_map = {}
        self.processed_nodes = set()
        self.builder = IVRNodeBuilder()

    def transform(self, graph: Dict) -> List[Dict[str, Any]]:
        """Transform complete graph into IVR nodes"""
        nodes = graph['nodes']
        edges = graph['edges']
        ivr_nodes = []
        
        # Build node map
        self.node_map = self._build_node_map(nodes, edges)
        
        # Process each node type
        for node_id, node in nodes.items():
            node_config = None
            
            # Welcome/Start node
            if "Welcome" in node.raw_text:
                node_config = self.builder.create_node(
                    "Welcome",
                    "Initial greeting and menu",
                    AudioPrompts.WELCOME
                )
                self.builder.add_digit_collection(
                    node_config,
                    num_digits=1,
                    valid_choices="1|3|7|9"
                )
                node_config["branch"] = {
                    "1": "EnterPin",
                    "3": "NeedMoreTime",
                    "7": "NotHome",
                    "9": "Welcome"
                }
            
            # PIN Entry node
            elif "PIN" in node.raw_text:
                node_config = self.builder.create_node(
                    "EnterPin",
                    "PIN entry prompt",
                    AudioPrompts.PIN_ENTRY
                )
                self.builder.add_digit_collection(
                    node_config,
                    num_digits=4,
                    max_tries=3
                )
                node_config["getDigits"]["terminator"] = "#"
                node_config["branch"] = {
                    "valid": "ElectricCallout",
                    "invalid": "InvalidPin"
                }
            
            # Electric Callout node
            elif "Electric Callout" in node.raw_text:
                node_config = self.builder.create_node(
                    "ElectricCallout",
                    "Electric callout information",
                    AudioPrompts.CALLOUT,
                    goto="CalloutReason"
                )
            
            # Callout Reason node
            elif "Callout Reason" in node.raw_text:
                node_config = self.builder.create_node(
                    "CalloutReason",
                    "Callout reason message",
                    AudioPrompts.REASON,
                    goto="TroubleLocation"
                )
            
            # Trouble Location node
            elif "Trouble Location" in node.raw_text:
                node_config = self.builder.create_node(
                    "TroubleLocation",
                    "Trouble location information",
                    AudioPrompts.LOCATION,
                    goto="CustomMessage"
                )
            
            # Available For Callout node
            elif "Available For Callout" in node.raw_text:
                node_config = self.builder.create_node(
                    "AvailableForCallout",
                    "Availability check",
                    AudioPrompts.AVAILABLE
                )
                self.builder.add_digit_collection(
                    node_config,
                    num_digits=1,
                    valid_choices="1|3|9"
                )
                node_config["branch"] = {
                    "1": "AcceptedResponse",
                    "3": "CalloutDecline",
                    "9": "QualifiedNo"
                }
            
            # Response nodes
            elif "Accepted Response" in node.raw_text:
                node_config = self.builder.create_node(
                    "AcceptedResponse",
                    "Accepted response recorded",
                    AudioPrompts.ACCEPT,
                    goto="Goodbye"
                )
            elif "Callout Decline" in node.raw_text:
                node_config = self.builder.create_node(
                    "CalloutDecline",
                    "Decline response recorded",
                    AudioPrompts.DECLINE,
                    goto="Goodbye"
                )
            elif "Qualified No" in node.raw_text:
                node_config = self.builder.create_node(
                    "QualifiedNo",
                    "Qualified no response",
                    AudioPrompts.QUALIFIED,
                    goto="Goodbye"
                )
            
            # Invalid Entry node
            elif "Invalid" in node.raw_text:
                node_config = self.builder.create_node(
                    "InvalidEntry",
                    "Invalid input handler",
                    AudioPrompts.INVALID,
                    goto="AvailableForCallout"
                )
            
            # Need More Time node
            elif "30-second message" in node.raw_text:
                node_config = self.builder.create_node(
                    "NeedMoreTime",
                    "Wait message",
                    AudioPrompts.WAIT,
                    goto="Welcome"
                )
            
            # Not Home node
            elif "Employee Not Home" in node.raw_text:
                node_config = self.builder.create_node(
                    "NotHome",
                    "Employee not home",
                    AudioPrompts.NOT_HOME,
                    goto="Goodbye"
                )

            if node_config:
                ivr_nodes.append(node_config)
        
        # Add standard handlers
        ivr_nodes.extend(self._create_standard_handlers())
        
        return ivr_nodes

    def _build_node_map(self, nodes: Dict[str, Node], edges: List[Edge]) -> Dict:
        """Build node relationship map"""
        node_map = {}
        for node_id, node in nodes.items():
            outgoing = [e for e in edges if e.from_id == node_id]
            incoming = [e for e in edges if e.to_id == node_id]
            node_map[node_id] = {
                'node': node,
                'outgoing': outgoing,
                'incoming': incoming
            }
        return node_map

    def _create_standard_handlers(self) -> List[Dict]:
        """Create standard error and exit handlers"""
        return [
            self.builder.create_node(
                "Problems",
                "Error handler",
                AudioPrompts.ERROR,
                goto="Goodbye"
            ),
            self.builder.create_node(
                "Goodbye",
                "Call completion",
                AudioPrompts.GOODBYE,
                goto="Disconnect"
            )
        ]

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """Convert Mermaid graph to IVR configuration"""
    transformer = IVRTransformer()
    return transformer.transform(graph)