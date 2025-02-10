"""
Custom Mermaid to IVR converter implementation
"""
from typing import Dict, List, Any
import logging
import json

class MermaidIVRConverter:
    def __init__(self, config = None):
        self.config = {
            'defaultMaxTries': 3,
            'defaultMaxTime': 7,
            'defaultErrorPrompt': 'callflow:1009',
            'defaultTimeout': 5000,
            **(config or {})
        }
        self.nodeMap = {}
        self.connections = []
        self.ivrFlow = []

    def convert_to_ivr(self, mermaid_code: str) -> str:
        """Convert Mermaid flowchart to IVR configuration"""
        try:
            ivrFlow = self.parseMermaidFlow(mermaid_code)
            nodes_str = self._format_nodes(ivrFlow)
            return f"module.exports = [\n{nodes_str}\n];"
        except Exception as e:
            logging.error(f"Custom conversion failed: {str(e)}")
            raise e

    def parseMermaidFlow(self, mermaid_code: str) -> List[Dict[str, Any]]:
        # Reset state for new conversion
        self.nodeMap = {}
        self.connections = []
        self.ivrFlow = []

        lines = mermaid_code.split('\n')
        current_subgraph = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith('%%') or line.startswith('flowchart'):
                continue

            if '-->' in line:
                self._parseConnection(line)
            elif any(c in line for c in '[]{}()'):
                self._parseNode(line)

        return self._generateIVRFlow()

    def _parseNode(self, line: str) -> None:
        node_match = None
        node_type = 'process'
        
        if '[' in line:
            node_match = line.split('[', 1)
            node_type = 'process'
        elif '{' in line:
            node_match = line.split('{', 1)
            node_type = 'decision'
        elif '(' in line:
            node_match = line.split('(', 1)
            node_type = 'rounded'

        if node_match:
            node_id = node_match[0].strip()
            content = node_match[1]
            for end_char in [']', '}', ')']:
                if end_char in content:
                    content = content.split(end_char)[0]
            content = content.replace('"', '').strip()
            
            self.nodeMap[node_id] = {
                'id': node_id,
                'type': node_type,
                'label': content.replace('<br/>', '\n').replace('<br>', '\n'),
                'connections': []
            }

    def _parseConnection(self, line: str) -> None:
        parts = line.split('-->')
        source = parts[0].strip()
        target = parts[1].strip()
        label = None

        if '|' in target:
            label_parts = target.split('|')
            label = label_parts[0].replace('"', '')
            target = label_parts[1].strip()

        if source in self.nodeMap:
            self.nodeMap[source]['connections'].append({
                'target': target,
                'label': label
            })

    def _generateIVRFlow(self) -> List[Dict[str, Any]]:
        ivr_flow = []

        for node_id, node in self.nodeMap.items():
            ivr_node = {
                'label': node_id,
                'log': node['label'].replace('\n', ' ')
            }

            if node['type'] == 'decision':
                ivr_node.update(self._createDecisionNode(node))
            else:
                ivr_node.update(self._createBasicNode(node))

            ivr_flow.append(ivr_node)

        ivr_flow.extend(self._createErrorHandlers())
        return ivr_flow

    def _createDecisionNode(self, node: Dict) -> Dict[str, Any]:
        valid_choices = []
        branch = {}

        for idx, conn in enumerate(node['connections'], 1):
            valid_choices.append(str(idx))
            branch[idx] = conn['target']

        return {
            'playPrompt': f"callflow:{node['id']}",
            'getDigits': {
                'numDigits': 1,
                'maxTries': self.config['defaultMaxTries'],
                'maxTime': self.config['defaultMaxTime'],
                'validChoices': '|'.join(valid_choices),
                'errorPrompt': self.config['defaultErrorPrompt'],
                'nonePrompt': self.config['defaultErrorPrompt']
            },
            'branch': {
                **branch,
                'error': 'Problems',
                'none': 'Problems'
            }
        }

    def _createBasicNode(self, node: Dict) -> Dict[str, Any]:
        result = {
            'playPrompt': f"callflow:{node['id']}"
        }

        if node['connections']:
            result['goto'] = node['connections'][0]['target']

        return result

    def _createErrorHandlers(self) -> List[Dict[str, Any]]:
        return [
            {
                'label': 'Problems',
                'playPrompt': 'callflow:1351',
                'goto': 'hangup'
            }
        ]

    def _format_nodes(self, nodes: List[Dict[str, Any]]) -> str:
        formatted = []
        indent = "    "
        
        for node in nodes:
            node_lines = []
            node_lines.append(f"{indent}{{")
            
            for key, value in node.items():
                if isinstance(value, str):
                    node_lines.append(f'{indent}    "{key}": "{value}",')
                elif isinstance(value, dict):
                    node_lines.append(f'{indent}    "{key}": {json.dumps(value, indent=8)},')
                else:
                    node_lines.append(f'{indent}    "{key}": {json.dumps(value)},')
            
            if node_lines[-1].endswith(","):
                node_lines[-1] = node_lines[-1][:-1]
            
            node_lines.append(f"{indent}}},")
            formatted.append("\n".join(node_lines))
        
        if formatted:
            formatted[-1] = formatted[-1][:-1]  # Remove trailing comma
        return "\n".join(formatted)

def convert_mermaid_to_ivr(mermaid_code: str, api_key: str = None) -> str:
    """
    Converts Mermaid code to IVR using custom converter
    The api_key parameter is kept for compatibility but not used
    """
    converter = MermaidIVRConverter()
    return converter.convert_to_ivr(mermaid_code)