"""
Enhanced OpenAI-powered IVR conversion with improved prompt engineering
"""
from typing import Dict, List, Any
from openai import OpenAI
import json
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class IVRPromptTemplate:
    """IVR-specific prompt templates"""
    
    SYSTEM_ROLE = """You are an expert IVR (Interactive Voice Response) system developer specializing in converting flowcharts into precise IVR configurations. Your task is to create exact, working IVR code that matches the input flow diagram perfectly."""

    EXAMPLE_IVR = """{
        "label": "Welcome",
        "log": "Initial greeting and menu options",
        "playPrompt": ["callflow:1001"],
        "getDigits": {
            "numDigits": 1,
            "maxTries": 3,
            "validChoices": "1|3|7|9",
            "errorPrompt": "callflow:1009",
            "timeoutPrompt": "callflow:1010"
        },
        "branch": {
            "1": "EnterPin",
            "3": "NeedMoreTime",
            "7": "NotHome",
            "9": "Welcome"
        }
    }"""

    CONVERSION_PROMPT = """Create a precise IVR configuration from this Mermaid flowchart following these requirements:

1. Exact Node Mapping:
   - Every node in the diagram must have a corresponding IVR configuration
   - Maintain all decision points and branches exactly as shown
   - Keep all retry logic and error handling paths
   - Preserve the exact flow sequence

2. Audio Prompts (use exact callflow IDs):
   - Welcome/Menu: callflow:1001
   - PIN Entry: callflow:1008
   - Invalid Input: callflow:1009
   - Timeout: callflow:1010
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
   - Error: callflow:1351

3. Response Codes:
   SaveCallResult parameters must use exact codes:
   - Accept: [1001, "Accept"]
   - Decline: [1002, "Decline"]
   - Not Home: [1006, "NotHome"]
   - Qualified No: [1145, "QualNo"]
   - Error: [1198, "Error Out"]

4. Required Node Properties:
   - label: Unique identifier for the node
   - log: Description of the node's purpose
   - playPrompt: Array of audio prompt IDs
   - getDigits (for input nodes):
     * numDigits: Number of digits to collect
     * maxTries: Maximum retry attempts
     * validChoices: Allowed inputs
     * errorPrompt: Invalid input message
     * timeoutPrompt: Timeout message
   - branch: Conditional paths based on input
   - goto: Direct transition to next node
   - gosub (for response recording): SaveCallResult parameters

5. Special Handling:
   - PIN verification must include both digit entry and validation
   - Retry logic must match diagram exactly (including max retries)
   - Availability check must include all options (1,3,9)
   - Error handling must include proper recovery paths
   - Timeout handling must be included where shown

Here's the Mermaid diagram to convert:

{mermaid_code}

Return only valid JavaScript code in this exact format:
module.exports = [
    // IVR nodes here
];

Each node must follow the example structure with appropriate modifications based on its role in the flow."""

class OpenAIIVRConverter:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OpenAI API key is required")
        self.client = OpenAI(api_key=api_key)
        logger.info("OpenAI IVR converter initialized")

    def convert_to_ivr(self, mermaid_code: str) -> str:
        """Convert Mermaid diagram to IVR configuration"""
        try:
            logger.info("Starting conversion process")
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": IVRPromptTemplate.SYSTEM_ROLE
                    },
                    {
                        "role": "user",
                        "content": IVRPromptTemplate.CONVERSION_PROMPT.format(
                            mermaid_code=mermaid_code
                        )
                    }
                ],
                temperature=0.1,  # Low temperature for consistent output
                max_tokens=4000
            )
            
            logger.info("Received response from OpenAI")
            ivr_code = response.choices[0].message.content.strip()
            
            # Validate the response
            if not ivr_code.startswith("module.exports = ["):
                logger.warning("Response doesn't match expected format")
                ivr_code = f"module.exports = {ivr_code};"
            
            # Validate JSON structure
            try:
                # Extract the array part
                json_str = ivr_code[16:-1].strip()  # Remove "module.exports = " and ";"
                nodes = json.loads(json_str)
                
                if not isinstance(nodes, list):
                    raise ValueError("Generated code is not a valid node array")
                
                for node in nodes:
                    self._validate_node(node)
                
                logger.info("Validation successful")
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON validation failed: {str(e)}")
                raise ValueError("Generated code is not valid JSON")
            except Exception as e:
                logger.error(f"Node validation failed: {str(e)}")
                raise
            
            return ivr_code

        except Exception as e:
            logger.error(f"Conversion failed: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

    def _validate_node(self, node: Dict):
        """Validate individual IVR node structure"""
        required_fields = {'label', 'log'}
        if not all(field in node for field in required_fields):
            raise ValueError(f"Missing required fields: {required_fields - set(node.keys())}")
        
        if 'playPrompt' in node:
            if not isinstance(node['playPrompt'], list):
                raise ValueError("playPrompt must be an array")
            for prompt in node['playPrompt']:
                if not isinstance(prompt, str) or not prompt.startswith('callflow:'):
                    raise ValueError(f"Invalid prompt format: {prompt}")
        
        if 'getDigits' in node:
            required_digit_fields = {'numDigits', 'maxTries', 'errorPrompt'}
            if not all(field in node['getDigits'] for field in required_digit_fields):
                raise ValueError("Missing required getDigits fields")

def convert_mermaid_to_ivr(mermaid_code: str, api_key: str) -> str:
    """Wrapper function for Mermaid to IVR conversion"""
    try:
        converter = OpenAIIVRConverter(api_key)
        return converter.convert_to_ivr(mermaid_code)
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        # Return a basic error handler node
        return '''module.exports = [
    {
        "label": "Problems",
        "log": "Error handler",
        "playPrompt": ["callflow:1351"],
        "goto": "Goodbye"
    }
];'''