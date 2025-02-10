"""
Enhanced Mermaid parser with IVR-specific functionality
"""
import re
from enum import Enum, auto
from typing import Dict, List, Optional, Union, Set, Tuple
from dataclasses import dataclass, field

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
    
    def is_interactive(self) -> bool:
        """Check if node requires user interaction"""
        return self.node_type in {NodeType.INPUT, NodeType.MENU, NodeType.DECISION}

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
        self.nodes = {}
        self.edges = []
        self.subgraphs = {}
        self._setup_patterns()

    def _setup_patterns(self):
        """Initialize regex patterns for parsing"""
        self.node_patterns = {
            # Node type identification patterns
            'start': r'\b(start|begin|entry|initial)\b',
            'end': r'\b(end|stop|done|terminate|hangup)\b',
            'decision': r'(\?|choice|if|press|select|option)',
            'input': r'\b(input|enter|prompt|get|digits|pin)\b',
            'transfer': r'\b(transfer|route|dispatch|forward|connect)\b',
            'menu': r'\b(menu|options|select|choices)\b',
            'prompt': r'\b(play|speak|announce|message)\b',
            'error': r'\b(error|fail|invalid|retry|timeout)\b'
        }

        # Node syntax patterns
        self.syntax_patterns = {
            'node': r'^(\w+)\s*(\[|\{|\()(.*?)(\]|\}|\))',
            'edge': r'(\w+)\s*(-+->)\s*(\w+)',
            'edge_label': r'\|\s*(.*?)\s*\|',
            'subgraph': r'subgraph\s+(\w+)(?:\s*\[(.*?)\])?',
            'style': r'style\s+(\w+)\s+(.*?)$',
            'class_def': r'classDef\s+(\w+)\s+(.*?)$'
        }

    def parse(self, mermaid_text: str) -> Dict:
        """Parse Mermaid diagram text into structured format"""
        self.nodes = {}
        self.edges = []
        self.subgraphs = {}
        current_subgraph = None
        
        lines = [line.strip() for line in mermaid_text.split('\n') if line.strip()]
        
        try:
            for line in lines:
                if line.startswith(('%%', 'flowchart', 'graph')):
                    continue

                if line.startswith('subgraph'):
                    current_subgraph = self._parse_subgraph(line)
                elif line == 'end':
                    current_subgraph = None
                elif '-->' in line:
                    edge = self._parse_edge(line)
                    if edge:
                        self.edges.append(edge)
                elif any(c in line for c in '[]{}()'):
                    node = self._parse_node(line)
                    if node:
                        self.nodes[node.id] = node
                        if current_subgraph:
                            node.subgraph = current_subgraph

            return self._build_output()
            
        except Exception as e:
            raise ValueError(f"Failed to parse Mermaid diagram: {str(e)}")

    def _parse_node(self, line: str) -> Optional[Node]:
        """Parse node definition with enhanced handling"""
        match = re.match(self.syntax_patterns['node'], line)
        if not match:
            return None

        node_id, open_bracket, content, close_bracket = match.groups()
        content = content.strip('"\'')
        
        # Determine node type
        node_type = NodeType.DECISION if open_bracket == '{' else NodeType.ACTION
        for type_name, pattern in self.node_patterns.items():
            if re.search(pattern, content.lower()):
                node_type = getattr(NodeType, type_name.upper())
                break

        return Node(
            id=node_id,
            raw_text=content,
            node_type=node_type
        )

    def _parse_edge(self, line: str) -> Optional[Edge]:
        """Parse edge definition with improved label handling"""
        edge_match = re.match(self.syntax_patterns['edge'], line)
        if not edge_match:
            return None

        from_id, arrow_type, to_id = edge_match.groups()
        label = None

        # Extract label if present
        label_match = re.search(self.syntax_patterns['edge_label'], line)
        if label_match:
            label = label_match.group(1).strip('"\'')

        return Edge(
            from_id=from_id,
            to_id=to_id,
            label=label,
            style=arrow_type
        )

    def _parse_subgraph(self, line: str) -> Optional[str]:
        """Parse subgraph definition"""
        match = re.match(self.syntax_patterns['subgraph'], line)
        if match:
            subgraph_id, title = match.groups()
            self.subgraphs[subgraph_id] = {
                'id': subgraph_id,
                'title': title or subgraph_id,
                'nodes': set()
            }
            return subgraph_id
        return None

    def _build_output(self) -> Dict:
        """Build final output structure"""
        return {
            'nodes': self.nodes,
            'edges': self.edges,
            'subgraphs': self.subgraphs,
            'metadata': {
                'direction': 'TD',
                'styles': {}
            }
        }

def parse_mermaid(mermaid_text: str) -> Dict:
    """Convenience wrapper for parsing Mermaid diagrams"""
    parser = MermaidParser()
    return parser.parse(mermaid_text)