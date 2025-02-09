"""
Enhanced IVR transformation module with exact node matching
"""
import re
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from parse_mermaid import Node, Edge, NodeType

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class AudioPrompts:
    """Audio prompt mapping"""
    # System prompts
    WELCOME = "1001"      # Welcome message
    PIN_ENTRY = "1008"    # PIN entry request
    INVALID = "1009"      # Invalid input
    TIMEOUT = "1010"      # Input timeout
    ERROR = "1351"        # General error
    
    # Response prompts
    ACCEPT = "1167"       # Accept response
    DECLINE = "1021"      # Decline response
    QUALIFIED = "1266"    # Qualified no
    GOODBYE = "1029"      # Goodbye message
    
    # Callout prompts
    CALLOUT = "1274"      # Callout information
    REASON = "1019"       # Callout reason
    LOCATION = "1232"     # Location information
    WAIT = "1265"         # Wait message
    NOT_HOME = "1017"     # Not home message
    AVAILABLE = "1316"    # Availability check

class IVRTransformer:
    """Enhanced IVR transformation engine"""
    
    def __init__(self):
        self.processed_nodes: Set[str] = set()
        self.node_map: Dict[str, Dict] = {}

    def transform(self, graph: Dict) -> List[Dict[str, Any]]:
        """Transform Mermaid graph to IVR configuration"""
        try:
            nodes = graph['nodes']
            edges = graph['edges']
            ivr_nodes = []
            
            # Build node relationships
            self.node_map = self._build_node_map(nodes, edges)
            
            # Process nodes in order of appearance
            for node_id, node in nodes.items():
                logger.debug(f"Processing node {node_id}: {node.raw_text}")
                
                # Skip subgraph nodes (Header and Footer)
                if hasattr(node, 'subgraph') and node.subgraph:
                    continue
                
                if node_id not in self.processed_nodes:
                    node_config = self._process_node(node, edges)
                    if node_config:
                        ivr_nodes.append(node_config)
                        self.processed_nodes.add(node_id)
                        logger.debug(f"Added node configuration: {node_config['label']}")
            
            # Add standard handlers if not already present
            if not any(node.get('label') == 'Problems' for node in ivr_nodes):
                ivr_nodes.append(self._create_error_handler())
            
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
        """Process individual node with improved text matching"""
        try:
            text = node.raw_text
            node_config = None
            logger.debug(f"Processing node text: {text}")

            # Match exact node patterns from your diagram
            if "This is an electric callout" in text and "Press" in text:
                node_config = {
                    "label": "Welcome",
                    "log": text,
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

            elif "30-second message" in text:
                node_config = {
                    "label": "NeedMoreTime",
                    "log": text,
                    "playPrompt": [f"callflow:{AudioPrompts.WAIT}"],
                    "getDigits": {
                        "numDigits": 1,
                        "maxTries": 1,
                        "errorPrompt": f"callflow:{AudioPrompts.INVALID}"
                    },
                    "goto": "Welcome"
                }

            elif "Employee Not Home" in text:
                node_config = {
                    "label": "NotHome",
                    "log": text,
                    "playPrompt": [f"callflow:{AudioPrompts.NOT_HOME}"],
                    "goto": "Goodbye"
                }

            elif "Invalid Entry" in text:
                node_config = {
                    "label": "InvalidEntry",
                    "log": text,
                    "playPrompt": [f"callflow:{AudioPrompts.INVALID}"],
                    "goto": "Welcome"
                }

            elif "Electric Callout" in text and "This is an electric callout" in text:
                node_config = {
                    "label": "ElectricCallout",
                    "log": text,
                    "playPrompt": [f"callflow:{AudioPrompts.CALLOUT}"],
                    "goto": "CalloutReason"
                }

            elif "Callout Reason" in text:
                node_config = {
                    "label": "CalloutReason",
                    "log": text,
                    "playPrompt": [f"callflow:{AudioPrompts.REASON}"],
                    "goto": "TroubleLocation"
                }

            elif "Trouble Location" in text:
                node_config = {
                    "label": "TroubleLocation",
                    "log": text,
                    "playPrompt": [f"callflow:{AudioPrompts.LOCATION}"],
                    "goto": "CustomMessage"
                }

            elif "Custom Message" in text:
                node_config = {
                    "label": "CustomMessage",
                    "log": text,
                    "playPrompt": [f"callflow:{AudioPrompts.CALLOUT}"],
                    "goto": "AvailableForCallout"
                }

            elif "Available For Callout" in text:
                node_config = {
                    "label": "AvailableForCallout",
                    "log": text,
                    "playPrompt": [f"callflow:{AudioPrompts.AVAILABLE}"],
                    "getDigits": {
                        "numDigits": 1,
                        "maxTries": 3,
                        "validChoices": "1|3|9",
                        "errorPrompt": f"callflow:{AudioPrompts.INVALID}"
                    },
                    "branch": {
                        "1": "AcceptedResponse",
                        "3": "CalloutDecline",
                        "9": "QualifiedNo"
                    }
                }

            elif "Accepted Response" in text:
                node_config = {
                    "label": "AcceptedResponse",
                    "log": text,
                    "playPrompt": [f"callflow:{AudioPrompts.ACCEPT}"],
                    "goto": "Goodbye"
                }

            elif "Callout Decline" in text:
                node_config = {
                    "label": "CalloutDecline",
                    "log": text,
                    "playPrompt": [f"callflow:{AudioPrompts.DECLINE}"],
                    "goto": "Goodbye"
                }

            elif "Qualified 'No'" in text or "Qualified No" in text:
                node_config = {
                    "label": "QualifiedNo",
                    "log": text,
                    "playPrompt": [f"callflow:{AudioPrompts.QUALIFIED}"],
                    "goto": "Goodbye"
                }

            elif "Goodbye" in text:
                node_config = {
                    "label": "Goodbye",
                    "log": text,
                    "playPrompt": [f"callflow:{AudioPrompts.GOODBYE}"],
                    "goto": "Disconnect"
                }

            if node_config:
                logger.debug(f"Created config for node: {node_config['label']}")
            else:
                logger.warning(f"No matching configuration for text: {text}")

            return node_config

        except Exception as e:
            logger.error(f"Error processing node: {str(e)}")
            return None

    def _create_error_handler(self) -> Dict:
        """Create standard error handler"""
        return {
            "label": "Problems",
            "log": "Error handler",
            "playPrompt": [f"callflow:{AudioPrompts.ERROR}"],
            "goto": "Goodbye"
        }

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """Convert Mermaid graph to IVR configuration with error handling"""
    try:
        transformer = IVRTransformer()
        return transformer.transform(graph)
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        raise