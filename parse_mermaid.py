import re
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

class NodeType(Enum):
    NORMAL = "normal"         # []
    ROUND = "round"          # ()
    STADIUM = "stadium"      # ([])
    SUBROUTINE = "subroutine"# [[]]
    CYLINDRICAL = "cylindrical" # [()]
    CIRCLE = "circle"        # (())
    ASYMMETRIC = "asymmetric"# >]
    RHOMBUS = "rhombus"     # {}
    HEXAGON = "hexagon"     # {{}}

@dataclass
class Node:
    id: str
    raw_text: str
    node_type: NodeType
    style_classes: List[str]
    subgraph: Optional[str] = None
    
@dataclass
class Edge:
    from_id: str
    to_id: str
    label: Optional[str] = None
    style: Optional[str] = None

class MermaidParser:
    def __init__(self):
        # Updated regex patterns for better multiline support
        self.node_patterns = {
            NodeType.NORMAL: re.compile(r'^(\w+)\s*\[((?:"[^"]*"|[^\]])*)\]', re.MULTILINE),
            NodeType.RHOMBUS: re.compile(r'^(\w+)\s*\{((?:"[^"]*"|[^\}])*)\}', re.MULTILINE),
            NodeType.CIRCLE: re.compile(r'^(\w+)\s*\(\(((?:"[^"]*"|[^\)])*)\)\)', re.MULTILINE)
        }
        
        self.edge_pattern = re.compile(
            r'(\w+)\s*-->(?:\|((?:"[^"]*"|[^|])*)\|)?\s*(\w+)'
        )
        
        self.subgraph_pattern = re.compile(
            r'^subgraph\s+(\w+)(?:\s*\[([^\]]+)\])?'
        )
        
        self.class_def_pattern = re.compile(
            r'^classDef\s+(\w+)\s+(.+)$'
        )
        
        self.class_pattern = re.compile(
            r'^class\s+(\w+)\s+(\w+)$'
        )
        
        self.end_pattern = re.compile(r'^end\s*$')

    def clean_text(self, text: str) -> str:
        """Clean node text by removing extra quotes and normalizing newlines"""
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        return text.replace('\\n', '\n').strip()

    def parse(self, mermaid_text: str) -> Dict:
        """Parses a Mermaid diagram and returns a complete data structure."""
        # Normalize line endings and clean input
        mermaid_text = mermaid_text.replace('\r\n', '\n').strip()
        lines = mermaid_text.split('\n')
        
        nodes: Dict[str, Node] = {}
        edges: List[Edge] = []
        subgraphs: Dict[str, dict] = {}
        styles: Dict[str, str] = {}
        node_classes: Dict[str, List[str]] = {}
        
        current_subgraph = None
        
        # First pass: collect all node definitions
        content = '\n'.join(lines)
        for node_type, pattern in self.node_patterns.items():
            for match in pattern.finditer(content):
                node_id = match.group(1)
                node_text = self.clean_text(match.group(2))
                nodes[node_id] = Node(
                    id=node_id,
                    raw_text=node_text,
                    node_type=node_type,
                    style_classes=node_classes.get(node_id, []),
                    subgraph=current_subgraph
                )

        # Second pass: collect all edges
        for line in lines:
            line = line.strip()
            
            # Skip empty lines, comments and node definitions
            if not line or line.startswith('%%') or any(p.match(line) for p in self.node_patterns.values()):
                continue
                
            # Process edges
            edge_matches = self.edge_pattern.finditer(line)
            for match in edge_matches:
                from_id = match.group(1)
                label = match.group(2)
                to_id = match.group(3)
                
                if label:
                    label = self.clean_text(label)
                
                edges.append(Edge(
                    from_id=from_id,
                    to_id=to_id,
                    label=label
                ))

        return {
            "nodes": nodes,
            "edges": edges,
            "subgraphs": subgraphs,
            "styles": styles
        }

def parse_mermaid(mermaid_text: str) -> Dict:
    """Wrapper function to maintain compatibility with existing code."""
    parser = MermaidParser()
    return parser.parse(mermaid_text)