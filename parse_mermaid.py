import re
from enum import Enum, auto
from typing import Dict, List, Optional
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
    subgraph: Optional[str] = None


@dataclass
class Edge:
    from_id: str
    to_id: str
    label: Optional[str] = None


class MermaidParser:
    def __init__(self):
        """Initialize Mermaid parser with regex-based node detection."""
        self.node_patterns = {
            NodeType.START: [r'\b(start|begin|entry|first|initial)\b'],
            NodeType.END: [r'\b(end|stop|done|terminal|finish)\b'],
            NodeType.DECISION: [r'\?', r'\{.*\}', r'\b(decision|choice|if|when)\b'],
            NodeType.INPUT: [r'\b(input|enter|prompt|get|digits)\b'],
            NodeType.TRANSFER: [r'\b(transfer|call|route|dispatch)\b'],
            NodeType.SUBPROCESS: [r'\b(subprocess|sub|call|module)\b']
        }

        self.node_type_patterns = {
            r'\["([^"]+)"\]': NodeType.ACTION,
            r'\(([^)]+)\)': NodeType.ACTION,
            r'\{([^}]+)\}': NodeType.DECISION,
            r'\(\(([^)]+)\)\)': NodeType.START,
            r'\[\[([^]]+)\]\]': NodeType.SUBPROCESS
        }

    def categorize_node(self, text: str) -> NodeType:
        """Categorizes node type based on regex patterns."""
        text_lower = text.lower()
        for node_type, patterns in self.node_patterns.items():
            if any(re.search(pattern, text_lower) for pattern in patterns):
                return node_type
        return NodeType.ACTION

    def parse(self, mermaid_text: str) -> Dict:
        """Parses Mermaid text into structured nodes and edges."""
        lines = [line.strip() for line in mermaid_text.split('\n') if line.strip()]
        nodes = {}
        edges = []
        subgraphs = {}
        current_subgraph = None

        for line in lines:
            if line.startswith('%%') or line.startswith('flowchart'):
                continue

            if line.startswith('subgraph'):
                match = re.match(r'subgraph\s+(\w+)\s*(\[.*\])?', line)
                if match:
                    current_subgraph = match.group(1)
                    subgraphs[current_subgraph] = {'id': current_subgraph, 'title': match.group(2) or current_subgraph}
                continue

            if line == 'end':
                current_subgraph = None
                continue

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

            edge_patterns = [
                r'^(\w+)\s*-->\s*(\w+)',  
                r'^(\w+)\s*--\|([^|]+)\|>\s*(\w+)',  
                r'^(\w+)\s*\.\.\.\s*(\w+)',  
                r'^(\w+)\s*=+>\s*(\w+)'  
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

                    edges.append(Edge(from_id=from_node, to_id=to_node, label=label))
                    break

        return {'nodes': nodes, 'edges': edges, 'subgraphs': subgraphs}

    
def parse_mermaid(mermaid_text: str) -> Dict:
    """Wrapper function for easy access to parsing functionality."""
    return MermaidParser().parse(mermaid_text)
