# graph_to_ivr.py
import re

def graph_to_ivr(graph):
    nodes_dict = graph['nodes']
    edges = graph['edges']

    ivr_nodes = []

    def out_edges(node_id):
        return [e for e in edges if e['from'] == node_id]

    def is_decision_node(node_id):
        for e in out_edges(node_id):
            # FIX: ensure label is a string
            label = e.get('label') or ''
            # e.g. "1 - accept"
            if re.match(r'^\d+\s*-\s*', label):
                return True
        return False

    for node_id, node_data in nodes_dict.items():
        node_label = to_title_case(node_id)
        raw_text = node_data['raw_text']

        ivr_node = {
            "label": node_label,
            "log": raw_text,     
            "playPrompt": parse_text_to_prompt(raw_text),
        }

        o_edges = out_edges(node_id)

        if is_decision_node(node_id):
            ivr_node["getDigits"] = {
                "numDigits": 1,
                "maxTries": 3,
                "maxTime": 7,
                "validChoices": "",
                "errorPrompt": "callflow:1009",
                "nonePrompt": "callflow:1009"
            }
            branch_map = {}
            digit_choices = []

            for oe in o_edges:
                # Another FIX: always use a string
                edge_label = (oe.get('label') or '').strip()
                match = re.match(r'^(\d+)\s*-\s*(.*)', edge_label)
                if match:
                    digit = match.group(1)
                    label_rest = match.group(2)
                    branch_map[digit] = to_title_case(oe['to'])
                    digit_choices.append(digit)
                elif re.search(r'invalid|no input', edge_label, re.IGNORECASE):
                    branch_map['error'] = to_title_case(oe['to'])
                    branch_map['none'] = to_title_case(oe['to'])
                else:
                    # fallback for non-digit label
                    branch_map[edge_label] = to_title_case(oe['to'])

            ivr_node["branch"] = branch_map
            if digit_choices:
                ivr_node["getDigits"]["validChoices"] = "|".join(digit_choices)
        else:
            # If not a decision node
            if len(o_edges) == 1:
                ivr_node["goto"] = to_title_case(o_edges[0]['to'])
            # If more edges or none, handle how you want

        ivr_nodes.append(ivr_node)

    return ivr_nodes

def parse_text_to_prompt(text):
    """A trivial approach: store TTS with line breaks replaced by spaces."""
    return f"tts:{text.replace('\\n', ' ')}"

def to_title_case(s):
    """Convert 'all_hands' -> 'All Hands' etc."""
    return re.sub(r'\b\w', lambda m: m.group(0).upper(), s.replace('_', ' '))