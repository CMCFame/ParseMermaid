"""
Complete IVR transformation module with debugging
Author: DevTeam
Version: 2.0
"""
import re
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from parse_mermaid import Node, Edge, NodeType

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class NodeCategory(Enum):
    """Categories of IVR nodes"""
    WELCOME = auto()
    MENU = auto()
    INPUT = auto()
    DECISION = auto()
    RESPONSE = auto()
    MESSAGE = auto()
    HANDLER = auto()

@dataclass
class AudioPrompt:
    """Audio prompt configuration"""
    id: str
    description: str
    category: NodeCategory
    default_timeout: int = 5

class AudioPrompts:
    """Audio prompt mapping"""
    # System prompts
    WELCOME = "1001"        # Welcome message
    PIN_ENTRY = "1008"      # PIN entry prompt
    INVALID = "1009"        # Invalid input
    TIMEOUT = "1010"        # Input timeout
    ERROR = "1351"          # General error message
    
    # Menu and input prompts
    MENU = "1677"           # Main menu options
    TRANSFER = "1645"       # Transfer request
    
    # Response prompts
    ACCEPT = "1167"         # Accept response
    DECLINE = "1021"        # Decline response
    QUALIFIED = "1266"      # Qualified no
    GOODBYE = "1029"        # Goodbye message
    
    # Callout prompts
    CALLOUT = "1274"        # Callout information
    REASON = "1019"        # Callout reason
    LOCATION = "1232"      # Location information
    WAIT = "1265"          # Wait message
    NOT_HOME = "1017"      # Not home message
    AVAILABLE = "1316"     # Availability check

@dataclass
class IVRNode:
    """IVR node configuration"""
    label: str
    log: str
    prompt_ids: List[str]
    category: NodeCategory
    digit_collection: Optional[Dict] = None
    branch_logic: Optional[Dict] = None
    goto: Optional[str] = None
    retries: int = 3
    timeout: int = 5

class IVRTransformer:
    """IVR transformation engine with debugging"""
    
    def __init__(self):
        self.processed_nodes: Set[str] = set()
        self.node_map: Dict[str, Dict] = {}
        self.debug = True

    def transform(self, graph: Dict) -> List[Dict[str, Any]]:
        """Transform Mermaid graph to IVR configuration"""
        try:
            nodes = graph['nodes']
            edges = graph['edges']
            ivr_nodes = []
            
            # Build node relationships
            self.node_map = self._build_node_map(nodes, edges)
            
            # Process each node
            for node_id, node in nodes.items():
                logger.debug(f"Processing node {node_id}: {node.raw_text}")
                
                if node_id not in self.processed_nodes:
                    node_config = self._process_node(node, edges)
                    if node_config:
                        ivr_nodes.append(node_config)
                        self.processed_nodes.add(node_id)
                        logger.debug(f"Added node configuration: {node_config['label']}")
            
            # Add standard handlers
            ivr_nodes.extend(self._create_standard_handlers())
            
            return ivr_nodes
            
        except Exception as e:
            logger.error(f"Transform failed: {str(e)}")
            raise

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
        logger.debug(f"Built node map with {len(node_map)} nodes")
        return node_map

    def _process_node(self, node: Node, edges: List[Edge]) -> Optional[Dict]:
        """Process individual node with detailed error tracking"""
        try:
            text = node.raw_text.lower()
            node_config = None
            
            logger.debug(f"Processing text: {text}")

            # Welcome/Initial node
            if any(x in text for x in ["welcome", "this is an electric callout"]):
                node_config = {
                    "label": "Welcome",
                    "log": node.raw_text,
                    "playPrompt": [f"callflow:{AudioPrompts.WELCOME}"],
                    "getDigits": {
                        "numDigits": 1,
                        "maxTries": 3,
                        "validChoices": "1|3|7|9",
                        "errorPrompt": f"callflow:{AudioPrompts.INVALID}",
                        "timeoutPrompt": f"callflow:{AudioPrompts.TIMEOUT}"
                    },
                    "branch": {
                        "1": "EnterPin",
                        "3": "NeedMoreTime",
                        "7": "NotHome",
                        "9": "Welcome"
                    }
                }
            
            # PIN Entry
            elif "pin" in text:
                node_config = {
                    "label": "EnterPin",
                    "log": node.raw_text,
                    "playPrompt": [f"callflow:{AudioPrompts.PIN_ENTRY}"],
                    "getDigits": {
                        "numDigits": 4,
                        "maxTries": 3,
                        "terminator": "#",
                        "errorPrompt": f"callflow:{AudioPrompts.INVALID}",
                        "timeoutPrompt": f"callflow:{AudioPrompts.TIMEOUT}"
                    },
                    "branch": {
                        "valid": "ElectricCallout",
                        "invalid": "InvalidPin"
                    }
                }
            
            # Electric Callout
            elif "electric callout" in text:
                node_config = {
                    "label": "ElectricCallout",
                    "log": node.raw_text,
                    "playPrompt": [f"callflow:{AudioPrompts.CALLOUT}"],
                    "goto": "CalloutReason"
                }
            
            # Callout Reason
            elif "callout reason" in text:
                node_config = {
                    "label": "CalloutReason",
                    "log": node.raw_text,
                    "playPrompt": [f"callflow:{AudioPrompts.REASON}"],
                    "goto": "TroubleLocation"
                }
            
            # Trouble Location
            elif "trouble location" in text:
                node_config = {
                    "label": "TroubleLocation",
                    "log": node.raw_text,
                    "playPrompt": [f"callflow:{AudioPrompts.LOCATION}"],
                    "goto": "AvailableForCallout"
                }
            
            # Available For Callout
            elif "available for callout" in text:
                node_config = {
                    "label": "AvailableForCallout",
                    "log": node.raw_text,
                    "playPrompt": [f"callflow:{AudioPrompts.AVAILABLE}"],
                    "getDigits": {
                        "numDigits": 1,
                        "maxTries": 3,
                        "validChoices": "1|3|9",
                        "errorPrompt": f"callflow:{AudioPrompts.INVALID}",
                        "timeoutPrompt": f"callflow:{AudioPrompts.TIMEOUT}"
                    },
                    "branch": {
                        "1": "AcceptedResponse",
                        "3": "CalloutDecline",
                        "9": "QualifiedNo"
                    }
                }
            
            # Accepted Response
            elif "accepted response" in text:
                node_config = {
                    "label": "AcceptedResponse",
                    "log": node.raw_text,
                    "playPrompt": [f"callflow:{AudioPrompts.ACCEPT}"],
                    "goto": "Goodbye"
                }
            
            # Decline Response
            elif "callout decline" in text:
                node_config = {
                    "label": "CalloutDecline",
                    "log": node.raw_text,
                    "playPrompt": [f"callflow:{AudioPrompts.DECLINE}"],
                    "goto": "Goodbye"
                }
            
            # Qualified No
            elif "qualified no" in text:
                node_config = {
                    "label": "QualifiedNo",
                    "log": node.raw_text,
                    "playPrompt": [f"callflow:{AudioPrompts.QUALIFIED}"],
                    "goto": "Goodbye"
                }
            
            # Invalid Entry
            elif "invalid" in text:
                node_config = {
                    "label": "InvalidEntry",
                    "log": node.raw_text,
                    "playPrompt": [f"callflow:{AudioPrompts.INVALID}"],
                    "goto": "Welcome"
                }
            
            # Need More Time
            elif "30-second message" in text:
                node_config = {
                    "label": "NeedMoreTime",
                    "log": node.raw_text,
                    "playPrompt": [f"callflow:{AudioPrompts.WAIT}"],
                    "goto": "Welcome"
                }
            
            # Not Home
            elif "not home" in text:
                node_config = {
                    "label": "NotHome",
                    "log": node.raw_text,
                    "playPrompt": [f"callflow:{AudioPrompts.NOT_HOME}"],
                    "goto": "Goodbye"
                }

            if node_config:
                logger.debug(f"Created config for {node_config['label']}")
            else:
                logger.warning(f"No config created for text: {text}")

            return node_config
            
        except Exception as e:
            logger.error(f"Error processing node: {str(e)}")
            return None

    def _create_standard_handlers(self) -> List[Dict]:
        """Create standard error and exit handlers"""
        return [
            {
                "label": "Problems",
                "log": "Error handler",
                "playPrompt": [f"callflow:{AudioPrompts.ERROR}"],
                "goto": "Goodbye"
            },
            {
                "label": "Goodbye",
                "log": "Call completion",
                "playPrompt": [f"callflow:{AudioPrompts.GOODBYE}"],
                "goto": "Disconnect"
            }
        ]

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """Convert Mermaid graph to IVR configuration with error handling"""
    try:
        transformer = IVRTransformer()
        return transformer.transform(graph)
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        raise