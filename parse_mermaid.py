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

@dataclass
class Subgraph:
    id: str
    title: str
    parent: Optional[str] = None
    style_classes: List[str] = None

class MermaidParser:
    def __init__(self):
        # Compile regex patterns for better performance
        self.node_patterns = {
            NodeType.NORMAL: re.compile(r'^(\w+)\s*\["([^"]+)"\]'),
            NodeType.ROUND: re.compile(r'^(\w+)\s*\("([^"]+)"\)'),
            NodeType.STADIUM: re.compile(r'^(\w+)\s*\(\["([^"]+)"\]\)'),
            NodeType.SUBROUTINE: re.compile(r'^(\w+)\s*\[\["([^"]+)"\]\]'),
            NodeType.CYLINDRICAL: re.compile(r'^(\w+)\s*\[\("([^"]+)"\)\]'),
            NodeType.CIRCLE: re.compile(r'^(\w+)\s*\(\("([^"]+)"\)\)'),
            NodeType.ASYMMETRIC: re.compile(r'^(\w+)\s*>\"([^"]+)"\]'),
            NodeType.RHOMBUS: re.compile(r'^(\w+)\s*\{"([^"]+)"\}'),
            NodeType.HEXAGON: re.compile(r'^(\w+)\s*\{\{"([^"]+)"\}\}')
        }
        
        self.edge_pattern = re.compile(
            r'^(\w+)\s*(-(?:-|\.)*>)\s*(?:\|([^|]+)\|)?\s*(\w+)(?:\s+(.*))?'
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

    def parse(self, mermaid_text: str) -> Dict:
        """
        Parses a Mermaid diagram and returns a complete data structure.
        """
        lines = mermaid_text.split('\n')
        
        nodes: Dict[str, Node] = {}
        edges: List[Edge] = []
        subgraphs: Dict[str, Subgraph] = {}
        styles: Dict[str, str] = {}
        node_classes: Dict[str, List[str]] = {}
        
        current_subgraph = None
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('%%'):
                continue
                
            # Process subgraph definition
            subgraph_match = self.subgraph_pattern.match(line)
            if subgraph_match:
                sg_id = subgraph_match.group(1)
                sg_title = subgraph_match.group(2) or sg_id
                subgraphs[sg_id] = Subgraph(
                    id=sg_id,
                    title=sg_title,
                    parent=current_subgraph,
                    style_classes=[]
                )
                current_subgraph = sg_id
                continue
                
            # Process subgraph end
            if self.end_pattern.match(line):
                current_subgraph = None
                continue
                
            # Process class definition
            class_def_match = self.class_def_pattern.match(line)
            if class_def_match:
                class_name = class_def_match.group(1)
                styles[class_name] = class_def_match.group(2)
                continue
                
            # Process class assignment
            class_match = self.class_pattern.match(line)
            if class_match:
                node_id = class_match.group(1)
                class_name = class_match.group(2)
                if node_id not in node_classes:
                    node_classes[node_id] = []
                node_classes[node_id].append(class_name)
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
                        style_classes=node_classes.get(node_id, []),
                        subgraph=current_subgraph
                    )
                    node_found = True
                    break
            if node_found:
                continue

            # Process edges
            edge_match = self.edge_pattern.match(line)
            if edge_match:
                from_id = edge_match.group(1)
                arrow_style = edge_match.group(2)
                label = edge_match.group(3)
                to_id = edge_match.group(4)
                style = edge_match.group(5)
                
                edges.append(Edge(
                    from_id=from_id,
                    to_id=to_id,
                    label=label.strip() if label else None,
                    style=style
                ))

        return {
            "nodes": nodes,
            "edges": edges,
            "subgraphs": subgraphs,
            "styles": styles
        }

def parse_mermaid(mermaid_text: str) -> Dict:
    """
    Wrapper function to maintain compatibility with existing code.
    """
    parser = MermaidParser()
    return parser.parse(mermaid_text)