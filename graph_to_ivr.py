# graph_to_ivr.py

import re

# A small dictionary mapping certain known lines to specific callflow prompts
AUDIO_PROMPTS = {
    "Invalid entry. Please try again": "callflow:1009",
    "Goodbye message": "callflow:1029",
    # add more as needed
}

def graph_to_ivr(graph):
    nodes_dict = graph['nodes']
    edges = graph['edges']

    ivr_nodes = []

    # 1) Insert a standard "Start" node
    #    Adjust to your liking if you only want it in certain flows
    ivr_nodes.append({
        "label": "Start",
        "maxLoop": ["Main", 3, "Problems"],
        "nobarge": "1",
        "log": "Entry point to the call flow"
    })

    def out_edges(node_id):
        return [e for e in edges if e['from'] == node_id]

    # Decide if a node is "decision-like" by seeing if it has edges with digit-based labels
    def is_decision_node(node_id):
        for e in out_edges(node_id):
            label = e.get('label') or ''
            if re.match(r'^\d+\s*-\s*', label):
                return True
        return False

    for node_id, node_data in nodes_dict.items():
        node_label = to_title_case(node_id)
        raw_text = node_data['raw_text']

        # Build a minimal node object
        ivr_node = {
            "label": node_label,
            "log": raw_text,  # store the raw text in "log" so devs see what it was
        }

        o_edges = out_edges(node_id)

        if is_decision_node(node_id):
            # This node expects digits
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
                edge_label = (oe.get('label') or '').strip()
                # parse patterns like "1 - accept"
                match = re.match(r'^(\d+)\s*-\s*(.*)', edge_label)
                if match:
                    digit = match.group(1)
                    target_label = to_title_case(oe['to'])
                    branch_map[digit] = target_label
                    digit_choices.append(digit)
                elif re.search(r'invalid|no input', edge_label, re.IGNORECASE):
                    # interpret that as error/none
                    branch_map["error"] = to_title_case(oe['to'])
                    branch_map["none"] = to_title_case(oe['to'])
                else:
                    # fallback
                    # maybe store branch_map[edge_label] = ...
                    branch_map[edge_label] = to_title_case(oe['to'])

            ivr_node["branch"] = branch_map
            if digit_choices:
                ivr_node["getDigits"]["validChoices"] = "|".join(digit_choices)

            # If there's only one outgoing edge, you might do a default goto
            if len(o_edges) == 1:
                ivr_node["goto"] = to_title_case(o_edges[0]['to'])
        else:
            # Regular node
            # We'll attempt to map text -> audio prompt
            # If not found in our dictionary, fallback to TTS
            audio_prompt = AUDIO_PROMPTS.get(raw_text, None)
            if audio_prompt:
                ivr_node["playPrompt"] = [audio_prompt]
            else:
                ivr_node["playPrompt"] = [f"tts:{raw_text}"]
            
            # If there's exactly one edge, let's goto
            if len(o_edges) == 1:
                ivr_node["goto"] = to_title_case(o_edges[0]['to'])

        # 2) If the label is something like "Accept", add a gosub
        #    Adjust these to your flow’s naming
        if node_label.lower() == "accept":
            ivr_node["gosub"] = ["SaveCallResult", 1001, "Accept"]
        elif node_label.lower() == "decline":
            ivr_node["gosub"] = ["SaveCallResult", 1002, "Decline"]
        elif node_label.lower() == "qualified no":
            ivr_node["gosub"] = ["SaveCallResult", 1145, "QualNo"]
        # etc. add more as needed

        ivr_nodes.append(ivr_node)

    # 3) Add a standard "Problems" node
    ivr_nodes.append({
        "label": "Problems",
        "gosub": ["SaveCallResult", 1198, "Error Out"],
        "goto": "Goodbye"
    })

    # 4) Add a standard "Goodbye" node
    ivr_nodes.append({
        "label": "Goodbye",
        "log": "Goodbye message",
        "playPrompt": ["callflow:1029"],
        "nobarge": "1",
        "goto": "hangup"
    })

    return ivr_nodes

def to_title_case(s):
    """ Convert 'all_hands' => 'All Hands' etc. """
    return re.sub(r'\b\w', lambda m: m.group(0).upper(), s.replace('_', ' '))
