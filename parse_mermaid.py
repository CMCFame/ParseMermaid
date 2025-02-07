import re
from typing import Dict, List, Optional, Union
from dataclasses import dataclass

@dataclass
class Node:
    id: str
    raw_text: str
    node_type: str  # 'normal', 'decision', 'end'
    edges: List['Edge'] = None

    def __post_init__(self):
        if self.edges is None:
            self.edges = []

@dataclass
class Edge:
    source: str
    target: str
    label: Optional[str] = None

class MermaidParser:
    def __init__(self):
        # Updated regex patterns to handle multi-line content
        self.node_regex = re.compile(r'^\s*(\w+)\s*(\["|{"|"\(|\(\()(.*?)("\]|"}"|"\)|"\))"?\s*$', re.DOTALL)
        self.edge_regex = re.compile(r'^\s*(\w+)\s*--?>(?:\|"([^"]*)"\|)?\s*(\w+)')

    def parse(self, mermaid_text: str) -> Dict:
        """Parse Mermaid flowchart text into a structured format."""
        # Preprocess to handle multiline nodes
        lines = []
        current_line = []
        
        for line in mermaid_text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('flowchart'):
                continue
                
            # Count quotes to determine if node definition is complete
            quotes = line.count('"')
            current_line.append(line)
            
            if quotes % 2 == 0:  # Complete node or edge definition
                lines.append(' '.join(current_line))
                current_line = []

        nodes = {}
        edges = []

        # Process lines
        for line in lines:
            # Try to match node definition
            node_match = self.node_regex.match(line)
            if node_match:
                node_id, start_delim, text, end_delim = node_match.groups()
                node_type = self._determine_node_type(start_delim)
                nodes[node_id] = {
                    'id': node_id,
                    'raw_text': text.replace('\\n', '\n').strip(),
                    'node_type': node_type
                }
                continue

            # Try to match edge definition
            edge_match = self.edge_regex.match(line)
            if edge_match:
                source, label, target = edge_match.groups()
                edges.append({
                    'from': source,
                    'to': target,
                    'label': label.strip() if label else None
                })

        return {
            'nodes': nodes,
            'edges': edges
        }

    def _determine_node_type(self, delimiter: str) -> str:
        """Determine the type of node based on its delimiter."""
        if '{' in delimiter:
            return 'decision'
        elif '(' in delimiter:
            return 'end'
        return 'normal'

    def _clean_text(self, text: str) -> str:
        """Clean node text content."""
        return text.replace('\\n', '\n').strip()

def parse_mermaid(mermaid_text: str) -> Dict:
    """Wrapper function to maintain compatibility with existing code."""
    parser = MermaidParser()
    return parser.parse(mermaid_text)