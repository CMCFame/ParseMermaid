"""
Enhanced Mermaid to IVR converter that produces exact format matching
the real IVR code requirements with proper callflow IDs, dynamic content,
and semantic node labeling.
"""
import re
import json
from datetime import datetime
from typing import Dict, List, Any, Set

class ExactIVRConverter:
    """
    Converter that transforms Mermaid flowcharts into IVR code with
    exact format matching the real IVR system requirements.
    """
    def __init__(self):
        self.nodes = {}
        self.connections = []
        # Standard callflow IDs
        self.callflow_ids = {
            "welcome": "1210",
            "live_answer": "1210",
            "menu_options": "1002",
            "pin_entry": "1008",
            "error": "1009",
            "timeout": "1010",
            "custom_message": "1200",
            "accepted": "1167",
            "declined": "1021",
            "not_home": "1017",
            "goodbye": "1029",
            "problems": "1351",
            "need_time": "1005",
            "repeat": "1643",
            "employee_info": "1004",
            "press_7": "1006",
            "press_9": "1641",
            "electric_callout": "1274"
        }
        
    def convert(self, mermaid_code: str) -> str:
        """
        Convert Mermaid code to exact IVR code format.
        
        Args:
            mermaid_code: Mermaid diagram code
            
        Returns:
            Formatted IVR code
        """
        # Parse the Mermaid code
        self.parse_mermaid(mermaid_code)
        
        # Generate IVR nodes with exact format
        ivr_nodes = self.generate_ivr_nodes()
        
        # Format the IVR code
        ivr_code = "module.exports = [\n"
        
        for i, node in enumerate(ivr_nodes):
            # Add comments and spacers for readability
            if i == 0:
                ivr_code += "    // ****************************************************** //\n"
            
            ivr_code += "    " + self.format_node(node)
            
            if i < len(ivr_nodes) - 1:
                ivr_code += ","
            
            ivr_code += "\n"
        
        ivr_code += "];"
        
        return ivr_code
        
    def format_node(self, node: Dict) -> str:
        """
        Format a node object as a string with proper indentation and formatting.
        
        Args:
            node: Node object
            
        Returns:
            Formatted node string
        """
        result = "{\n"
        
        # Add comment if present
        if "comment" in node:
            result += f"        // {node['comment']}\n"
            
        # Format each property
        for key, value in node.items():
            if key == "comment":
                continue
                
            if key == "guard" and isinstance(value, str):
                # Format guard function
                result += f"        {key}: function (){{ {value} }}"
            elif isinstance(value, list):
                # Format arrays with proper indentation
                result += f"        {key}: ["
                
                if all(isinstance(item, str) for item in value):
                    # Format string arrays on one line
                    items = ", ".join([f'"{item}"' if not item.startswith("callflow:") and not item.startswith("names:") and not item.startswith("location:") and not item.startswith("standard:") else item for item in value])
                    result += f" {items} ]"
                else:
                    # Format complex arrays with each item on a new line
                    result += "\n"
                    for item in value:
                        if isinstance(item, str):
                            if item.startswith("callflow:") or item.startswith("names:") or item.startswith("location:") or item.startswith("standard:"):
                                result += f"            {item}"
                            else:
                                result += f'            "{item}"'
                        else:
                            result += f"            {item}"
                        
                        if item != value[-1]:
                            result += ","
                        
                        result += "\n"
                    
                    result += "        ]"
            elif isinstance(value, dict):
                # Format objects
                result += f"        {key}: {{\n"
                
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, str):
                        if sub_value.startswith("callflow:") or sub_value == "1" or sub_key in ["1", "3", "7", "9", "error"]:
                            result += f"            {sub_key}: {sub_value}"
                        else:
                            result += f'            {sub_key}: "{sub_value}"'
                    else:
                        result += f"            {sub_key}: {sub_value}"
                    
                    if sub_key != list(value.keys())[-1]:
                        result += ","
                    
                    result += "\n"
                
                result += "        }"
            else:
                # Format primitive values
                if isinstance(value, str):
                    if value.startswith("callflow:") or value.startswith("names:") or value.startswith("location:") or value.startswith("standard:") or key == "label" or key in ["1", "3", "7", "9", "error"]:
                        result += f"        {key}: {value}"
                    else:
                        result += f'        {key}: "{value}"'
                else:
                    result += f"        {key}: {value}"
            
            if key != list(node.keys())[-1] and key != "comment":
                result += ","
            
            result += "\n"
        
        result += "    }"
        
        return result
    
    def parse_mermaid(self, mermaid_code: str) -> None:
        """
        Parse Mermaid code into nodes and connections.
        
        Args:
            mermaid_code: Mermaid diagram code
        """
        self.nodes = {}
        self.connections = []
        
        # Split lines and filter out empty ones
        lines = [line.strip() for line in mermaid_code.split('\n') if line.strip()]
        
        # Skip subgraph sections and classes
        skip_until_end = False
        
        for line in lines:
            # Skip comment lines and flowchart definition
            if line.startswith('%%') or line.startswith('flowchart') or line.startswith('classDef'):
                continue
                
            # Handle subgraphs (we'll skip their content)
            if line.startswith('subgraph'):
                skip_until_end = True
                continue
                
            if skip_until_end and line == 'end':
                skip_until_end = False
                continue
                
            if skip_until_end:
                continue
                
            # Process class definitions
            if line.startswith('class '):
                continue
                
            # Process connections
            if '-->' in line:
                self.parse_connection(line)
            # Process nodes
            else:
                self.parse_node(line)
    
    def parse_node(self, line: str) -> None:
        """
        Parse a node definition in Mermaid.
        
        Args:
            line: Mermaid node definition
        """
        # Handle node definitions like A["Text"] or A{"Decision"}
        node_pattern = r'^(\w+)\s*([\[\(\{])([^"\]\)\}]*)[\]\)\}]$'
        match = re.match(node_pattern, line)
        
        if not match:
            # Try alternative pattern with explicit quotes
            node_pattern = r'^(\w+)\s*([\[\(\{])"([^"]*)"[\]\)\}]$'
            match = re.match(node_pattern, line)
            
        if not match:
            return
            
        node_id, bracket_type, content = match.groups()
        
        # Determine node type based on bracket
        if bracket_type == '{':
            node_type = 'decision'
        elif bracket_type == '[':
            node_type = 'process'
        elif bracket_type == '(':
            node_type = 'terminal'
        else:
            node_type = 'process'
        
        # Clean content by replacing <br/> with newlines
        content = re.sub(r'<br\s*/?>', '\n', content)
        
        # Store the node
        self.nodes[node_id] = {
            'id': node_id,
            'type': node_type,
            'content': content
        }
    
    def parse_connection(self, line: str) -> None:
        """
        Parse a connection between nodes in Mermaid.
        
        Args:
            line: Mermaid connection line
        """
        # Handle connections like A -->|"label"| B or A --> B
        conn_pattern = r'^(\w+)\s*-->\s*(?:\|([^|]*)\|\s*)?(\w+)$'
        match = re.match(conn_pattern, line)
        
        if not match:
            return
            
        from_id, label, to_id = match.groups()
        
        # Clean up the label
        label = label.strip() if label else ""
        
        # Remove quotes from label
        label = label.strip('"').strip("'")
        
        # Store the connection
        self.connections.append({
            'from': from_id,
            'to': to_id,
            'label': label
        })
    
    def generate_ivr_nodes(self) -> List[Dict[str, Any]]:
        """
        Generate IVR nodes that match the exact format required.
        
        Returns:
            List of IVR nodes
        """
        ivr_nodes = []
        semantic_labels = self.create_semantic_labels()
        
        # Create the first welcome/live answer node
        welcome_node = self.create_live_answer_node()
        if welcome_node:
            ivr_nodes.append(welcome_node)
        
        # Create environment node
        env_node = self.create_environment_node()
        if env_node:
            ivr_nodes.append(env_node)
        
        # Create the main menu/options node
        menu_node = self.create_menu_options_node()
        if menu_node:
            ivr_nodes.append(menu_node)
        
        # Process all other nodes
        processed_nodes = set(['A'])  # Assume A is the welcome node
        
        for node_id, node in self.nodes.items():
            if node_id in processed_nodes:
                continue
                
            semantic_label = semantic_labels.get(node_id, f"Node-{node_id}")
            
            if "custom message" in node['content'].lower():
                ivr_nodes.append(self.create_custom_message_node(node, semantic_label))
            elif "confirm" in node['content'].lower():
                ivr_nodes.append(self.create_confirm_node(node, semantic_label))
            elif "not home" in node['content'].lower() and "employee" in node['content'].lower():
                ivr_nodes.append(self.create_employee_not_home_node(node, semantic_label))
            elif "not home" in node['content'].lower() and "contact" in node['content'].lower():
                ivr_nodes.append(self.create_contact_not_home_node(node, semantic_label))
            elif "accepted" in node['content'].lower():
                ivr_nodes.append(self.create_accepted_node(node, semantic_label))
            elif "invalid" in node['content'].lower():
                ivr_nodes.append(self.create_invalid_entry_node(node, semantic_label))
            elif "goodbye" in node['content'].lower():
                ivr_nodes.append(self.create_goodbye_node(node, semantic_label))
            else:
                ivr_nodes.append(self.create_standard_node(node, semantic_label))
            
            processed_nodes.add(node_id)
        
        # Add standard handling nodes
        if not any(node.get('label') == 'Problems' for node in ivr_nodes):
            ivr_nodes.append(self.create_problems_node())
        
        return ivr_nodes
    
    def create_live_answer_node(self) -> Dict[str, Any]:
        """
        Create the Live Answer node, which is typically the first node.
        
        Returns:
            Live Answer node in the exact format
        """
        # Find the first node (usually A)
        first_node = self.nodes.get('A')
        
        if not first_node:
            return None
        
        # Get current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create the node
        return {
            "comment": "#GITHASH: GIT_HASH_ID",
            "label": "Live Answer",
            "log": f"Dev Date: {timestamp}",
            "maxLoop": ["Main", 3, "Problems"],
            "playLog": [
                "This is a",
                "L2 location",
                "callout"
            ],
            "playPrompt": [
                f"callflow:{self.callflow_ids['welcome']}",
                "location:{{level2_location}}",
                f"callflow:{self.callflow_ids['electric_callout']}"
            ]
        }
    
    def create_environment_node(self) -> Dict[str, Any]:
        """
        Create the environment check node.
        
        Returns:
            Environment node in the exact format
        """
        return {
            "log": "environment",
            "guard": "return this.data.env!='prod' && this.data.env!='PROD'",
            "playPrompt": "callflow:{{env}}",
            "nobarge": "1"
        }
    
    def create_menu_options_node(self) -> Dict[str, Any]:
        """
        Create the menu options node with all possible options.
        
        Returns:
            Menu options node in the exact format
        """
        # Find what each option maps to by looking at connections from A
        branches = {}
        for conn in self.connections:
            if conn['from'] == 'A':
                label = conn['label'].lower()
                target = conn['to']
                
                if "1" in label:
                    branches["1"] = "Enter PIN"
                elif "3" in label:
                    branches["3"] = "Sleep"
                elif "7" in label:
                    branches["7"] = "Not Home"
                elif "9" in label or "repeat" in label:
                    branches["9"] = "Live Answer"
        
        # Add default error handling
        if not branches:
            branches = {
                "1": "Enter PIN",
                "3": "Sleep",
                "7": "Not Home",
                "9": "Live Answer"
            }
        
        branches["error"] = "Live Answer"
        
        return {
            "comment": "# next will fall through",
            "playLog": [
                "Press 1 if this is",
                "Employee name spoken({{contact_id}})",
                "if you need more time to get",
                "Employee name spoken",
                "to the phone",
                "Press 7",
                "if",
                "Employee name spoken",
                "is not home",
                "Press 9",
                "to repeat this message"
            ],
            "playPrompt": [
                f"callflow:{self.callflow_ids['menu_options']}",
                "names:{{contact_id}}",
                f"callflow:{self.callflow_ids['need_time']}",
                "names:{{contact_id}}",
                f"callflow:{self.callflow_ids['press_7']}",
                "standard:PRS7NEU",
                f"callflow:{self.callflow_ids['press_9']}",
                "names:{{contact_id}}",
                f"callflow:{self.callflow_ids['employee_info']}",
                "standard:PRS9NEU",
                f"callflow:{self.callflow_ids['repeat']}"
            ],
            "getDigits": {
                "numDigits": 1,
                "maxTime": 1,
                "validChoices": "1|3|7|9",
                "errorPrompt": f"callflow:{self.callflow_ids['error']}"
            },
            "branch": branches
        }
    
    def create_custom_message_node(self, node: Dict[str, Any], semantic_label: str) -> Dict[str, Any]:
        """
        Create a Custom Message node.
        
        Args:
            node: Mermaid node data
            semantic_label: Semantic label for the node
            
        Returns:
            Custom Message node in the exact format
        """
        return {
            "label": semantic_label,
            "log": node['content'],
            "playLog": ["Custom message content"],
            "playPrompt": [f"callflow:{self.callflow_ids['custom_message']}"],
            "goto": self.get_next_node(node['id'])
        }
    
    def create_confirm_node(self, node: Dict[str, Any], semantic_label: str) -> Dict[str, Any]:
        """
        Create a Confirm node with getDigits.
        
        Args:
            node: Mermaid node data
            semantic_label: Semantic label for the node
            
        Returns:
            Confirm node in the exact format
        """
        # Gather branches based on connections
        branches = {}
        for conn in self.connections:
            if conn['from'] == node['id']:
                label = conn['label'].lower()
                target = conn['to']
                
                if "1" in label or "accept" in label:
                    branches["1"] = "Accepted"
                elif "3" in label or "repeat" in label:
                    branches["3"] = "Custom Message"
                elif "invalid" in label:
                    branches["error"] = "Invalid Entry"
                elif "no input" in label:
                    branches["none"] = "Invalid Entry"
        
        # Add default error handling
        if "error" not in branches:
            branches["error"] = "Problems"
        if "none" not in branches:
            branches["none"] = "Problems"
        
        return {
            "label": semantic_label,
            "log": node['content'],
            "playLog": ["To confirm receipt of this message, press 1. To replay the message, press 3."],
            "playPrompt": [f"callflow:{self.callflow_ids['menu_options']}"],
            "getDigits": {
                "numDigits": 1,
                "maxTries": 3,
                "maxTime": 7,
                "validChoices": "1|3",
                "errorPrompt": f"callflow:{self.callflow_ids['error']}"
            },
            "branch": branches
        }
    
    def create_employee_not_home_node(self, node: Dict[str, Any], semantic_label: str) -> Dict[str, Any]:
        """
        Create an Employee Not Home node.
        
        Args:
            node: Mermaid node data
            semantic_label: Semantic label for the node
            
        Returns:
            Employee Not Home node in the exact format
        """
        return {
            "label": semantic_label,
            "log": node['content'],
            "playLog": ["Please have employee call the callout system"],
            "playPrompt": [f"callflow:{self.callflow_ids['not_home']}"],
            "goto": self.get_next_node(node['id'])
        }
    
    def create_contact_not_home_node(self, node: Dict[str, Any], semantic_label: str) -> Dict[str, Any]:
        """
        Create a Contact Not Home node.
        
        Args:
            node: Mermaid node data
            semantic_label: Semantic label for the node
            
        Returns:
            Contact Not Home node in the exact format
        """
        return {
            "label": semantic_label,
            "log": node['content'],
            "playLog": ["Please inform the contact of the notification"],
            "playPrompt": [f"callflow:{self.callflow_ids['not_home']}"],
            "goto": self.get_next_node(node['id'])
        }
    
    def create_accepted_node(self, node: Dict[str, Any], semantic_label: str) -> Dict[str, Any]:
        """
        Create an Accepted Response node.
        
        Args:
            node: Mermaid node data
            semantic_label: Semantic label for the node
            
        Returns:
            Accepted Response node in the exact format
        """
        return {
            "label": semantic_label,
            "log": node['content'],
            "playLog": ["You have accepted receipt of this message"],
            "playPrompt": [f"callflow:{self.callflow_ids['accepted']}"],
            "goto": self.get_next_node(node['id'])
        }
    
    def create_invalid_entry_node(self, node: Dict[str, Any], semantic_label: str) -> Dict[str, Any]:
        """
        Create an Invalid Entry node.
        
        Args:
            node: Mermaid node data
            semantic_label: Semantic label for the node
            
        Returns:
            Invalid Entry node in the exact format
        """
        return {
            "label": semantic_label,
            "log": node['content'],
            "playLog": ["Invalid entry. Please try again."],
            "playPrompt": [f"callflow:{self.callflow_ids['error']}"],
            "goto": self.get_next_node(node['id'])
        }
    
    def create_goodbye_node(self, node: Dict[str, Any] = None, semantic_label: str = "Goodbye") -> Dict[str, Any]:
        """
        Create a Goodbye node.
        
        Args:
            node: Optional Mermaid node data
            semantic_label: Semantic label for the node
            
        Returns:
            Goodbye node in the exact format
        """
        node_data = {
            "label": semantic_label,
            "log": "Thank you. Goodbye.",
            "playLog": ["Thank you for your response"],
            "playPrompt": [f"callflow:{self.callflow_ids['goodbye']}"],
            "nobarge": "1"
        }
        
        # Add hangup if this is the final node
        if node and self.is_leaf_node(node['id']):
            node_data["hangup"] = "1"
        else:
            node_data["goto"] = "Disconnect"
        
        return node_data
    
    def create_problems_node(self) -> Dict[str, Any]:
        """
        Create a Problems node for error handling.
        
        Returns:
            Problems node in the exact format
        """
        return {
            "label": "Problems",
            "nobarge": "1",
            "playLog": "I'm sorry you are having problems.",
            "playPrompt": [f"callflow:{self.callflow_ids['problems']}"],
            "goto": "Goodbye"
        }
    
    def create_standard_node(self, node: Dict[str, Any], semantic_label: str) -> Dict[str, Any]:
        """
        Create a standard node for other cases.
        
        Args:
            node: Mermaid node data
            semantic_label: Semantic label for the node
            
        Returns:
            Standard node in the exact format
        """
        return {
            "label": semantic_label,
            "log": node['content'],
            "playLog": [node['content'].split('\n')[0]],
            "playPrompt": [f"callflow:{node['id']}"],
            "goto": self.get_next_node(node['id'])
        }
    
    def create_semantic_labels(self) -> Dict[str, str]:
        """
        Create semantic labels for nodes based on their content.
        
        Returns:
            Dictionary mapping node IDs to semantic labels
        """
        semantic_labels = {}
        
        for node_id, node in self.nodes.items():
            content = node['content'].lower()
            
            # Map based on content patterns
            if any(keyword in content for keyword in ["welcome", "important notification", "press 1"]):
                semantic_labels[node_id] = "Live Answer"
            elif "90-second message" in content or "30-second message" in content:
                semantic_labels[node_id] = "Sleep"
            elif "custom message" in content:
                semantic_labels[node_id] = "Custom Message"
            elif "confirm" in content:
                semantic_labels[node_id] = "Confirm"
            elif "not home" in content and "employee" in content:
                semantic_labels[node_id] = "Employee Not Home"
            elif "not home" in content and "contact" in content:
                semantic_labels[node_id] = "Contact Not Home"
            elif "accepted" in content:
                semantic_labels[node_id] = "Accepted"
            elif "invalid" in content:
                semantic_labels[node_id] = "Invalid Entry"
            elif "goodbye" in content or "thank you" in content:
                semantic_labels[node_id] = "Goodbye"
            elif "disconnect" in content:
                semantic_labels[node_id] = "Disconnect"
            elif node['type'] == 'decision':
                if "employee" in content and "contact" in content:
                    semantic_labels[node_id] = "Employee Or Contact"
                else:
                    semantic_labels[node_id] = "Decision"
            else:
                semantic_labels[node_id] = f"Node-{node_id}"
        
        return semantic_labels
    
    def get_next_node(self, node_id: str) -> str:
        """
        Get the next node in the flow.
        
        Args:
            node_id: Current node ID
            
        Returns:
            Next node label or default
        """
        # Find outgoing connections
        for conn in self.connections:
            if conn['from'] == node_id:
                target_id = conn['to']
                
                # Get target content to determine semantic label
                target = self.nodes.get(target_id)
                if target:
                    content = target['content'].lower()
                    
                    if "goodbye" in content or "thank you" in content:
                        return "Goodbye"
                    elif "custom message" in content:
                        return "Custom Message"
                    elif "accepted" in content:
                        return "Accepted"
                    elif "invalid" in content:
                        return "Invalid Entry"
                    elif "confirm" in content:
                        return "Confirm"
                    else:
                        return target_id
        
        # Default to Goodbye if no connections
        return "Goodbye"
    
    def is_leaf_node(self, node_id: str) -> bool:
        """
        Check if a node is a leaf node (no outgoing connections).
        
        Args:
            node_id: Node ID to check
            
        Returns:
            True if leaf node, False otherwise
        """
        return not any(conn['from'] == node_id for conn in self.connections)

def convert_mermaid_to_ivr(mermaid_code: str) -> str:
    """
    Convert Mermaid code to IVR configuration with exact format.
    
    Args:
        mermaid_code: Mermaid diagram code
        
    Returns:
        Formatted IVR code
    """
    converter = ExactIVRConverter()
    return converter.convert(mermaid_code)

if __name__ == "__main__":
    # Test with sample Mermaid code
    sample = """flowchart TD
    A["Welcome<br/>This is an IMPORTANT notification. It is (dow, date, time, time zone).<br/>Press 1 if this is (employee/contact).<br/>Press 3 if you need more time to get (employee/contact) to the phone.<br/>Press 7 if (employee/contact) is not home.<br/>Press 9 to repeat this message."] -->|"input"| B{"9 - repeat or invalid input"}
    B --> A
    B -->|"7 - not home"| C{"Employee or<br/>Contact?"}
    B -->|"3 - need more time"| D["90-second message<br/>Press any key to continue..."]
    B -->|"no input"| D
    B -->|"1 - this is employee"| E["Custom Message<br/>(Play selected custom message.)"]
    C -->|"Employee"| F["Employee Not Home<br/>Please have<br/>(employee) call the<br/>(Level 2) Callout<br/>System at<br/>866-502-7267."]
    C -->|"Contact"| G["Contact Not Home<br/>Please inform the<br/>contact that a (Level<br/>2) Notification<br/>occurred at (time)<br/>on (dow, date)."]
    E -->|"input"| H{"Confirm<br/>To confirm receipt of this<br/>message, press 1.<br/>To replay the message,<br/>press 3."}
    H -->|"1 - accept"| I["Accepted Response<br/>You have accepted<br/>receipt of this message."]
    H -->|"3 - repeat"| E
    H -->|"invalid input"| J["Invalid Entry.<br/>Invalid entry.<br/>Please try again."]
    H -->|"no input"| J
    J --> H
    I --> K["Goodbye<br/>Thank you.<br/>Goodbye."]
    K --> L["Disconnect"]
    F --> K
    G --> K
    """
    
    print(convert_mermaid_to_ivr(sample))