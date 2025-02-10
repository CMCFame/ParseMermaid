"""
Enhanced IVR converter with both OpenAI and custom conversion capabilities
"""
from typing import Dict, List, Any
import logging
from openai import OpenAI
import json

class MermaidToIVRConverter:
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

    def parseMermaidFlow(self, mermaid_code: str) -> List[Dict[str, Any]]:
        lines = mermaid_code.split('\n')
        current_subgraph = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith('%%') or line.startswith('flowchart'):
                continue

            if line.startswith('subgraph'):
                current_subgraph = self._parseSubgraph(line)
            elif line == 'end':
                current_subgraph = None
            elif '-->' in line:
                self._parseConnection(line)
            elif any(c in line for c in '[]{}()'):
                self._parseNode(line, current_subgraph)

        return self._generateIVRFlow()

    def _parseNode(self, line: str, subgraph: str = None) -> None:
        # Handle different node types
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
            content = node_match[1].split(']')[0].split('}')[0].split(')')[0].replace('"', '')
            
            self.nodeMap[node_id] = {
                'id': node_id,
                'type': node_type,
                'label': content.replace('<br/>', '\n').replace('<br>', '\n'),
                'subgraph': subgraph,
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

        # Add standard error handlers
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

class OpenAIIVRConverter:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.custom_converter = MermaidToIVRConverter()

    def convert_to_ivr(self, mermaid_code: str) -> str:
        try:
            return self.custom_converter.convert_to_ivr(mermaid_code)
        except Exception as e:
            logging.warning(f"Custom conversion failed, using OpenAI: {str(e)}")
            return self._convert_with_openai(mermaid_code)

    def _convert_with_openai(self, mermaid_code: str) -> str:
        prompt = f"""Convert this Mermaid flowchart to IVR JavaScript configuration:

{mermaid_code}

Return only the JavaScript code in module.exports = [...]; format."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an IVR system expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            ivr_code = response.choices[0].message.content.strip()
            
            # Validate and clean response
            if "module.exports = [" in ivr_code:
                start_idx = ivr_code.find("module.exports = [")
                end_idx = ivr_code.rfind("];") + 2
                ivr_code = ivr_code[start_idx:end_idx]

            return ivr_code

        except Exception as e:
            logging.error(f"OpenAI conversion failed: {str(e)}")
            return 'module.exports = [{ "label": "Problems", "playPrompt": "callflow:1351", "goto": "hangup" }];'

def convert_mermaid_to_ivr(mermaid_code: str, api_key: str = None) -> str:
    if api_key:
        converter = OpenAIIVRConverter(api_key)
    else:
        converter = MermaidToIVRConverter()
    
    return converter.convert_to_ivr(mermaid_code)