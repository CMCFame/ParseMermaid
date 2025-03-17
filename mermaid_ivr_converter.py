"""
Local converter for Mermaid flowcharts to IVR configuration.
This module parses Mermaid code and generates an IVR configuration
in a JavaScript module format.
"""

import re
import json
from typing import List, Dict, Any, Optional, Set

class MermaidIVRConverter:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {
            'defaultMaxTries': 3,
            'defaultMaxTime': 7,
            'defaultErrorPrompt': "callflow:1009",
            'defaultTimeout': 5000
        }
        if config:
            self.config.update(config)
        self.nodes: Dict[str, Dict[str, Any]] = {}   # Map node id -> node dict
        self.connections: List[Dict[str, str]] = []    # List of connections
        self.subgraphs: List[Dict[str, Any]] = []        # (Not used for IVR but stored)

    def convert(self, mermaid_code: str) -> List[Dict[str, Any]]:
        self.parseGraph(mermaid_code)
        ivr_flow = self.generateIVRFlow()
        return ivr_flow

    def parseGraph(self, code: str) -> None:
        lines = [line.strip() for line in code.splitlines() if line.strip()]
        currentSubgraph = None

        for line in lines:
            if line.startswith('%%'):
                continue
            if line.startswith('flowchart'):
                continue
            if line.startswith('subgraph'):
                currentSubgraph = self.parseSubgraph(line)
                if currentSubgraph:
                    self.subgraphs.append(currentSubgraph)
                continue
            if line == 'end':
                currentSubgraph = None
                continue
            if '-->' in line:
                self.parseConnection(line)
            elif line.startswith('class '):
                self.parseStyle(line)
            else:
                self.parseNode(line, currentSubgraph)

    def parseNode(self, line: str, subgraph: Optional[Dict[str, Any]]) -> None:
        # Updated regex: matches node definitions with optional quotes around the text.
        pattern = r'^(\w+)\s*([\[\(\{])(?:")?(.*?)(?:")?\s*([\]\)\}])$'
        match = re.match(pattern, line)
        if not match:
            return
        node_id, openBracket, content, closeBracket = match.groups()
        node_type = self.getNodeType(openBracket, closeBracket)
        # Replace HTML <br/> tags with newline
        label = re.sub(r'<br\s*/?>', '\n', content)
        # Remove any residual quotes
        label = label.replace('"', '').replace("'", "").strip()
        node = {
            'id': node_id,
            'type': node_type,
            'label': label,
            'subgraph': subgraph['id'] if subgraph and 'id' in subgraph else None,
            'isDecision': (node_type == 'decision'),
            'connections': []
        }
        if node_id not in self.nodes:
            self.nodes[node_id] = node

    def parseConnection(self, line: str) -> None:
        # Pattern to capture: source -->|label| target (label is optional)
        pattern = r'^(\w+)\s*-->\s*(?:\|([^|]+)\|\s*)?(.+)$'
        match = re.match(pattern, line)
        if not match:
            return
        source, label, target = match.groups()
        source = source.strip()
        target = target.strip()
        label = label.strip() if label else ""
        # Process inline node definitions if present
        if re.search(r'[\[\(\{]', source):
            source = self.parseInlineNode(source)
        if re.search(r'[\[\(\{]', target):
            target = self.parseInlineNode(target)
        self.connections.append({
            'source': source,
            'target': target,
            'label': label
        })

    def parseInlineNode(self, nodeStr: str) -> str:
        # Updated regex to allow optional quotes
        pattern = r'^(\w+)\s*([\[\(\{])(?:")?(.*?)(?:")?\s*([\]\)\}])$'
        match = re.match(pattern, nodeStr)
        if not match:
            return nodeStr  # Return as plain node ID if no inline definition
        node_id, openBracket, content, closeBracket = match.groups()
        if node_id not in self.nodes:
            node_type = self.getNodeType(openBracket, closeBracket)
            label = re.sub(r'<br\s*/?>', '\n', content)
            label = label.replace('"', '').replace("'", "").strip()
            node = {
                'id': node_id,
                'type': node_type,
                'label': label,
                'subgraph': None,
                'isDecision': (node_type == 'decision'),
                'connections': []
            }
            self.nodes[node_id] = node
        return node_id

    def parseSubgraph(self, line: str) -> Optional[Dict[str, Any]]:
        pattern = r'^subgraph\s+(\w+)\s*\[?([^\]]*)\]?$'
        match = re.match(pattern, line)
        if not match:
            return None
        sub_id, title = match.groups()
        return {
            'id': sub_id,
            'title': title.strip() if title else sub_id,
            'direction': None,
            'nodes': []
        }

    def parseStyle(self, line: str) -> None:
        pattern = r'^class\s+(\w+)\s+(\w+)'
        match = re.match(pattern, line)
        if not match:
            return
        node_id, className = match.groups()
        if node_id in self.nodes:
            self.nodes[node_id]['className'] = className

    def getNodeType(self, openBracket: str, closeBracket: str) -> str:
        bracket = openBracket[0]
        if bracket == '[':
            return 'process'
        elif bracket == '(':
            return 'subroutine' if len(openBracket) == 2 else 'terminal'
        elif bracket == '{':
            return 'decision'
        else:
            return 'process'

    def generateIVRFlow(self) -> List[Dict[str, Any]]:
        ivrFlow: List[Dict[str, Any]] = []
        processed: Set[str] = set()

        # Process start nodes first (nodes with no incoming connections)
        startNodes = self.findStartNodes()
        for node_id in startNodes:
            self.processNode(node_id, ivrFlow, processed)

        # Process any remaining nodes
        for node_id in self.nodes.keys():
            self.processNode(node_id, ivrFlow, processed)

        # Append a standard error handler node
        ivrFlow.append(self.createErrorHandlers())
        return ivrFlow

    def processNode(self, node_id: str, ivrFlow: List[Dict[str, Any]], processed: Set[str]) -> None:
        if node_id in processed:
            return
        processed.add(node_id)
        node = self.nodes.get(node_id)
        if not node:
            return
        # Gather outgoing connections from this node
        outgoing = [conn for conn in self.connections if conn['source'] == node_id]
        node['connections'] = outgoing
        ivrNode = self.createIVRNode(node)
        ivrFlow.append(ivrNode)
        for conn in outgoing:
            self.processNode(conn['target'], ivrFlow, processed)

    def createIVRNode(self, node: Dict[str, Any]) -> Dict[str, Any]:
        base = {
            'label': node['id'],
            'log': node['label'].replace('\n', ' ')
        }
        if node.get('isDecision'):
            return self.createDecisionNode(node, base)
        ivrNode = {
            **base,
            'playPrompt': f"callflow:{node['id']}"
        }
        if len(node.get('connections', [])) == 1:
            ivrNode['goto'] = node['connections'][0]['target']
        return ivrNode

    def createDecisionNode(self, node: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
        validChoices = [str(i + 1) for i in range(len(node.get('connections', [])))]
        branch = {str(idx + 1): conn['target'] for idx, conn in enumerate(node.get('connections', []))}
        branch['error'] = 'Problems'
        branch['none'] = 'Problems'
        return {
            **base,
            'playPrompt': f"callflow:{node['id']}",
            'getDigits': {
                'numDigits': 1,
                'maxTries': self.config.get('defaultMaxTries', 3),
                'maxTime': self.config.get('defaultMaxTime', 7),
                'validChoices': '|'.join(validChoices),
                'errorPrompt': self.config.get('defaultErrorPrompt', "callflow:1009"),
                'timeoutPrompt': self.config.get('defaultErrorPrompt', "callflow:1009")
            },
            'branch': branch
        }

    def createErrorHandlers(self) -> Dict[str, Any]:
        return {
            'label': 'Problems',
            'nobarge': '1',
            'playLog': "I'm sorry you are having problems.",
            'playPrompt': 'callflow:1351',
            'goto': 'hangup'
        }

    def findStartNodes(self) -> List[str]:
        incoming = {conn['target'] for conn in self.connections}
        return [node_id for node_id in self.nodes if node_id not in incoming]

def convert_mermaid_to_ivr(mermaid_code: str) -> str:
    """
    Convert Mermaid code to IVR configuration.
    Returns a JavaScript module string in the format:
    module.exports = [ ... ];
    """
    converter = MermaidIVRConverter()
    ivr_flow = converter.convert(mermaid_code)
    js_code = "module.exports = " + json.dumps(ivr_flow, indent=2) + ";"
    return js_code

# For testing the module independently:
if __name__ == "__main__":
    sample_mermaid = """flowchart TD
A["Welcome<br/>Press 1 for option"] -->|input| B{"Is it correct?"}
B -->|1| C["Proceed"]
B -->|2| A
"""
    ivr = convert_mermaid_to_ivr(sample_mermaid)
    print(ivr)
