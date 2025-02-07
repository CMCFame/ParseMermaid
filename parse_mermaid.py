# parse_mermaid.py

import re

def parse_mermaid(mermaid_text: str):
    """
    A naive parser that extracts 'nodes' and 'edges' from a single Mermaid 'flowchart TD' diagram.
    Returns a dict: { 'nodes': {id: {...}}, 'edges': [{'from':..., 'to':..., 'label':...}, ...] }
    """
    lines = mermaid_text.split('\n')

    node_pattern = re.compile(r'^(\w+)\s*(\(|\[|{)"?([^"\n]+)"?\)?')
    edge_pattern = re.compile(r'^(\w+)\s*-->\s*(?:\|([^|]+)\|)?\s*(\w+)')

    nodes = {}
    edges = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith('%%'):
            continue  # skip empty or comment lines

        # Match node definitions
        node_match = node_pattern.match(line)
        if node_match:
            node_id = node_match.group(1)
            raw_text = node_match.group(3).strip()
            nodes[node_id] = {
                'id': node_id,
                'raw_text': raw_text
            }
            continue

        # Match edge definitions
        edge_match = edge_pattern.match(line)
        if edge_match:
            from_id = edge_match.group(1)
            label = edge_match.group(2).strip() if edge_match.group(2) else None
            to_id = edge_match.group(3)
            edges.append({
                'from': from_id,
                'to': to_id,
                'label': label
            })

    return {"nodes": nodes, "edges": edges}
