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
        # Regular expressions for parsing
        self.node_regex = re.compile(r'^\s*(\w+)((?:\["|{"|"\(|\(\().*(?:\]"|"}"|"\)|\)\)))')
        self.edge_regex = re.compile(r'^\s*(\w+)\s*--?>(?:\|"([^"]*)")?\|\s*(\w+)')
        self.text_extract_regex = re.compile(r'(?:\["|\{"|\(\()(.*?)(?:"\]|"}|"\)|"\)\))')

    def parse(self, mermaid_text: str) -> Dict:
        """Parse Mermaid flowchart text into a structured format."""
        lines = mermaid_text.strip().split('\n')
        nodes = {}
        edges = []

        for line in lines:
            if line.strip().startswith('flowchart'):
                continue

            # Try to match node definition
            node_match = self.node_regex.match(line)
            if node_match:
                node_id, node_def = node_match.groups()
                text_match = self.text_extract_regex.search(node_def)
                if text_match:
                    raw_text = text_match.group(1)
                    node_type = self._determine_node_type(node_def)
                    nodes[node_id] = {
                        'id': node_id,
                        'raw_text': raw_text,
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

    def _determine_node_type(self, node_def: str) -> str:
        """Determine the type of node based on its definition."""
        if '{"' in node_def:
            return 'decision'
        elif '((' in node_def:
            return 'end'
        return 'normal'

def parse_mermaid(mermaid_text: str) -> Dict:
    """Wrapper function to maintain compatibility with existing code."""
    parser = MermaidParser()
    return parser.parse(mermaid_text)