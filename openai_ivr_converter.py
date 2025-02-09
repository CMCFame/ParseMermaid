"""
Enhanced OpenAI-based IVR conversion with detailed debugging
"""
from typing import Dict, List, Any
from openai import OpenAI, OpenAIError
import json
import logging
import traceback
import sys

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class OpenAIIVRConverter:
    def __init__(self, api_key: str):
        logger.info("Initializing OpenAIIVRConverter")
        if not api_key:
            raise ValueError("OpenAI API key is required")
        try:
            self.client = OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            raise

    def convert_to_ivr(self, mermaid_code: str) -> str:
        """Convert Mermaid diagram to IVR configuration using GPT-4"""
        logger.info("Starting conversion process")
        logger.debug(f"Input Mermaid code length: {len(mermaid_code)}")
        
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
           - Do not include any subgraphs or notes in the conversion

        6. Required Flow Elements:
           - Welcome message with options 1,3,7,9
           - 30-second message with return to welcome
           - PIN entry and validation flow
           - Electric callout announcement
           - Callout reason and location
           - Availability check with options 1,3,9
           - Response recording (Accept/Decline/Qualified No)
           - Proper goodbye and disconnect handling

        Here's the Mermaid diagram to convert:

        {mermaid_code}

        Create an IVR configuration that matches this flow EXACTLY, with every node, path, and option preserved.
        Return only the JavaScript code in module.exports format. Do not include any explanations or comments."""

        try:
            logger.info("Making OpenAI API call")
            response = self.client.chat.completions.create(
                model="gpt-4",
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
                temperature=0.1,
                max_tokens=4000
            )
            logger.info("Received response from OpenAI")
            logger.debug(f"Response status: {response.model_dump()}")

            # Extract and clean the response
            ivr_code = response.choices[0].message.content.strip()
            logger.debug(f"Generated IVR code length: {len(ivr_code)}")
            
            # Extract just the JavaScript code
            if "module.exports = [" in ivr_code:
                start_idx = ivr_code.find("module.exports = [")
                end_idx = ivr_code.rfind("];") + 2
                ivr_code = ivr_code[start_idx:end_idx]
                logger.info("Successfully extracted code section")
            else:
                logger.warning("Could not find module.exports section in response")
                logger.debug(f"Full response content: {ivr_code}")
                raise ValueError("Invalid response format from OpenAI")

            # Validate the generated code
            try:
                self._validate_ivr_code(ivr_code)
                logger.info("IVR code validation passed")
            except ValueError as ve:
                logger.error(f"IVR code validation failed: {str(ve)}")
                raise

            return ivr_code

        except OpenAIError as oe:
            logger.error(f"OpenAI API error: {str(oe)}")
            logger.debug(f"OpenAI error details: {traceback.format_exc()}")
            raise
        except Exception as e:
            logger.error(f"IVR conversion failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return '''module.exports = [
  {
    "label": "Problems",
    "log": "Error handler",
    "playPrompt": ["callflow:1351"],
    "goto": "Goodbye"
  }
];'''

    def _validate_ivr_code(self, ivr_code: str):
        """Validate the generated IVR code structure"""
        try:
            # Remove module.exports wrapper
            json_str = ivr_code[16:-1].strip()
            nodes = json.loads(json_str)

            if not isinstance(nodes, list):
                raise ValueError("Generated code is not a valid node array")

            required_nodes = {
                "Welcome",
                "EnterPin",
                "ElectricCallout",
                "CalloutReason",
                "TroubleLocation",
                "CustomMessage",
                "AvailableForCallout",
                "AcceptedResponse",
                "CalloutDecline",
                "QualifiedNo",
                "Goodbye"
            }

            found_nodes = set()
            for node in nodes:
                if not isinstance(node, dict):
                    raise ValueError("Invalid node structure")
                
                if 'label' not in node:
                    raise ValueError("Node missing label property")
                
                found_nodes.add(node['label'])
                
                # Validate required properties based on node type
                if "getDigits" in node:
                    required_props = ["numDigits", "maxTries", "errorPrompt"]
                    if not all(prop in node["getDigits"] for prop in required_props):
                        raise ValueError(f"Missing required getDigits properties in node {node['label']}")
                
                # Validate audio prompts
                if "playPrompt" in node and not all(p.startswith("callflow:") for p in node["playPrompt"]):
                    raise ValueError(f"Invalid audio prompt format in node {node['label']}")

            # Check for missing required nodes
            missing_nodes = required_nodes - found_nodes
            if missing_nodes:
                raise ValueError(f"Missing required nodes: {missing_nodes}")

        except json.JSONDecodeError as je:
            logger.error(f"JSON decode error: {str(je)}")
            logger.debug(f"Invalid JSON content: {ivr_code}")
            raise ValueError("Generated code is not valid JSON")
        except Exception as e:
            raise ValueError(f"Validation error: {str(e)}")

def convert_mermaid_to_ivr(mermaid_code: str, api_key: str) -> str:
    """Wrapper function for Mermaid to IVR conversion"""
    try:
        logger.info("Starting conversion with wrapper function")
        converter = OpenAIIVRConverter(api_key)
        return converter.convert_to_ivr(mermaid_code)
    except Exception as e:
        logger.error(f"Wrapper function error: {str(e)}")
        raise