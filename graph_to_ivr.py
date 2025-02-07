import re

def graph_to_ivr(graph):
    nodes_dict = graph['nodes']
    edges = graph['edges']

    # We'll store the final array of node objects here
    ivr_nodes = []

    # Helper: find edges from a given node
    def out_edges(node_id):
        return [e for e in edges if e['from'] == node_id]

    # A naive check for "decision node": if we see an edge label like "1 - something"
    def is_decision_node(node_id):
        for e in out_edges(node_id):
            label = e.get('label', '')
            # e.g. "1 - accept"
            if re.match(r'^\d+\s*-\s*', label):
                return True
        return False

    # We'll transform each node in alphabetical order, or just iteration order
    for node_id, node_data in nodes_dict.items():
        node_label = to_title_case(node_id)
        raw_text = node_data['raw_text']

        # Start building the dictionary
        ivr_node = {
            "label": node_label,
            "log": raw_text,     # place the raw text in "log"
            "playPrompt": parse_text_to_prompt(raw_text),
        }

        # gather outgoing edges
        o_edges = out_edges(node_id)
        if is_decision_node(node_id):
            # build getDigits + branch
            ivr_node["getDigits"] = {
                "numDigits": 1,
                "maxTries": 3,
                "maxTime": 7,
                "validChoices": "",  # we'll fill from the edges
                "errorPrompt": "callflow:1009",
                "nonePrompt": "callflow:1009"
            }
            branch_map = {}
            digit_choices = []

            for oe in o_edges:
                edge_label = (oe['label'] or "").strip()
                # check for patterns like "1 - accept"
                match = re.match(r'^(\d+)\s*-\s*(.*)', edge_label)
                if match:
                    digit = match.group(1)
                    label_rest = match.group(2)
                    branch_map[digit] = to_title_case(oe['to'])
                    digit_choices.append(digit)
                elif re.search(r'invalid|no input', edge_label, re.IGNORECASE):
                    # we'll treat that as error/none
                    branch_map['error'] = to_title_case(oe['to'])
                    branch_map['none'] = to_title_case(oe['to'])
                else:
                    # fallback if there's a label but not digit-based
                    # we could store as "branch[label] = ..."
                    # or handle differently
                    branch_map[edge_label] = to_title_case(oe['to'])

            ivr_node["branch"] = branch_map
            if digit_choices:
                ivr_node["getDigits"]["validChoices"] = "|".join(digit_choices)

        else:
            # If not a decision node, see if there's exactly one outgoing edge
            if len(o_edges) == 1:
                ivr_node["goto"] = to_title_case(o_edges[0]['to'])
            elif len(o_edges) > 1:
                # If multiple edges from a non-decision node, you might handle them differently
                pass

        ivr_nodes.append(ivr_node)

    return ivr_nodes

def parse_text_to_prompt(text):
    """
    A trivial approach: just store TTS with line breaks replaced by spaces
    In your real code, you'd likely parse or do a better mapping to 'callflow:####' files
    """
    return f"tts:{text.replace('\\n', ' ')}"

def to_title_case(s):
    """
    Convert 'all_hands' -> 'All Hands', etc.
    Very naive. 
    """
    return re.sub(r'\b\w', lambda m: m.group(0).upper(), s.replace('_', ' '))
