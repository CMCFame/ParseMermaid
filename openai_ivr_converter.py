"""
Simplified Mermaid to IVR converter
"""
import re
from typing import Dict, List, Any
import logging

class MermaidIVRConverter:
    def __init__(self):
        self.nodes = {}
        self.connections = []

    def convert_to_ivr(self, mermaid_code: str) -> str:
        """Convert Mermaid flowchart to IVR configuration"""
        try:
            # Reset state
            self.nodes = {}
            self.connections = []
            
            # Process the code
            self._parse_mermaid(mermaid_code)
            
            # Generate IVR nodes
            ivr_nodes = self._generate_ivr_nodes()
            
            # Format the output
            nodes_str = self._format_nodes(ivr_nodes)
            return f"module.exports = [\n{nodes_str}\n];"
            
        except Exception as e:
            logging.error(f"Conversion failed: {str(e)}")
            return 'module.exports = [{ "label": "Problems", "playPrompt": "callflow:1351", "goto": "hangup" }];'

    def _parse_mermaid(self, code: str) -> None:
        """Parse Mermaid code into nodes and connections"""
        lines = [line.strip() for line in code.split('\n') if line.strip()]
        
        for line in lines:
            # Skip non-essential lines
            if line.startswith(('flowchart', 'graph', '%%', 'style', 'classDef')):
                continue
                
            # Parse connections and nodes
            if '-->' in line:
                self._parse_connection(line)
            elif '[' in line or '{' in line:
                self._parse_node(line)

    def _parse_node(self, line: str) -> None:
        """Parse a node definition line"""
        # Extract node ID and content
        if '[' in line:
            parts = line.split('[', 1)
            closing = ']'
            node_type = 'process'
        elif '{' in line:
            parts = line.split('{', 1)
            closing = '}'
            node_type = 'decision'
        else:
            return

        if len(parts) != 2:
            return

        node_id = parts[0].strip()
        content = parts[1].split(closing)[0].strip(' "\'')

        self.nodes[node_id] = {
            'type': node_type,
            'content': content.replace('<br/>', '\n').replace('<br>', '\n'),
            'connections': []
        }

    def _parse_connection(self, line: str) -> None:
        """Parse a connection line"""
        # Split on arrow
        parts = line.split('-->')
        if len(parts) != 2:
            return

        source = parts[0].strip()
        target = parts[1].strip()
        label = None

        # Handle connection labels
        if '|' in target:
            label_parts = target.split('|')
            if len(label_parts) == 2:
                label = label_parts[0].strip(' "\'')
                target = label_parts[1].strip()

        # Clean up node IDs
        source = source.split('[')[0].strip()
        target = target.split('[')[0].strip()

        if source in self.nodes:
            self.nodes[source]['connections'].append({
                'target': target,
                'label': label
            })

    def _generate_ivr_nodes(self) -> List[Dict[str, Any]]:
        """Generate IVR node configurations"""
        ivr_nodes = []

        for node_id, node in self.nodes.items():
            ivr_node = {
                'label': node_id,
                'log': node['content']
            }

            if node['type'] == 'decision':
                # Decision node with multiple paths
                ivr_node.update({
                    'playPrompt': f"callflow:{node_id}",
                    'getDigits': {
                        'numDigits': 1,
                        'maxTries': 3,
                        'maxTime': 7,
                        'validChoices': '|'.join(str(i+1) for i in range(len(node['connections']))),
                        'errorPrompt': 'callflow:1009',
                        'nonePrompt': 'callflow:1009'
                    },
                    'branch': {
                        **{str(i+1): conn['target'] for i, conn in enumerate(node['connections'])},
                        'error': 'Problems',
                        'none': 'Problems'
                    }
                })
            else:
                # Regular node with single path
                ivr_node['playPrompt'] = f"callflow:{node_id}"
                if node['connections']:
                    ivr_node['goto'] = node['connections'][0]['target']

            ivr_nodes.append(ivr_node)

        # Add error handler
        if ivr_nodes:
            ivr_nodes.append({
                'label': 'Problems',
                'playPrompt': 'callflow:1351',
                'goto': 'hangup'
            })

        return ivr_nodes

    def _format_nodes(self, nodes: List[Dict[str, Any]]) -> str:
        """Format nodes as JavaScript code"""
        lines = []
        indent = "    "
        
        for node in nodes:
            node_lines = [f"{indent}{{"]
            
            for key, value in node.items():
                if isinstance(value, str):
                    node_lines.append(f'{indent}    "{key}": "{value}",')
                else:
                    node_lines.append(f'{indent}    "{key}": {value},')
            
            # Remove trailing comma from last property
            if node_lines[-1].endswith(","):
                node_lines[-1] = node_lines[-1][:-1]
            
            node_lines.append(f"{indent}}},")
            lines.append("\n".join(node_lines))
        
        # Remove trailing comma from last node
        if lines:
            lines[-1] = lines[-1][:-1]
        
        return "\n".join(lines)

def convert_mermaid_to_ivr(mermaid_code: str, api_key: str = None) -> str:
    """Convenience wrapper for Mermaid to IVR conversion"""
    converter = MermaidIVRConverter()
    return converter.convert_to_ivr(mermaid_code)