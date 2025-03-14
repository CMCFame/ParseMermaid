"""
Enhanced Mermaid-to-IVR converter that follows IVR documentation standards.
This module parses Mermaid flowcharts and produces standardized IVR configurations.
"""

import re
import json
from typing import Dict, List, Any, Optional, Set, Tuple

class EnhancedMermaidIVRConverter:
    """
    Converts Mermaid flowcharts to IVR call flow configurations
    following the standards in the IVR documentation.
    """
    
    def __init__(self):
        # Standard IVR configuration values
        self.standard_config = {
            'maxTries': 3,
            'maxTime': 7,
            'errorPrompt': "callflow:1009",
            'timeoutPrompt': "callflow:1010"
        }
        
        # Standard IVR prompt IDs (from documentation)
        self.standard_prompts = {
            'welcome': "callflow:1001",
            'pin_entry': "callflow:1008",
            'invalid_input': "callflow:1009",
            'timeout': "callflow:1010",
            'accept': "callflow:1167",
            'decline': "callflow:1021",
            'qualified_no': "callflow:1266",
            'callout_info': "callflow:1274",
            'callout_reason': "callflow:1019",
            'location': "callflow:1232",
            'wait': "callflow:1265",
            'not_home': "callflow:1017",
            'availability': "callflow:1316",
            'goodbye': "callflow:1029",
            'error': "callflow:1351"
        }
        
        # Initialize data structures
        self.nodes = {}          # Map node id -> node dict
        self.connections = []    # List of connections
        self.subgraphs = []      # List of subgraphs

    def convert(self, mermaid_code: str) -> str:
        """
        Convert Mermaid code to IVR configuration.
        Returns a JavaScript module string in the format:
        module.exports = [ ... ];
        """
        self.parse_graph(mermaid_code)
        ivr_flow = self.generate_ivr_flow()
        js_code = "module.exports = " + json.dumps(ivr_flow, indent=2) + ";"
        return js_code

    def parse_graph(self, code: str) -> None:
        """Parse Mermaid flowchart into nodes and connections"""
        lines = [line.strip() for line in code.splitlines() if line.strip()]
        current_subgraph = None

        for line in lines:
            # Skip comments and flowchart definition
            if line.startswith('%%') or line.startswith('flowchart'):
                continue
                
            # Handle subgraphs
            if line.startswith('subgraph'):
                current_subgraph = self.parse_subgraph(line)
                if current_subgraph:
                    self.subgraphs.append(current_subgraph)
                continue
                
            if line == 'end':
                current_subgraph = None
                continue
                
            # Parse connections and nodes
            if '-->' in line:
                self.parse_connection(line)
            elif not line.startswith('class '):  # Skip style lines
                self.parse_node(line, current_subgraph)

    def parse_node(self, line: str, subgraph: Optional[Dict[str, Any]]) -> None:
        """Parse a node definition line"""
        # Match node ID, brackets, and content
        pattern = r'^(\w+)\s*([\[\(\{])(?:")?(.*?)(?:")?\s*([\]\)\}])$'
        match = re.match(pattern, line)
        if not match:
            return
            
        node_id, open_bracket, content, close_bracket = match.groups()
        node_type = self.get_node_type(open_bracket, close_bracket)
        
        # Process the label - replace HTML breaks with newlines
        label = re.sub(r'<br\s*/?>', '\n', content)
        label = label.replace('"', '').replace("'", "").strip()
        
        # Create the node
        node = {
            'id': node_id,
            'type': node_type,
            'label': label,
            'subgraph': subgraph['id'] if subgraph else None,
            'is_decision': (node_type == 'decision'),
            'connections': []
        }
        
        self.nodes[node_id] = node

    def parse_connection(self, line: str) -> None:
        """Parse a connection line"""
        # Pattern to match: source -->|label| target
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
            source = self.parse_inline_node(source)
        if re.search(r'[\[\(\{]', target):
            target = self.parse_inline_node(target)
            
        self.connections.append({
            'source': source,
            'target': target,
            'label': label
        })

    def parse_inline_node(self, node_str: str) -> str:
        """Parse an inline node definition and return the node ID"""
        pattern = r'^(\w+)\s*([\[\(\{])(?:")?(.*?)(?:")?\s*([\]\)\}])$'
        match = re.match(pattern, node_str)
        if not match:
            return node_str  # Return as is if no inline definition
            
        node_id, open_bracket, content, close_bracket = match.groups()
        if node_id not in self.nodes:
            node_type = self.get_node_type(open_bracket, close_bracket)
            label = re.sub(r'<br\s*/?>', '\n', content)
            label = label.replace('"', '').replace("'", "").strip()
            
            node = {
                'id': node_id,
                'type': node_type,
                'label': label,
                'subgraph': None,
                'is_decision': (node_type == 'decision'),
                'connections': []
            }
            self.nodes[node_id] = node
            
        return node_id

    def parse_subgraph(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a subgraph definition"""
        pattern = r'^subgraph\s+(\w+)(?:\s*\[([^\]]*)\])?$'
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

    def get_node_type(self, open_bracket: str, close_bracket: str) -> str:
        """Determine node type based on bracket style"""
        bracket = open_bracket[0]
        if bracket == '[':
            return 'process'
        elif bracket == '(':
            return 'terminal'
        elif bracket == '{':
            return 'decision'
        else:
            return 'process'

    def generate_ivr_flow(self) -> List[Dict[str, Any]]:
        """Generate the IVR flow array from parsed nodes and connections"""
        ivr_flow = []
        processed = set()

        # Process start nodes first (nodes with no incoming connections)
        start_nodes = self.find_start_nodes()
        for node_id in start_nodes:
            self.process_node(node_id, ivr_flow, processed)

        # Process any remaining nodes
        for node_id in self.nodes:
            self.process_node(node_id, ivr_flow, processed)

        # Append standard error handlers
        ivr_flow.append(self.create_error_handlers())
        ivr_flow.append(self.create_goodbye_node())
        
        return ivr_flow

    def process_node(self, node_id: str, ivr_flow: List[Dict[str, Any]], 
                     processed: Set[str]) -> None:
        """Process a node and its connections into the IVR flow"""
        if node_id in processed:
            return
            
        processed.add(node_id)
        node = self.nodes.get(node_id)
        if not node:
            return
            
        # Gather outgoing connections
        outgoing = [conn for conn in self.connections if conn['source'] == node_id]
        node['connections'] = outgoing
        
        # Create IVR node
        ivr_node = self.create_ivr_node(node)
        ivr_flow.append(ivr_node)
        
        # Process connected nodes
        for conn in outgoing:
            self.process_node(conn['target'], ivr_flow, processed)

    def create_ivr_node(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Create an IVR node configuration based on the Mermaid node"""
        # Common properties for all nodes
        base = {
            'label': node['id'],
            'log': node['label'].replace('\n', ' ')
        }
        
        # For decision nodes, create input collection and branching
        if node.get('is_decision'):
            return self.create_decision_node(node, base)
            
        # For regular nodes with a single connection, add goto
        ivr_node = {
            **base,
            'playPrompt': f"callflow:{node['id']}"
        }
        
        if len(node.get('connections', [])) == 1:
            ivr_node['goto'] = node['connections'][0]['target']
            
        return ivr_node

    def create_decision_node(self, node: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
        """Create an IVR decision node with input handling and branching"""
        connections = node.get('connections', [])
        choices = []
        branch = {}
        
        # Build valid choices and branches based on connections
        for i, conn in enumerate(connections):
            choice = str(i + 1)
            choices.append(choice)
            branch[choice] = conn['target']
        
        # Add error handling
        branch['error'] = 'Problems'
        branch['none'] = 'Problems'
        
        return {
            **base,
            'playPrompt': f"callflow:{node['id']}",
            'getDigits': {
                'numDigits': 1,
                'maxTries': self.standard_config['maxTries'],
                'maxTime': self.standard_config['maxTime'],
                'validChoices': '|'.join(choices),
                'errorPrompt': self.standard_config['errorPrompt'],
                'timeoutPrompt': self.standard_config['timeoutPrompt']
            },
            'branch': branch
        }

    def create_error_handlers(self) -> Dict[str, Any]:
        """Create standard error handler node"""
        return {
            'label': 'Problems',
            'nobarge': '1',
            'playLog': "I'm sorry you are having problems.",
            'playPrompt': self.standard_prompts['error'],
            'goto': 'Goodbye'
        }
        
    def create_goodbye_node(self) -> Dict[str, Any]:
        """Create standard goodbye/hangup node"""
        return {
            'label': 'Goodbye',
            'playLog': "Thank you. Goodbye.",
            'playPrompt': self.standard_prompts['goodbye'],
            'hangup': '1'
        }

    def find_start_nodes(self) -> List[str]:
        """Find nodes with no incoming connections (start nodes)"""
        incoming = set(conn['target'] for conn in self.connections)
        return [node_id for node_id in self.nodes if node_id not in incoming]

    def detect_callflow_type(self, mermaid_code: str) -> Tuple[str, Dict[str, str]]:
        """
        Detect the type of callflow to assign appropriate prompts
        Returns a tuple of (callflow_type, specialized_prompt_map)
        """
        # Default to standard prompts
        callflow_type = "standard"
        prompts = self.standard_prompts.copy()
        
        # Look for keywords that suggest electric callout
        if (re.search(r'electric\s+callout|ARCOS', mermaid_code, re.IGNORECASE) or
            re.search(r'employee|trouble\s+location', mermaid_code, re.IGNORECASE)):
            callflow_type = "electric_callout"
            prompts['welcome'] = "callflow:1274"  # Electric callout info
            
        # Look for keywords suggesting PIN authentication flow
        elif re.search(r'PIN|password|authenticate', mermaid_code, re.IGNORECASE):
            callflow_type = "pin_authentication"
            prompts['welcome'] = "callflow:1008"  # PIN entry request
            
        # Look for keywords suggesting transfer flow
        elif re.search(r'transfer|connect|dispatch', mermaid_code, re.IGNORECASE):
            callflow_type = "transfer"
            prompts['welcome'] = "callflow:1645"  # Transfer request
            
        return callflow_type, prompts

def convert_mermaid_to_ivr(mermaid_code: str) -> str:
    """
    Convert Mermaid code to IVR configuration.
    Returns a JavaScript module string.
    """
    converter = EnhancedMermaidIVRConverter()
    return converter.convert(mermaid_code)