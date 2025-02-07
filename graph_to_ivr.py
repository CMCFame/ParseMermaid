# graph_to_ivr.py
import re

AUDIO_PROMPTS = {
    "Invalid entry. Please try again": "callflow:1009",
    "Goodbye message": "callflow:1029",
}

def graph_to_ivr(parsed):
    """
    Takes the complex structure from parse_mermaid()
    and returns a single array of IVR nodes.
    We'll flatten subgraphs so the final code doesn't break.
    """
    # Flatten all subgraphs into single list of nodes & edges
    all_nodes = {}
    all_edges = []

    def visit_subgraph(sg):
        # sg has "nodes", "edges", "subgraphs"
        for nid, nd in sg["nodes"].items():
            all_nodes[nid] = nd
        for e in sg["edges"]:
            all_edges.append(e)
        for sub in sg.get("subgraphs", []):
            visit_subgraph(sub)

    visit_subgraph(parsed)  # merges everything into all_nodes, all_edges

    # Now we convert all_nodes + all_edges into an IVR array
    # We'll build a small adjacency for each node:
    adjacency = {}
    for e in all_edges:
        from_id = e["from"]
        to_id = e["to"]
        adjacency.setdefault(from_id, []).append(e)

    ivr_nodes = []

    # Insert standard "Start"
    ivr_nodes.append({
        "label": "Start",
        "maxLoop": ["Main", 3, "Problems"],
        "nobarge": "1",
        "log": "Entry point to the call flow"
    })

    visited = set()

    def is_decision(node_id):
        # If out edges have patterns like "1 - accept"
        out_e = adjacency.get(node_id, [])
        for edge in out_e:
            lbl = edge.get("label", "") or ""
            if re.match(r'^\d+\s*-\s*', lbl):
                return True
        return False

    # We'll build a node object for each. If we see the node text in AUDIO_PROMPTS, we use that.
    for nid, nd in all_nodes.items():
        node_label = nd["id"]
        shape = nd.get("shape", "")
        text = nd.get("text", node_label)  # fallback
        edges_out = adjacency.get(nid, [])

        node_obj = {
            "label": to_title_case(node_label),
            "log": f"Shape={shape} rawText={text}",  # store shape & text for debugging
        }

        # Decide if it's a "decision" node
        if is_decision(nid):
            # Build getDigits
            node_obj["getDigits"] = {
                "numDigits": 1,
                "maxTries": 3,
                "maxTime": 7,
                "validChoices": "",
                "errorPrompt": "callflow:1009",
                "nonePrompt": "callflow:1009"
            }
            branch_map = {}
            digit_choices = []
            for oe in edges_out:
                lbl = (oe.get("label") or "").strip()
                match = re.match(r'^(\d+)\s*-\s*(.*)', lbl)
                if match:
                    digit = match.group(1)
                    rest = match.group(2)
                    branch_map[digit] = to_title_case(oe["to"])
                    digit_choices.append(digit)
                elif re.search(r'invalid|no input', lbl, re.IGNORECASE):
                    branch_map["error"] = to_title_case(oe["to"])
                    branch_map["none"] = to_title_case(oe["to"])
                else:
                    # fallback
                    arrow_type = oe.get("arrow")
                    # we can store something else if we want
                    branch_map[lbl or arrow_type] = to_title_case(oe["to"])
            if digit_choices:
                node_obj["getDigits"]["validChoices"] = "|".join(digit_choices)
            node_obj["branch"] = branch_map

        else:
            # Not a decision node => prompt node
            # If text is in AUDIO_PROMPTS, we do that. Otherwise TTS
            audio_code = AUDIO_PROMPTS.get(text)
            if audio_code:
                node_obj["playPrompt"] = [audio_code]
            else:
                node_obj["playPrompt"] = [f"tts:{text}"]

            # If exactly 1 out edge, do goto
            if len(edges_out) == 1:
                node_obj["goto"] = to_title_case(edges_out[0]["to"])

        # If label is "Accept", "Decline", "Qualified No", etc. add gosub
        lower_lbl = node_obj["label"].lower()
        if lower_lbl == "accept":
            node_obj["gosub"] = ["SaveCallResult", 1001, "Accept"]
        elif lower_lbl == "decline":
            node_obj["gosub"] = ["SaveCallResult", 1002, "Decline"]

        ivr_nodes.append(node_obj)

    # add Problems + Goodbye
    ivr_nodes.append({
        "label": "Problems",
        "gosub": ["SaveCallResult", 1198, "Error Out"],
        "goto": "Goodbye"
    })
    ivr_nodes.append({
        "label": "Goodbye",
        "log": "Goodbye message",
        "playPrompt": ["callflow:1029"],
        "nobarge": "1",
        "goto": "hangup"
    })

    return ivr_nodes

def to_title_case(s):
    return re.sub(r'\b\w', lambda m: m.group(0).upper(), s.replace('_', ' '))
