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
        self.initialize_patterns()

    def initialize_patterns(self):
        # Node detection patterns
        self.node_types = {
            NodeType.START: [r'\bstart\b', r'\bbegin\b', r'\bentry\b'],
            NodeType.END: [r'\bend\b', r'\bstop\b', r'\bhangup\b'],
            NodeType.DECISION: [r'\?', r'\bif\b', r'\bpress\b', r'\bselect\b'],
            NodeType.INPUT: [r'\binput\b', r'\benter\b', r'\bpin\b'],
            NodeType.TRANSFER: [r'\btransfer\b', r'\bconnect\b'],
            NodeType.PROMPT: [r'\bplay\b', r'\bspeak\b', r'\bmessage\b'],
            NodeType.ERROR: [r'\berror\b', r'\binvalid\b', r'\bretry\b']
        }

        # Connection patterns
        self.connection_patterns = {
            r'-->': 'normal',
            r'-->\|.*?\|': 'labeled',
            r'-\.-?>': 'dotted',
            r'==+>': 'thick'
        }

    def parse(self, mermaid_text: str) -> Dict:
        """Parse Mermaid diagram text into structured format"""
        lines = self._clean_lines(mermaid_text)
        
        result = {
            'nodes': {},
            'edges': [],
            'subgraphs': {},
            'metadata': {
                'direction': self._get_direction(lines),
                'styles': {}
            }
        }

        current_subgraph = None
        for line in lines:
            if self._is_subgraph_start(line):
                current_subgraph = self._parse_subgraph_header(line)
                result['subgraphs'][current_subgraph] = {'nodes': set()}
            elif line == 'end':
                current_subgraph = None
            elif '-->' in line:
                edge = self._parse_edge(line)
                if edge:
                    result['edges'].append(edge)
            elif self._is_node_definition(line):
                node_id, node = self._parse_node(line)
                if node_id:
                    result['nodes'][node_id] = node
                    if current_subgraph:
                        result['subgraphs'][current_subgraph]['nodes'].add(node_id)
            elif line.startswith(('style', 'classDef')):
                self._parse_style(line, result['metadata']['styles'])

        return result

    def _clean_lines(self, text: str) -> List[str]:
        """Clean and normalize input lines"""
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line and not line.startswith('%%'):
                lines.append(line)
        return lines

    def _get_direction(self, lines: List[str]) -> str:
        """Extract flowchart direction"""
        for line in lines:
            if line.startswith(('flowchart', 'graph')):
                parts = line.split()
                if len(parts) > 1:
                    return parts[1]
        return 'TD'

    def _is_subgraph_start(self, line: str) -> bool:
        """Check if line starts a subgraph"""
        return line.startswith('subgraph')

    def _parse_subgraph_header(self, line: str) -> str:
        """Parse subgraph header line"""
        match = re.match(r'subgraph\s+(\w+)(?:\s*\[(.*?)\])?', line)
        return match.group(1) if match else None

    def _is_node_definition(self, line: str) -> bool:
        """Check if line defines a node"""
        return bool(re.match(r'^\w+\s*[\[\{\(]', line))

    def _parse_node(self, line: str) -> Tuple[Optional[str], Optional[Node]]:
        """Parse node definition with enhanced syntax handling"""
        node_match = re.match(r'^(\w+)\s*([\[\{\(])(.*?)([\]\}\)])', line)
        if not node_match:
            return None, None

        node_id, open_bracket, content, close_bracket = node_match.groups()
        node_type = self._determine_node_type(content, open_bracket)
        
        return node_id, Node(
            id=node_id,
            raw_text=content.strip('"\''),
            node_type=node_type
        )

    def _parse_edge(self, line: str) -> Optional[Edge]:
        """Parse edge definition with enhanced label handling"""
        base_pattern = r'(\w+)\s*-->'
        
        # Check for labeled edge
        label_match = re.match(f'{base_pattern}\s*\|(.*?)\|\s*(\w+)', line)
        if label_match:
            from_id, label, to_id = label_match.groups()
            return Edge(from_id=from_id, to_id=to_id, label=label.strip('"\''))
        
        # Check for simple edge
        simple_match = re.match(f'{base_pattern}\s*(\w+)', line)
        if simple_match:
            from_id, to_id = simple_match.groups()
            return Edge(from_id=from_id, to_id=to_id)
        
        return None

    def _parse_style(self, line: str, styles: Dict) -> None:
        """Parse style definitions"""
        style_match = re.match(r'(?:style|classDef)\s+(\w+)\s+(.*?)$', line)
        if style_match:
            class_name, style_def = style_match.groups()
            styles[class_name] = self._parse_style_attributes(style_def)

    def _parse_style_attributes(self, style_def: str) -> Dict[str, str]:
        """Parse CSS-style attributes"""
        attrs = {}
        for part in style_def.split(','):
            if ':' in part:
                key, value = part.split(':', 1)
                attrs[key.strip()] = value.strip()
        return attrs

    def _determine_node_type(self, content: str, bracket: str) -> NodeType:
        """Determine node type from content and bracket style"""
        content_lower = content.lower()
        
        # Check bracket-based type first
        if bracket == '{':
            return NodeType.DECISION
        
        # Check content patterns
        for node_type, patterns in self.node_types.items():
            if any(re.search(pattern, content_lower) for pattern in patterns):
                return node_type
        
        return NodeType.ACTION

def parse_mermaid(mermaid_text: str) -> Dict:
    """Convenience wrapper for parsing Mermaid diagrams"""
    parser = MermaidParser()
    try:
        return parser.parse(mermaid_text)
    except Exception as e:
        raise ValueError(f"Failed to parse Mermaid diagram: {str(e)}")