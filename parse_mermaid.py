import re
from enum import Enum, auto
from typing import Dict, List, Optional, Union
from dataclasses import dataclass

class NodeType(Enum):
    START = auto()
    END = auto()
    ACTION = auto()
    DECISION = auto()
    INPUT = auto()
    TRANSFER = auto()
    SUBPROCESS = auto()

@dataclass
class Node:
    id: str
    raw_text: str
    node_type: NodeType
    style_classes: List[str] = None
    subgraph: Optional[str] = None

@dataclass
class Edge:
    from_id: str
    to_id: str
    label: Optional[str] = None
    style: Optional[str] = None

class MermaidParser:
    def __init__(self):
        # Comprehensive node type detection patterns
        self.node_patterns = {
            NodeType.START: [
                r'\bstart\b', r'\bbegin\b', r'\bentry\b', 
                r'\bfirst\b', r'\binitial\b'
            ],
            NodeType.END: [
                r'\bend\b', r'\bstop\b', r'\bdone\b', 
                r'\bterminal\b', r'\bfinish\b'
            ],
            NodeType.DECISION: [
                r'\?', r'\{.*\}', r'\bdecision\b', r'\bchoice\b', 
                r'\bif\b', r'\bwhen\b'
            ],
            NodeType.INPUT: [
                r'\binput\b', r'\benter\b', r'\bprompt\b', 
                r'\bget\b', r'\bdigits\b'
            ],
            NodeType.TRANSFER: [
                r'\btransfer\b', r'\bcall\b', r'\broute\b', 
                r'\bdispatch\b'
            ],
            NodeType.SUBPROCESS: [
                r'\bsubprocess\b', r'\bsub\b', r'\bcall\b', 
                r'\bmodule\b'
            ]
        }

        # Comprehensive regex patterns for node parsing
        self.node_type_patterns = {
            r'\["([^"]+)"\]': NodeType.ACTION,
            r'\(([^)]+)\)': NodeType.ACTION,
            r'\{([^}]+)\}': NodeType.DECISION,
            r'\(\(([^)]+)\)\)': NodeType.START,
            r'\[\[([^]]+)\]\]': NodeType.SUBPROCESS
        }

    def categorize_node(self, text: str) -> NodeType:
        """Intelligently categorize node type based on text content and patterns"""
        text_lower = text.lower()
        
        # Check specific keyword patterns first
        for node_type, patterns in self.node_patterns.items():
            if any(re.search(pattern, text_lower) for pattern in patterns):
                return node_type
        
        # Default to ACTION if no specific type detected
        return NodeType.ACTION

    def parse(self, mermaid_text: str) -> Dict:
        """Advanced parsing with flexible node and edge detection"""
        lines = [line.strip() for line in mermaid_text.split('\n') if line.strip()]
        
        nodes = {}
        edges = []
        subgraphs = {}
        styles = {}
        current_subgraph = None

        for line in lines:
            # Skip non-meaningful lines
            if not line or line.startswith('%%') or line.startswith('flowchart'):
                continue

            # Subgraph handling
            if line.startswith('subgraph'):
                subgraph_match = re.match(r'subgraph\s+(\w+)\s*(\[.*\])?', line)
                if subgraph_match:
                    current_subgraph = subgraph_match.group(1)
                    subgraphs[current_subgraph] = {
                        'id': current_subgraph,
                        'title': subgraph_match.group(2) or current_subgraph
                    }
                continue

            # End of subgraph
            if line == 'end':
                current_subgraph = None
                continue

            # Node parsing (more robust)
            node_match = None
            for pattern, node_type in self.node_type_patterns.items():
                match = re.match(r'^(\w+)' + pattern, line)
                if match:
                    node_match = match
                    break

            if node_match:
                node_id = node_match.group(1)
                text = node_match.group(2)
                
                nodes[node_id] = Node(
                    id=node_id,
                    raw_text=text,
                    node_type=self.categorize_node(text),
                    subgraph=current_subgraph
                )
            
            # Edge parsing (more comprehensive)
            edge_patterns = [
                r'^(\w+)\s*-->\s*(\w+)',  # Simple edge
                r'^(\w+)\s*--\|([^|]+)\|>\s*(\w+)',  # Edge with label
                r'^(\w+)\s*\.\.\.\s*(\w+)',  # Dotted edge
                r'^(\w+)\s*=+>\s*(\w+)'  # Thick edge
            ]

            for pattern in edge_patterns:
                edge_match = re.match(pattern, line)
                if edge_match:
                    groups = edge_match.groups()
                    if len(groups) == 2:
                        from_node, to_node = groups
                        label = None
                    else:
                        from_node, label, to_node = groups
                    
                    edges.append(Edge(
                        from_id=from_node,
                        to_id=to_node,
                        label=label
                    ))
                    break

        return {
            'nodes': nodes,
            'edges': edges,
            'subgraphs': subgraphs,
            'styles': styles
        }

def parse_mermaid(mermaid_text: str) -> Dict:
    """Wrapper function for easy access"""
    parser = MermaidParser()
    return parser.parse(mermaid_text)
