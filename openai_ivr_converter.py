"""
Custom Mermaid to IVR converter implementation
"""
from typing import Dict, List, Any
import logging
import json
import re

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

    def convert_to_ivr(self, mermaid_code: str) -> str:
        try:
            # Clean the mermaid code first
            cleaned_code = self._clean_mermaid_code(mermaid_code)
            ivrFlow = self.parseMermaidFlow(cleaned_code)
            nodes_str = self._format_nodes(ivrFlow)
            return f"module.exports = [\n{nodes_str}\n];"
        except Exception as e:
            logging.error(f"Custom conversion failed: {str(e)}")
            return 'module.exports = [{ "label": "Problems", "playPrompt": "callflow:1351", "goto": "hangup" }];'

    def _clean_mermaid_code(self, code: str) -> str:
        """Clean and normalize mermaid code"""
        # Split into lines and clean each line
        lines = []
        for line in code.split('\n'):
            line = line.strip()
            if line and not line.startswith(('%%', 'flowchart', 'style', 'classDef')):
                # Remove color and style information
                if not any(style in line.lower() for style in ['fill:', 'stroke:', 'stroke-width:']):
                    lines.append(line)
        return '\n'.join(lines)

    def parseMermaidFlow(self, mermaid_code: str) -> List[Dict[str, Any]]:
        self.nodeMap = {}
        lines = mermaid_code.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith(('%%', 'flowchart', 'style', 'classDef')):
                continue

            if '-->' in line:
                self._parseConnection(line)
            elif any(c in line for c in '[]{}()'):
                self._parseNode(line)

        return self._generateIVRFlow()

    def _parseNode(self, line: str) -> None:
        """Parse node with enhanced content handling"""
        # Match node ID and content
        node_match = re.match(r'([A-Za-z0-9_]+)\s*[\[\{\(](["\']?)(.*?)(["\'\]\}\)])', line)
        if not node_match:
            return

        node_id = node_match.group(1)
        content = node_match.group(3)
        node_type = 'decision' if '{' in line else 'process'

        # Clean up the content
        content = (content
                  .replace('"', '')
                  .replace("'", "")
                  .replace('<br/>', '\n')
                  .replace('<br>', '\n'))

        self.nodeMap[node_id] = {
            'id': node_id,
            'type': node_type,
            'label': content,
            'connections': []
        }

    def _parseConnection(self, line: str) -> None:
        """Parse connection with label handling"""
        # Handle connection with or without labels
        if '|' in line:
            # Connection with label
            match = re.match(r'([A-Za-z0-9_]+)\s*-->\|([^|]*)\|\s*([A-Za-z0-9_]+)', line)
            if match:
                source, label, target = match.groups()
                if source in self.nodeMap:
                    self.nodeMap[source]['connections'].append({
                        'target': target,
                        'label': label.strip('"\'')
                    })
        else:
            # Simple connection
            match = re.match(r'([A-Za-z0-9_]+)\s*-->\s*([A-Za-z0-9_]+)', line)
            if match:
                source, target = match.groups()
                if source in self.nodeMap:
                    self.nodeMap[source]['connections'].append({
                        'target': target,
                        'label': None
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

        if ivr_flow:
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
        return [{
            'label': 'Problems',
            'playPrompt': 'callflow:1351',
            'goto': 'hangup'
        }]

    def _format_nodes(self, nodes: List[Dict[str, Any]]) -> str:
        formatted = []
        indent = "    "
        
        for node in nodes:
            node_lines = [f"{indent}{{"]
            
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
            formatted[-1] = formatted[-1][:-1]
        return "\n".join(formatted)

def convert_mermaid_to_ivr(mermaid_code: str, api_key: str = None) -> str:
    converter = MermaidIVRConverter()
    return converter.convert_to_ivr(mermaid_code)