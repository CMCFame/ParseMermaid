"""
Direct IVR conversion using OpenAI with specific IVR format handling
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
        
        prompt = f"""You are an expert IVR system developer. Create an exact 1:1 conversion of this IVR flow diagram into JavaScript code. Each node and path in the Mermaid diagram must have a corresponding IVR configuration.

        Rules for conversion:
        1. Initial Welcome Node ("This is an electric callout..."):
           {{
             "label": "Welcome",
             "log": "Initial welcome and menu options",
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

        2. PIN Entry and Validation:
           - First check for entered digits
           - Then validate PIN
           - Include retry paths
           - Use callflow:1008 for PIN prompt

        3. Response Nodes:
           Accepted Response:
           {{
             "label": "AcceptedResponse",
             "log": "Response accepted",
             "playPrompt": ["callflow:1167"],
             "gosub": ["SaveCallResult", 1001, "Accept"],
             "goto": "Goodbye"
           }}

        4. Audio Prompt Mapping:
           - Welcome/Menu: callflow:1001
           - PIN Entry: callflow:1008
           - Invalid Input: callflow:1009
           - Electric Callout: callflow:1274
           - Callout Reason: callflow:1019
           - Location Info: callflow:1232
           - Wait Message: callflow:1265
           - Not Home: callflow:1017
           - Available Check: callflow:1316
           - Accept: callflow:1167
           - Decline: callflow:1021
           - Qualified No: callflow:1266
           - Goodbye: callflow:1029

        5. SaveCallResult Codes:
           - Accept: [1001, "Accept"]
           - Decline: [1002, "Decline"]
           - Not Home: [1006, "NotHome"]
           - Qualified No: [1145, "QualNo"]
           - Error: [1198, "Error Out"]

        Critical Requirements:
        1. Every node in the Mermaid diagram must have a corresponding IVR node
        2. Every connection and condition must be preserved
        3. Retry logic must match the diagram exactly
        4. Error handling paths must be maintained
        5. All menu options and input handling must match
        6. PIN verification flow must include both checks shown in diagram
        7. Available for Callout must include all options (1,3,9)
        8. Preserve the exact flow sequence

        Here's the Mermaid diagram:

        {mermaid_code}

        Convert this diagram into a complete IVR configuration, ensuring every node and path is preserved exactly.
        Return only the JavaScript code in module.exports format."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",  # Note: Changed from gpt-4o to gpt-4
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert IVR system developer. Your task is to create exact 1:1 conversions from flowcharts to IVR code, preserving every node, path, and condition precisely."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=4000
            )

            # Extract and clean the response
            ivr_code = response.choices[0].message.content.strip()
            
            # Extract just the JavaScript code
            if "module.exports = [" in ivr_code:
                start_idx = ivr_code.find("module.exports = [")
                end_idx = ivr_code.rfind("];") + 2
                ivr_code = ivr_code[start_idx:end_idx]

            # Validate code
            try:
                # Remove module.exports wrapper for validation
                json_str = ivr_code[16:-1]  # Remove "module.exports = " and ";"
                nodes = json.loads(json_str)
                
                # Validate node structure
                required_nodes = [
                    "Welcome", "EnterPin", "ElectricCallout", 
                    "CalloutReason", "TroubleLocation", "CustomMessage",
                    "AvailableForCallout", "AcceptedResponse", "CalloutDecline",
                    "QualifiedNo", "Goodbye"
                ]
                
                found_nodes = set(node['label'] for node in nodes if isinstance(node, dict) and 'label' in node)
                missing_nodes = set(required_nodes) - found_nodes
                
                if missing_nodes:
                    logger.warning(f"Missing nodes: {missing_nodes}")
                    raise ValueError("Generated code missing required nodes")

            except json.JSONDecodeError:
                raise ValueError("Generated code is not valid JSON")

            return ivr_code

        except Exception as e:
            logger.error(f"IVR conversion failed: {str(e)}")
            return '''module.exports = [
  {
    "label": "Problems",
    "log": "Error handler",
    "playPrompt": ["callflow:1351"],
    "goto": "Goodbye"
  }
];'''

def convert_mermaid_to_ivr(mermaid_code: str, api_key: str) -> str:
    """Wrapper function for Mermaid to IVR conversion"""
    converter = OpenAIIVRConverter(api_key)
    return converter.convert_to_ivr(mermaid_code)