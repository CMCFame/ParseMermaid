"""
Local converter for Mermaid flowcharts to IVR configuration.
This module parses Mermaid code and generates an IVR configuration
in a Python dictionary format, and extracts diagram notes.
"""

import re
import json
from typing import List, Dict, Any, Optional, Set, Tuple

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
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.connections: List[Dict[str, str]] = []
        self.subgraphs: List[Dict[str, Any]] = []
        self.notes: List[str] = []

    def convert(self, mermaid_code: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        self.parseGraph(mermaid_code)
        ivr_flow = self.generateIVRFlow()
        return ivr_flow, self.notes

    def parseGraph(self, code: str) -> None:
        lines = [line.strip() for line in code.splitlines() if line.strip()]
        currentSubgraph = None

        for line in lines:
            if line.startswith('%%'):
                continue
            if line.startswith('flowchart'):
                continue

            # Capture notes for display in the UI
            if 'Notes:' in line or 'Note:' in line:
                self.notes.append(line)

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
        pattern = r'^(\w+)\s*([\[\(\{])(?:")?(.*?)(?:")?\s*([\]\)\}])$'
        match = re.match(pattern, line)
        if not match:
            return
        node_id, openBracket, content, closeBracket = match.groups()
        node_type = self.getNodeType(openBracket, closeBracket)
        label = re.sub(r'<br\s*/?>', '\n', content)
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
        pattern = r'^(\w+)\s*-->\s*(?:\|([^|]+)\|\s*)?(.+)$'
        match = re.match(pattern, line)
        if not match:
            return
        source, label, target = match.groups()
        source = source.strip()
        target = target.strip()
        label = label.strip() if label else ""
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
        pattern = r'^(\w+)\s*([\[\(\{])(?:")?(.*?)(?:")?\s*([\]\)\}])$'
        match = re.match(pattern, nodeStr)
        if not match:
            return nodeStr
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
        return {'id': sub_id, 'title': title.strip() if title else sub_id, 'direction': None, 'nodes': []}

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
        if bracket == '[': return 'process'
        elif bracket == '(': return 'subroutine' if len(openBracket) == 2 else 'terminal'
        elif bracket == '{': return 'decision'
        else: return 'process'

    def generateIVRFlow(self) -> List[Dict[str, Any]]:
        ivrFlow: List[Dict[str, Any]] = []
        processed: Set[str] = set()
        startNodes = self.findStartNodes()
        for node_id in startNodes:
            self.processNode(node_id, ivrFlow, processed)
        for node_id in self.nodes.keys():
            self.processNode(node_id, ivrFlow, processed)
        ivrFlow.append(self.createErrorHandlers())
        return ivrFlow

    def processNode(self, node_id: str, ivrFlow: List[Dict[str, Any]], processed: Set[str]) -> None:
        if node_id in processed: return
        processed.add(node_id)
        node = self.nodes.get(node_id)
        if not node: return
        outgoing = [conn for conn in self.connections if conn['source'] == node_id]
        node['connections'] = outgoing
        ivrNode = self.createIVRNode(node)
        ivrFlow.append(ivrNode)
        for conn in outgoing:
            self.processNode(conn['target'], ivrFlow, processed)

    def createIVRNode(self, node: Dict[str, Any]) -> Dict[str, Any]:
        base = {'label': node['id'], 'log': node['label'].replace('\n', ' ')}
        if node.get('isDecision'):
            return self.createDecisionNode(node, base)
        ivrNode = {**base, 'playPrompt': f"callflow:{node['id']}"}
        if len(node.get('connections', [])) == 1:
            ivrNode['goto'] = node['connections'][0]['target']
        return ivrNode

    def createDecisionNode(self, node: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
        branch = {}
        validChoices = []
        error_target = 'Problems'
        timeout_target = 'Problems'

        for conn in node.get('connections', []):
            label = conn.get('label', '').lower()
            target = conn.get('target')

            digit_match = re.search(r'^\s*(\d+)', label)
            
            if digit_match:
                choice = digit_match.group(1)
                if choice not in branch:
                    branch[choice] = target
                    validChoices.append(choice)
            elif 'yes' in label:
                if '1' not in branch: branch['1'] = target; validChoices.append('1')
            elif 'no' in label:
                if '2' not in branch: branch['2'] = target; validChoices.append('2')
            elif 'invalid' in label or 'retry' in label:
                error_target = target
            elif 'no input' in label or 'timeout' in label:
                timeout_target = target
        
        branch.setdefault('error', error_target)
        branch.setdefault('none', timeout_target)
        validChoices = sorted(list(set(validChoices)))

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
        return {'label': 'Problems', 'nobarge': '1', 'playLog': "I'm sorry you are having problems.", 'playPrompt': 'callflow:1351', 'goto': 'hangup'}

    def findStartNodes(self) -> List[str]:
        incoming = {conn['target'] for conn in self.connections}
        return [node_id for node_id in self.nodes if node_id not in incoming]

def convert_mermaid_to_ivr(mermaid_code: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Convert Mermaid code to IVR configuration.
    Returns a tuple containing:
    - ivr_flow: A list of python dictionaries representing the flow.
    - notes: A list of strings containing extracted notes.
    """
    converter = MermaidIVRConverter()
    ivr_flow, notes = converter.convert(mermaid_code)
    return ivr_flow, notes