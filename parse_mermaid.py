# parse_mermaid.py
import re

# Regexes to detect:
# 1) subgraph start:   subgraph <something> or subgraph <id> [label]
# 2) subgraph end:     end
# 3) node definitions:  id, possible shape in bracket/parenthesis, or new v11.3 shape syntax id@{ shape: ???, label: ??? }
# 4) edges of various forms: A --> B, A --x B, A --o B, A -.-> B, A ==> B, A ~~~ B, etc.
#    possibly with text labels: A -- text --> B, A --|label| B

SUBGRAPH_START = re.compile(r'^(?:subgraph)\s*(\w+)?(?:\s*\[([^\]]+)\])?(?:\s*(.*))?$')
# e.g.  subgraph one
#       subgraph sId [title here]

SUBGRAPH_END = re.compile(r'^(?:end)\s*$')

# A single node definition might be:
#   id<someShape>someText
#   or the new shape syntax:   A@{ shape: diamond, label: "Decision" }
NODE_PATTERN_V11 = re.compile(
    r'^(\w+)\@\{\s*shape:\s*([\w-]+)\s*(?:,\s*label:\s*"([^"]*)")?.*?\}\s*$'
)
# e.g.  A@{ shape: diamond, label: "Decision" }

# Classic bracket-based node syntax:
#   id["text"]   id("text")   id{text}   id((text))   id```   ...
# We'll do a big inclusive pattern capturing:
NODE_PATTERN_CLASSIC = re.compile(
    r'^(\w+)\s*'
    r'(\(\((.*?)\)\)|'      # ((double circle))
    r'\(\)(.*?)|'
    r'\(\s*(.*?)\)|'        # (round edges)
    r'\[\[(.*?)\]\]|'       # [[subroutine]]
    r'\[(.*?)\]|'           # [stadium]
    r'\{(.*?)\}|'           # {rhombus}
    r'\{\{(.*?)\}\}|'       # {{hexagon}}
    r'>(.*?)\]|'            # >asym]
    r'\(?(.*?)\)?'          # fallback capturing a parenth or ...
    r')?\s*$'
)
# It's messy, but we try to capture the ID plus shape & text group.

# For edges, we handle lines that contain multiple edges (chaining).
# We'll search for edge patterns like "A -- text --> B", "B --o C", "C -->|lbl|D", "E -.-> F", etc.
# Then we split them out into separate edges (A -> B, B->C, etc.)
EDGE_SPLIT_PATTERN = re.compile(r'((?:\w+|\"[^\"]+\"|\`[^\`]+\`|\{\{[^}]+\}\}|\.{3,})(?:\s*-{1,5}[ox\.]?[>-]?|~{3,}|={1,5}[>]?)(?:\|[^|]*\|)?\s*(?:\w+|\"[^\"]+\"|\`[^\`]+\`|\{\{[^}]+\}\}))')


# Edge sub-pattern to parse from -> arrow -> to, optional label
EDGE_PATTERN = re.compile(
    # Possibly a node ID or quoted or backtick-literal, followed by arrow.
    r'^(?P<from>[^-=\s~]+)'  # from node
    r'\s*(?P<arrow>-{1,5}[ox\.]?[>-]?|~{3,}|={1,5}[>]?)(?:\|(?P<label>[^\|]+)\|)?'
    r'\s*(?P<to>.+)$'
)

def parse_mermaid(mermaid_text: str):
    """
    A more advanced parser that tries to handle subgraphs, multiple shapes,
    chaining edges, arrow styles, etc.
    Returns:
      {
        "nodes": { nodeId: { "id": ..., "text":..., "shape":..., ... }, ...},
        "edges": [ { "from": ..., "to": ..., "arrow":..., "label":...}, ... ],
        "subgraphs": [ { "id":..., "title":..., "nodes":..., "edges":..., "subgraphs":[...] }, ... ],
        "topLevelEdges": [...],  # edges not enclosed in a subgraph
        ...
      }
    """
    lines = mermaid_text.split('\n')
    root = {
        "nodes": {},
        "edges": [],
        "subgraphs": []
    }

    # We'll maintain a stack of subgraphs for nesting
    subgraph_stack = [root]

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith('%%'):
            continue  # skip empty or comment line

        # Check subgraph start
        sg_start = SUBGRAPH_START.match(line)
        if sg_start:
            sub_id = sg_start.group(1) or ""  # might be None if subgraph with no id
            sub_title = sg_start.group(2) or sg_start.group(3) or sub_id
            new_sg = {
                "id": sub_id,
                "title": sub_title.strip(),
                "nodes": {},
                "edges": [],
                "subgraphs": []
            }
            subgraph_stack[-1]["subgraphs"].append(new_sg)
            subgraph_stack.append(new_sg)
            continue

        # Check subgraph end
        sg_end = SUBGRAPH_END.match(line)
        if sg_end:
            if len(subgraph_stack) > 1:
                subgraph_stack.pop()  # end current subgraph
            continue

        # Now we see if the line declares a node
        #  - either a new shape syntax or a bracket-based node
        # We'll store it in the *current subgraph*
        sg = subgraph_stack[-1]

        new_v11 = NODE_PATTERN_V11.match(line)
        if new_v11:
            # e.g. A@{ shape: diamond, label: "Decision" }
            node_id = new_v11.group(1)
            shape = new_v11.group(2)
            text = new_v11.group(3) or node_id  # if label not provided, fallback
            sg["nodes"][node_id] = {
                "id": node_id,
                "shape": shape,
                "text": text
            }
            continue
        else:
            # Check classic bracket-based
            classic = NODE_PATTERN_CLASSIC.match(line)
            if classic:
                node_id = classic.group(1)
                # We have up to 10 capturing groups in the monstrous pattern.
                # Let's find which one is not None:
                shape_texts = classic.groups()[1:]  # skip group(0) which is the entire match, group(1) is node_id
                # we expect only one of these groups to be non-empty
                # shape_texts might look like: ( '(.*?)', None, None, None, ... ) etc.
                node_label = None
                for g in shape_texts:
                    if g and g.strip():
                        node_label = g.strip()
                        break

                # node_label might contain shape info or text
                # e.g. if the shape was [some text], node_label= "some text"
                # if shape was (some text), node_label= "some text"
                # let's guess shape by bracket type:
                # the pattern is complicated, so let's do a quick check in the original line for shape
                # e.g. if line has '[[', shape= 'subroutine', if it has '((', shape= 'doublecircle' etc.
                shape = detect_shape_from_line(line)
                # if no text found, fallback to the node_id as text
                text = node_label or node_id

                sg["nodes"][node_id] = {
                    "id": node_id,
                    "shape": shape or "",
                    "text": text
                }
                continue

        # If not a node or subgraph directive, we might have edges (possibly multiple).
        # We'll try the chaining approach.
        # e.g. "A --> B & C --> D" or "A -- text --> B -- text2 --> C"
        # We'll chunk them out with a big regex that looks for "node arrow node"
        # For each match, we parse from, arrow, label, to.
        # This won't catch sub-sub-chaining with parentheses, but it covers typical usage.

        # Gather all "node arrow node" segments from the line
        segments = EDGE_SPLIT_PATTERN.findall(line)
        if not segments:
            # If we get here, it might be a purely textual line or advanced syntax we can't parse.
            # We'll skip it. Or you can store it as "unparsed" if you want.
            continue

        # For each matched segment, parse from->to.
        for seg in segments:
            edge_match = EDGE_PATTERN.match(seg.strip())
            if edge_match:
                from_id = edge_match.group('from').strip()
                arrow = edge_match.group('arrow')
                label = edge_match.group('label')
                to_id = edge_match.group('to').strip()
                # store an edge
                sg["edges"].append({
                    "from": from_id,
                    "to": to_id,
                    "arrow": arrow,
                    "label": label
                })

    return root


def detect_shape_from_line(line:str)->str:
    """
    A quick heuristic to guess shape type from the bracket symbols we see.
    For advanced shapes, we do a partial guess. 
    E.g. '((something))' => 'doublecircle', '{something}' => 'diamond', etc.
    """
    if '@{' in line:
        # The new shape syntax is handled in a separate regex, so if we get here, it might be just leftover
        return ''
    if '[[' in line:
        return 'subroutine'
    if '(((' in line:
        return 'doublecircle'
    if '[(' in line:
        return 'cylinder'
    if '((' in line:
        return 'doublecircle'
    if '([' in line:
        return 'stadium'
    if '[/' in line or '\]' in line:
        return 'trapezoid'
    if '[[[' in line:
        return 'multi'
    if '{(' in line:
        return 'hexagon'
    if '{{' in line:
        return 'hexagon'
    if '}}' in line:
        return 'hexagon'
    if '>' in line:
        return 'asymmetric'
    if '{' in line and '}' in line:
        return 'diamond'
    if '(' in line and ')' in line:
        return 'roundedges'
    if '[' in line and ']' in line:
        return 'rectangle'
    # fallback
    return ''
