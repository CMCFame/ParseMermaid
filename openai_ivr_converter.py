"""
Enhanced OpenAI-based IVR conversion with exact flow matching
"""
from typing import Dict, List, Any
from openai import OpenAI
import json
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class OpenAIIVRConverter:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def convert_to_ivr(self, mermaid_code: str) -> str:
        """Convert Mermaid diagram to IVR configuration using GPT-4"""
        
        prompt = f"""You are an expert IVR system developer. Create a precise, 1:1 IVR configuration from this Mermaid flowchart following these exact requirements:

        1. Node Structure Requirements:
           - Each node needs exact properties depending on its type:
             * Welcome/Menu nodes need getDigits with specific options
             * Decision nodes need branch logic with all paths
             * Response nodes need appropriate callflow IDs
             * All nodes need proper goto or branch properties

        2. Exact Audio Prompts to Use:
           Welcome/Initial: callflow:1001
           PIN Entry: callflow:1008
           Invalid Input: callflow:1009
           Timeout: callflow:1010
           Electric Callout: callflow:1274
           Callout Reason: callflow:1019
           Location Info: callflow:1232
           Wait/30-sec: callflow:1265
           Not Home: callflow:1017
           Available Check: callflow:1316
           Accept: callflow:1167
           Decline: callflow:1021
           Qualified No: callflow:1266
           Goodbye: callflow:1029
           Error: callflow:1351

        3. Response Code Standards:
           Accept: SaveCallResult [1001, "Accept"]
           Decline: SaveCallResult [1002, "Decline"]
           Not Home: SaveCallResult [1006, "NotHome"]
           Qualified No: SaveCallResult [1145, "QualNo"]
           Error: SaveCallResult [1198, "Error Out"]

        4. Required Node Structure Example:
           Welcome/Menu Node:
           {{
             "label": "Welcome",
             "log": "Initial greeting",
             "playPrompt": ["callflow:1001"],
             "getDigits": {{
               "numDigits": 1,
               "maxTries": 3,
               "validChoices": "1|3|7|9",
               "errorPrompt": "callflow:1009",
               "timeoutPrompt": "callflow:1010"
             }},
             "branch": {{
               "1": "EnterPin",
               "3": "NeedMoreTime",
               "7": "NotHome",
               "9": "Welcome"
             }}
           }}

        5. CRITICAL: Match these exact patterns:
           - PIN verification needs both digit entry and validation checks
           - Error handling must include retry paths
           - Maintain all timeout and retry logic
           - Every path must be preserved exactly as shown
           - Response nodes must have correct SaveCallResult commands
           - All prompts must match the exact text shown

        Here's the Mermaid diagram to convert:

        {mermaid_code}

        Create an IVR configuration that matches this flow EXACTLY, with every node, path, and option preserved.
        Return only the JavaScript code in module.exports format."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert IVR system developer specialized in creating exact 1:1 IVR configurations from flowcharts. Every node and path must be preserved precisely."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent output
                max_tokens=4000
            )

            # Extract and clean the response
            ivr_code = response.choices[0].message.content.strip()
            
            # Extract just the JavaScript code
            if "module.exports = [" in ivr_code:
                start_idx = ivr_code.find("module.exports = [")
                end_idx = ivr_code.rfind("];") + 2
                ivr_code = ivr_code[start_idx:end_idx]

            # Validate basic structure
            if not (ivr_code.startswith("module.exports = [") and ivr_code.endswith("];")):
                raise ValueError("Invalid IVR code format generated")

            # Basic validation of node structure
            try:
                nodes = json.loads(ivr_code[16:-1])  # Remove module.exports = and ;
                if not isinstance(nodes, list):
                    raise ValueError("Generated code is not a valid node array")
                for node in nodes:
                    if not isinstance(node, dict) or 'label' not in node:
                        raise ValueError("Invalid node structure")
                    
                    # Verify required properties based on node type
                    if "getDigits" in node:
                        required_props = ["numDigits", "maxTries", "errorPrompt"]
                        if not all(prop in node["getDigits"] for prop in required_props):
                            raise ValueError(f"Missing required getDigits properties in node {node['label']}")
                    
                    # Verify correct audio prompts
                    if "playPrompt" in node and not all(p.startswith("callflow:") for p in node["playPrompt"]):
                        raise ValueError(f"Invalid audio prompt format in node {node['label']}")

            except json.JSONDecodeError:
                raise ValueError("Generated code is not valid JSON")

            return ivr_code

        except Exception as e:
            logger.error(f"IVR conversion failed: {str(e)}")
            # Return a basic error handler node
            return '''module.exports = [
  {
    "label": "Problems",
    "log": "Error handler",
    "playPrompt": ["callflow:1351"],
    "goto": "Goodbye"
  }
];'''

    def _validate_flow_completeness(self, nodes: List[Dict]) -> bool:
        """Validate that all required nodes and paths are present"""
        required_nodes = {
            "Welcome", "EnterPin", "InvalidEntry", "ElectricCallout",
            "CalloutReason", "TroubleLocation", "CustomMessage",
            "AvailableForCallout", "AcceptedResponse", "CalloutDecline",
            "QualifiedNo", "Goodbye"
        }
        
        node_labels = {node["label"] for node in nodes}
        return required_nodes.issubset(node_labels)

def convert_mermaid_to_ivr(mermaid_code: str, api_key: str) -> str:
    """Wrapper function for Mermaid to IVR conversion"""
    converter = OpenAIIVRConverter(api_key)
    return converter.convert_to_ivr(mermaid_code)