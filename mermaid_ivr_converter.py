"""
Enhanced Mermaid-to-IVR converter that follows real IVR code examples.
This module parses Mermaid flowcharts and produces standardized IVR configurations
that match the exact format of the real ARCOS IVR code.
"""

import re
import json
from typing import Dict, List, Any, Optional, Set, Tuple
import datetime

class EnhancedMermaidIVRConverter:
    """
    Converts Mermaid flowcharts to IVR call flow configurations
    following the standards in real IVR code examples.
    """
    
    def __init__(self):
        # Map common descriptions to standard callflow IDs
        self.callflow_ids = {
            "welcome": "1210",
            "press_1": "1002",
            "press_3": "1005",
            "press_7": "1641",
            "press_9": "1643",
            "need_more_time": "1006",
            "not_home": "1004",
            "repeat_message": "1007",
            "pin_entry": "1008",
            "invalid_input": "1009",
            "timeout": "1010",
            "accept": "1167",
            "decline": "1021",
            "qualified_no": "1266",
            "callout": "1274",
            "custom_message": "custom:{{custom_message}}",
            "wait_message": "1265",
            "goodbye": "1029",
            "error": "1351"
        }
        
        # Initialize data structures
        self.nodes = {}          # Map node id -> node dict
        self.connections = []    # List of connections
        self.node_labels = {}    # Map node id -> semantic label
        self.decision_nodes = set()  # Keep track of decision nodes

        # Track creation date for "Dev Date" comment
        now = datetime.datetime.now()
        self.dev_date = now.strftime("%Y-%m-%d %H:%M:%S")

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
        
        # Process title info if available
        title_info = self.extract_title_info(code)
        
        # First pass: identify all nodes
        for line in lines:
            # Skip comments and flowchart definition
            if line.startswith('%%') or line.startswith('flowchart') or line.startswith('graph'):
                continue
                
            # Parse node definitions
            if "-->" not in line and not line.startswith('subgraph') and not line == 'end' and not line.startswith('class'):
                self.parse_node_definition(line)
                
        # Second pass: parse connections
        for line in lines:
            if "-->" in line:
                self.parse_connection(line)
                
        # Assign semantic labels based on node content
        self.assign_semantic_labels()

    def extract_title_info(self, code: str) -> Dict[str, str]:
        """Extract title and other metadata from the flowchart"""
        title_info = {}
        
        # Look for title in a subgraph called "Header"
        header_match = re.search(r'subgraph\s+Header.*?Title\s*\["([^"]+)"\]', code, re.DOTALL)
        if header_match:
            title_info['title'] = header_match.group(1)
            
        # Look for customer info
        customer_match = re.search(r'Customer\s+ID:\s*(\w+)', code)
        if customer_match:
            title_info['customer_id'] = customer_match.group(1)
            
        return title_info

    def parse_node_definition(self, line: str) -> None:
        """Parse a node definition line"""
        # Match node ID and content with different bracket types
        node_patterns = [
            r'^(\w+)\s*\["([^"]+)"\]',  # ["text"] - process node
            r'^(\w+)\s*\{"([^"]+)"\}',  # {"text"} - decision node
            r'^(\w+)\s*\("([^"]+)"\)',  # ("text") - terminal node
            r'^(\w+)\s*\[\("([^"]+)"\)\]'  # [("text")] - subroutine node
        ]
        
        for pattern in node_patterns:
            match = re.match(pattern, line)
            if match:
                node_id, content = match.groups()
                
                # Determine if this is a decision node
                is_decision = pattern == node_patterns[1] or "?" in content
                if is_decision:
                    self.decision_nodes.add(node_id)
                
                # Store the node content, cleaned of HTML tags
                self.nodes[node_id] = {
                    'id': node_id,
                    'content': re.sub(r'<br\s*/?>', '\n', content).strip(),
                    'connections': [],
                    'is_decision': is_decision
                }
                break

    def parse_connection(self, line: str) -> None:
        """Parse a connection line"""
        # Basic connection pattern: A --> B
        basic_match = re.match(r'(\w+)\s*-->\s*(\w+)', line)
        if basic_match:
            source, target = basic_match.groups()
            self.connections.append({
                'source': source, 
                'target': target,
                'label': ''
            })
            return
            
        # Connection with label: A -->|label| B
        label_match = re.match(r'(\w+)\s*-->\s*\|([^|]+)\|\s*(\w+)', line)
        if label_match:
            source, label, target = label_match.groups()
            
            # Clean up the label
            label = label.strip().strip('"\'')
            
            self.connections.append({
                'source': source, 
                'target': target,
                'label': label
            })

    def assign_semantic_labels(self) -> None:
        """
        Assign semantic labels to nodes based on their content.
        This helps create more meaningful IVR node labels.
        """
        label_patterns = {
            r'welcome': 'Welcome',
            r'press any key': 'Sleep',
            r'invalid entry': 'Invalid Entry',
            r'this is employee': 'Enter PIN',
            r'not home': 'Not Home',
            r'Thank you': 'Goodbye',
            r'Message': 'Custom Message',
            r'confirm': 'Confirm',
            r'accept': 'Accept',
            r'decline': 'Decline',
            r'disconnect': 'Disconnect'
        }
        
        for node_id, node in self.nodes.items():
            content = node['content'].lower()
            
            # Try to assign a semantic label based on content
            assigned = False
            for pattern, label in label_patterns.items():
                if re.search(pattern, content, re.IGNORECASE):
                    self.node_labels[node_id] = label
                    assigned = True
                    break
                    
            # If no label assigned, use a default based on node position
            if not assigned:
                if self.is_start_node(node_id):
                    self.node_labels[node_id] = "Live Answer"
                else:
                    # Use the first 2-3 words of content as a label
                    words = re.split(r'\s+', node['content'])
                    if len(words) > 2:
                        label = ' '.join(words[:2]) + '...'
                    else:
                        label = node['content']
                    self.node_labels[node_id] = label
                    
                    # Special case for decision nodes
                    if node['is_decision']:
                        self.node_labels[node_id] = "Offer" if "avail" in content.lower() else "Decision"

    def is_start_node(self, node_id: str) -> bool:
        """Check if this is a start node (no incoming connections)"""
        return not any(conn['target'] == node_id for conn in self.connections)

    def get_outgoing_connections(self, node_id: str) -> List[Dict[str, str]]:
        """Get all outgoing connections from this node"""
        return [conn for conn in self.connections if conn['source'] == node_id]

    def generate_ivr_flow(self) -> List[Dict[str, Any]]:
        """Generate the IVR flow array from parsed nodes and connections"""
        ivr_flow = []
        processed = set()

        # Process start nodes first
        start_nodes = [node_id for node_id in self.nodes if self.is_start_node(node_id)]
        for node_id in start_nodes:
            self.process_node(node_id, ivr_flow, processed)

        # Process any remaining nodes
        for node_id in self.nodes:
            self.process_node(node_id, ivr_flow, processed)

        # Add standard error handling nodes if not already present
        if not any(node.get('label') == 'Problems' for node in ivr_flow):
            ivr_flow.append(self.create_problems_node())
            
        if not any(node.get('label') == 'Goodbye' for node in ivr_flow):
            ivr_flow.append(self.create_goodbye_node())

        return ivr_flow

    def process_node(self, node_id: str, ivr_flow: List[Dict[str, Any]], processed: Set[str]) -> None:
        """Process a node and all its outgoing connections"""
        if node_id in processed:
            return
            
        processed.add(node_id)
        
        # Skip nodes that don't exist (they might be referenced but not defined)
        if node_id not in self.nodes:
            return
            
        node = self.nodes[node_id]
        outgoing = self.get_outgoing_connections(node_id)
        node['connections'] = outgoing
        
        # Create an IVR node
        ivr_node = self.create_ivr_node(node)
        ivr_flow.append(ivr_node)
        
        # Process connected nodes
        for conn in outgoing:
            self.process_node(conn['target'], ivr_flow, processed)

    def create_ivr_node(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an IVR node configuration based on the Mermaid node.
        This follows the format of real IVR code examples.
        """
        node_id = node['id']
        content = node['content']
        
        # Set the meaningful label
        label = self.node_labels.get(node_id, f"Node-{node_id}")
        
        # Basic node structure
        ivr_node = {
            'label': label,
            'log': f"Dev Date: {self.dev_date}" if label == "Live Answer" else content
        }
        
        # Add maxLoop for certain nodes
        if label == "Live Answer":
            ivr_node['maxLoop'] = ["Main", 3, "Problems"]
            
        # Set playLog and playPrompt based on content
        content_lines = content.split('\n')
        if len(content_lines) > 1:
            ivr_node['playLog'] = [line for line in content_lines if line.strip()]
            
            # Create matching playPrompt array
            play_prompts = []
            for line in content_lines:
                if line.strip():
                    # Map content to standard callflow IDs where possible
                    prompt_id = self.map_content_to_callflow_id(line)
                    if prompt_id:
                        play_prompts.append(prompt_id)
            
            if play_prompts:
                ivr_node['playPrompt'] = play_prompts
            else:
                # Default to using the node ID as callflow ID
                ivr_node['playPrompt'] = [f"callflow:{node_id}"]
        else:
            # Single line content
            prompt_id = self.map_content_to_callflow_id(content)
            if prompt_id:
                ivr_node['playPrompt'] = [prompt_id]
            else:
                ivr_node['playPrompt'] = [f"callflow:{node_id}"]
        
        # Handle decision nodes
        if node['is_decision']:
            ivr_node = self.handle_decision_node(node, ivr_node)
        else:
            # For non-decision nodes with exactly one outgoing connection, add a goto
            outgoing = node['connections']
            if len(outgoing) == 1:
                target_id = outgoing[0]['target']
                if target_id in self.node_labels:
                    ivr_node['goto'] = self.node_labels[target_id]
                else:
                    ivr_node['goto'] = target_id
        
        # Special handling for specific node types
        if "not home" in content.lower():
            ivr_node['nobarge'] = "1"
            
        if "invalid entry" in content.lower():
            if 'goto' not in ivr_node:
                # Find likely target for invalid entry
                for conn in self.connections:
                    if conn['source'] == node['id']:
                        target = conn['target']
                        if target in self.node_labels:
                            ivr_node['goto'] = self.node_labels[target]
                        break
        
        return ivr_node

    def handle_decision_node(self, node: Dict[str, Any], ivr_node: Dict[str, Any]) -> Dict[str, Any]:
        """Create getDigits and branch objects for decision nodes"""
        # Set up getDigits object
        get_digits = {
            'numDigits': 1,
            'maxTries': 3,
            'maxTime': 7,
            'validChoices': "1|3|7|9",  # Default, will be refined based on connections
            'errorPrompt': "callflow:1009"
        }
        
        # Build branch object based on outgoing connections
        branch = {}
        valid_choices = []
        
        for conn in node['connections']:
            label = conn['label'].lower()
            target_id = conn['target']
            target_label = self.node_labels.get(target_id, target_id)
            
            # Map connection label to digit
            if '1' in label or 'yes' in label or 'accept' in label:
                branch['1'] = target_label
                valid_choices.append('1')
            elif '3' in label or 'more time' in label or 'replay' in label:
                branch['3'] = target_label
                valid_choices.append('3')
            elif '7' in label or 'not home' in label:
                branch['7'] = target_label
                valid_choices.append('7')
            elif '9' in label or 'repeat' in label:
                branch['9'] = target_label
                valid_choices.append('9')
            elif 'error' in label or 'invalid' in label:
                branch['error'] = target_label
            elif 'none' in label or 'no input' in label:
                branch['none'] = target_label
            else:
                # Check for simple number
                digit_match = re.search(r'(\d+)', label)
                if digit_match:
                    digit = digit_match.group(1)
                    branch[digit] = target_label
                    valid_choices.append(digit)
        
        # Always add error handling
        if 'error' not in branch:
            branch['error'] = 'Problems'
        if 'none' not in branch:
            branch['none'] = 'Problems'
            
        # Update validChoices based on the connected options
        if valid_choices:
            get_digits['validChoices'] = '|'.join(sorted(valid_choices))
            
        # Add to node
        ivr_node['getDigits'] = get_digits
        ivr_node['branch'] = branch
        
        return ivr_node

    def map_content_to_callflow_id(self, content: str) -> Optional[str]:
        """Map content to standard callflow IDs based on keywords"""
        content_lower = content.lower()
        
        # Check for standard messages
        if "welcome" in content_lower or "this is a" in content_lower:
            return "callflow:1210"
        elif "press 1" in content_lower:
            return "callflow:1002"
        elif "press 3" in content_lower or "more time" in content_lower:
            return "callflow:1005"
        elif "press 7" in content_lower or "not home" in content_lower:
            return "callflow:1004"
        elif "press 9" in content_lower or "repeat" in content_lower:
            return "callflow:1643"
        elif "pin" in content_lower:
            return "callflow:1008"
        elif "invalid" in content_lower:
            return "callflow:1009"
        elif "accept" in content_lower:
            return "callflow:1167"
        elif "decline" in content_lower:
            return "callflow:1021"
        elif "press any key" in content_lower:
            return "callflow:1265"
        elif "goodbye" in content_lower or "thank you" in content_lower:
            return "callflow:1029"
        elif "custom message" in content_lower:
            return "custom:{{custom_message}}"
        elif "error" in content_lower or "problem" in content_lower:
            return "callflow:1351"
            
        # For location specific content
        if "(level 2)" in content_lower or "l2 location" in content_lower:
            return "location:{{level2_location}}"
        
        # For employee name content
        if "employee" in content_lower:
            return "names:{{contact_id}}"
            
        # Not a standard prompt
        return None

    def create_problems_node(self) -> Dict[str, Any]:
        """Create a standard Problems node"""
        return {
            'label': 'Problems',
            'nobarge': '1',
            'playLog': "I'm sorry you are having problems.",
            'playPrompt': "callflow:1351",
            'goto': 'Goodbye'
        }

    def create_goodbye_node(self) -> Dict[str, Any]:
        """Create a standard Goodbye node"""
        return {
            'label': 'Goodbye',
            'log': "Thank you. Goodbye.",
            'playPrompt': "callflow:1029",
            'nobarge': "1",
            'goto': "hangup"
        }

def convert_mermaid_to_ivr(mermaid_code: str) -> str:
    """
    Convert Mermaid code to IVR configuration.
    Returns a JavaScript module string in the correct format.
    """
    converter = EnhancedMermaidIVRConverter()
    return converter.convert(mermaid_code)