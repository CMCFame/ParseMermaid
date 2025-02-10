"""
Enhanced Mermaid parser with improved IVR-specific functionality
"""
import re
from enum import Enum, auto
from typing import Dict, List, Optional, Union, Set
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

class NodeType(Enum):
    """Extended node types for IVR flows"""
    START = auto()
    END = auto()
    ACTION = auto()
    DECISION = auto()
    INPUT = auto()
    TRANSFER = auto()
    SUBPROCESS = auto()
    MENU = auto()
    PROMPT = auto()
    ERROR = auto()
    RETRY = auto()

@dataclass
class Node:
    """Enhanced node representation"""
    id: str
    raw_text: str
    node_type: NodeType
    style_classes: List[str] = field(default_factory=list)
    subgraph: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)

@dataclass
class Edge:
    """Enhanced edge representation"""
    from_id: str
    to_id: str
    label: Optional[str] = None
    style: Optional[str] = None
    condition: Optional[str] = None

class MermaidParser:
    """Enhanced Mermaid parser with IVR focus"""
    
    def __init__(self):
        self.node_patterns = {
            # Node type detection patterns
            NodeType.START: [
                r'\b(start|begin|entry)\b',
                r'welcome',
                r'initial'
            ],
            NodeType.END: [
                r'\b(end|stop|exit)\b',
                r'goodbye',
                r'terminate'
            ],
            NodeType.DECISION: [
                r'\{([^}]+)\}',  # Diamond nodes
                r'(yes|no)',
                r'(press|option|select)\s*\d+',
                r'if|then|else'
            ],
            NodeType.INPUT: [
                r'(enter|input|collect)\s*\w+',
                r'get\s*(pin|digits)',
                r'prompt\s*for'
            ],
            NodeType.TRANSFER: [
                r'(transfer|forward|connect)',
                r'agent|operator|dispatch'
            ],
            NodeType.MENU: [
                r'menu',
                r'options',
                r'select\s*from'
            ],
            NodeType.PROMPT: [
                r'(play|speak|announce)',
                r'message',
                r'prompt'
            ],
            NodeType.ERROR: [
                r'(error|invalid|fail)',
                r'retry',
                r'exceeded'
            ]
        }

        self.edge_patterns = {
            'simple': r'([\w\d]+)\s*-->\s*([\w\d]+)',
            'labeled': r'([\w\d]+)\s*--([^>]+)-->\s*([\w\d]+)',
            'condition': r'([\w\d]+)\s*--(.*?)\s*\|(.*?)\|\s*-->\s*([\w\d]+)'
        }

    def parse(self, mermaid_text: str) -> Dict:
        """Parse Mermaid diagram text into structured format"""
        lines = [line.strip() for line in mermaid_text.split('\n') if line.strip()]
        
        nodes = {}
        edges = []
        subgraphs = {}
        current_subgraph = None
        
        try:
            for line in lines:
                # Skip comments and empty lines
                if line.startswith('%') or not line:
                    continue
                
                # Handle flowchart direction
                if line.startswith(('flowchart', 'graph')):
                    continue
                
                # Handle subgraphs
                if line.startswith('subgraph'):
                    subgraph_match = re.match(r'subgraph\s+(\w+)(?:\s*\[(.*?)\])?', line)
                    if subgraph_match:
                        current_subgraph = subgraph_match.group(1)
                        subgraphs[current_subgraph] = {
                            'id': current_subgraph,
                            'title': subgraph_match.group(2) or current_subgraph,
                            'nodes': set()
                        }
                    continue
                
                if line == 'end':
                    current_subgraph = None
                    continue
                
                # Try to parse node definition
                node = self._parse_node_definition(line)
                if node:
                    nodes[node.id] = node
                    if current_subgraph:
                        subgraphs[current_subgraph]['nodes'].add(node.id)
                    continue
                
                # Try to parse edge definition
                edge = self._parse_edge_definition(line)
                if edge:
                    edges.append(edge)
                    continue
            
            return {
                'nodes': nodes,
                'edges': edges,
                'subgraphs': subgraphs
            }
            
        except Exception as e:
            logger.error(f"Failed to parse Mermaid diagram: {str(e)}")
            raise

    def _parse_node_definition(self, line: str) -> Optional[Node]:
        """Parse node definition with enhanced pattern matching"""
        node_patterns = [
            # Standard node
            r'^\s*(\w+)\s*\[(.*?)\]',
            # Decision node
            r'^\s*(\w+)\s*\{(.*?)\}',
            # Circle node
            r'^\s*(\w+)\s*\((.*?)\)',
            # Rounded rectangle
            r'^\s*(\w+)\s*\[\((.*?)\)\]'
        ]
        
        for pattern in node_patterns:
            match = re.match(pattern, line)
            if match:
                node_id, text = match.groups()
                node_type = self._determine_node_type(text)
                return Node(id=node_id, raw_text=text, node_type=node_type)
        
        return None

    def _parse_edge_definition(self, line: str) -> Optional[Edge]:
        """Parse edge definition with support for conditions"""
        for pattern_name, pattern in self.edge_patterns.items():
            match = re.match(pattern, line)
            if match:
                if pattern_name == 'simple':
                    return Edge(from_id=match.group(1), to_id=match.group(2))
                elif pattern_name == 'labeled':
                    return Edge(
                        from_id=match.group(1),
                        to_id=match.group(3),
                        label=match.group(2).strip()
                    )
                elif pattern_name == 'condition':
                    return Edge(
                        from_id=match.group(1),
                        to_id=match.group(4),
                        label=match.group(2).strip(),
                        condition=match.group(3).strip()
                    )
        return None

    def _determine_node_type(self, text: str) -> NodeType:
        """Determine node type from text content"""
        text_lower = text.lower()
        
        for node_type, patterns in self.node_patterns.items():
            if any(re.search(pattern, text_lower) for pattern in patterns):
                return node_type
        
        # Default to ACTION if no specific type matches
        return NodeType.ACTION

def parse_mermaid(mermaid_text: str) -> Dict:
    """Convenience wrapper for parsing Mermaid diagrams"""
    parser = MermaidParser()
    return parser.parse(mermaid_text)