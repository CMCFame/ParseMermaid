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
        # Simpler, proven regex patterns
        self.node_patterns = {
            NodeType.NORMAL: re.compile(r'^(\w+)\s*\["([^"]+)"\]'),
            NodeType.RHOMBUS: re.compile(r'^(\w+)\s*\{"([^"]+)"\}'),
            NodeType.CIRCLE: re.compile(r'^(\w+)\s*\(\("([^"]+)"\)\)')
        }
        
        self.edge_pattern = re.compile(
            r'(\w+)\s*-->\s*(?:\|([^|]*)\|)?\s*(\w+)'
        )

    def parse(self, mermaid_text: str) -> Dict:
        """
        Parses a Mermaid diagram and returns a complete data structure.
        """
        lines = mermaid_text.split('\n')
        
        nodes: Dict[str, Node] = {}
        edges: List[Edge] = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('%%') or line.startswith('flowchart'):
                continue

            # Process nodes
            node_found = False
            for node_type, pattern in self.node_patterns.items():
                match = pattern.match(line)
                if match:
                    node_id = match.group(1)
                    raw_text = match.group(2)
                    nodes[node_id] = Node(
                        id=node_id,
                        raw_text=raw_text,
                        node_type=node_type,
                        style_classes=[]
                    )
                    node_found = True
                    break
            if node_found:
                continue

            # Process edges
            edge_matches = self.edge_pattern.finditer(line)
            for match in edge_matches:
                from_id = match.group(1)
                label = match.group(2)
                to_id = match.group(3)
                
                edges.append(Edge(
                    from_id=from_id,
                    to_id=to_id,
                    label=label.strip() if label else None
                ))

        return {
            "nodes": nodes,
            "edges": edges,
            "subgraphs": {},
            "styles": {}
        }

def parse_mermaid(mermaid_text: str) -> Dict:
    """
    Wrapper function to maintain compatibility with existing code.
    """
    parser = MermaidParser()
    return parser.parse(mermaid_text)