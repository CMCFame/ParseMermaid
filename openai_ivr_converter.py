"""
Enhanced OpenAI-powered IVR conversion with improved prompt engineering and validation
"""
from typing import Dict, List, Any, Optional
from openai import OpenAI
import json
import logging
import traceback
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class NodeType(Enum):
    """IVR node types"""
    MENU = "menu"
    INPUT = "input"
    TRANSFER = "transfer"
    ERROR = "error"
    ACTION = "action"
    PROMPT = "prompt"

class IVRPromptTemplate:
    """IVR-specific enhanced prompt templates"""
    
    SYSTEM_ROLE = """You are an expert IVR developer specialized in converting Mermaid flowcharts to precise IVR JavaScript code. Your expertise includes:
- Complex menu structures and navigation
- Input validation and error handling
- Audio prompt management
- Call flow control and branching logic

Key Capabilities:
1. Menu Creation: Build hierarchical menu structures with proper prompt IDs
2. Input Handling: Implement robust input collection with validation
3. Error Management: Create comprehensive error handling paths
4. Transfer Logic: Implement proper call transfer mechanisms
5. State Management: Track and manage call state effectively"""

    CONVERSION_RULES = """Convert following these exact IVR patterns:

1. Menu Structure:
   {
       "label": "MainMenu",
       "playMenu": [
           {"press": "1", "prompt": "callflow:1234", "log": "Description"},
           {"press": "2", "prompt": "callflow:5678", "log": "Description"}
       ],
       "getDigits": {
           "numDigits": 1,
           "maxTries": 3,
           "timeoutSeconds": 5,
           "validChoices": "1|2",
           "errorPrompt": "callflow:1009",
           "timeoutPrompt": "callflow:1010"
       },
       "branch": {
           "1": "NextNode1",
           "2": "NextNode2",
           "error": "ErrorHandler",
           "timeout": "TimeoutHandler"
       }
   }

2. Input Collection:
   {
       "label": "GetPin",
       "playPrompt": "callflow:1008",
       "getDigits": {
           "numDigits": 4,
           "terminator": "#",
           "maxTries": 3,
           "validChoices": "{{pin}}",
           "errorPrompt": "callflow:1009"
       },
       "branch": {
           "valid": "ValidatePin",
           "error": "ErrorHandler"
       }
   }

3. Error Handling:
   {
       "label": "ErrorHandler",
       "maxLoop": ["Loop-Name", 3, "Problems"],
       "playPrompt": "callflow:1351",
       "goto": "MainMenu"
   }

4. Transfer Logic:
   {
       "label": "TransferToAgent",
       "log": "Transferring call to agent",
       "setvar": {
           "transfer_ringback": "callflow:2223"
       },
       "include": "../../util/xfer.js",
       "gosub": "XferCall",
       "branch": {
           "success": "Goodbye",
           "failure": "TransferError"
       }
   }

5. Call State Management:
   {
       "label": "SaveCallResult",
       "gosub": ["SaveCallResult", "{{result_code}}", "{{result_description}}"],
       "goto": "NextStep"
   }"""

    COMMON_PATTERNS = {
        "welcome": {
            "prompt": "callflow:1001",
            "type": NodeType.PROMPT
        },
        "pin_entry": {
            "prompt": "callflow:1008",
            "type": NodeType.INPUT
        },
        "invalid_input": {
            "prompt": "callflow:1009",
            "type": NodeType.ERROR
        },
        "timeout": {
            "prompt": "callflow:1010",
            "type": NodeType.ERROR
        },
        "transfer": {
            "prompt": "callflow:2223",
            "type": NodeType.TRANSFER
        }
    }

    @classmethod
    def create_conversion_prompt(cls, mermaid_code: str) -> str:
        return f"""Analyze this Mermaid flowchart and convert it to a precise IVR configuration:

{mermaid_code}

Key Requirements:
1. Each diamond node (?) becomes a decision point with getDigits
2. Each rectangular node becomes a playPrompt or action
3. Edge labels with numbers become menu options
4. Create proper error handling for each input
5. Include timeout handling where needed
6. Maintain the exact flow logic
7. Use appropriate prompt IDs from the COMMON_PATTERNS
8. Implement proper call state management
9. Include proper logging for each node

Additional Guidelines:
- Start with module.exports = [
- Each node must have a unique label
- Include proper error recovery paths
- Implement retry logic where appropriate
- Add guards for secure operations
- Use gosub for reusable components
- Handle all possible user inputs
- Include proper transfer logic
- Manage call state consistently

Return only valid JavaScript in module.exports format."""

class IVRNodeValidator:
    """Validates IVR node structures"""
    
    REQUIRED_FIELDS = {
        NodeType.MENU: {'label', 'playMenu', 'getDigits'},
        NodeType.INPUT: {'label', 'playPrompt', 'getDigits'},
        NodeType.TRANSFER: {'label', 'setvar', 'gosub'},
        NodeType.ERROR: {'label', 'playPrompt', 'goto'},
        NodeType.ACTION: {'label', 'log'},
        NodeType.PROMPT: {'label', 'playPrompt'}
    }
    
    @classmethod
    def validate_node(cls, node: dict, node_type: NodeType) -> bool:
        """Validate node structure based on type"""
        try:
            if not isinstance(node_type, NodeType):
                raise ValueError(f"Invalid node type: {node_type}")
                
            required = cls.REQUIRED_FIELDS[node_type]
            if not all(field in node for field in required):
                raise ValueError(f"Missing required fields for {node_type.value}: {required - set(node.keys())}")
            
            if 'getDigits' in node:
                cls._validate_get_digits(node['getDigits'])
                
            if 'playPrompt' in node:
                cls._validate_prompts(node['playPrompt'])
                
            if 'branch' in node:
                cls._validate_branch(node['branch'])
                
            return True
            
        except Exception as e:
            logger.error(f"Node validation failed: {str(e)}")
            raise
    
    @classmethod
    def _validate_get_digits(cls, get_digits: dict):
        """Validate getDigits configuration"""
        required = {'numDigits', 'maxTries', 'errorPrompt'}
        if not all(field in get_digits for field in required):
            raise ValueError(f"Invalid getDigits configuration: missing {required - set(get_digits.keys())}")
    
    @classmethod
    def _validate_prompts(cls, prompts):
        """Validate prompt IDs"""
        if isinstance(prompts, str):
            prompts = [prompts]
        
        for prompt in prompts:
            if not isinstance(prompt, str) or not prompt.startswith('callflow:'):
                raise ValueError(f"Invalid prompt format: {prompt}")
    
    @classmethod
    def _validate_branch(cls, branch: dict):
        """Validate branch configuration"""
        if not isinstance(branch, dict):
            raise ValueError("Branch must be a dictionary")
        if 'error' not in branch:
            raise ValueError("Branch must include error handling")

class OpenAIIVRConverter:
    """Enhanced OpenAI-powered IVR converter"""
    
    def __init__(self, api_key: str):
        """Initialize converter with OpenAI client"""
        if not api_key:
            raise ValueError("OpenAI API key is required")
            
        self.client = OpenAI(api_key=api_key)
        self.validator = IVRNodeValidator()
        logger.info("OpenAI IVR converter initialized")

    def convert_to_ivr(self, mermaid_code: str) -> str:
        """
        Convert Mermaid diagram to IVR configuration
        
        Args:
            mermaid_code: Mermaid diagram syntax
            
        Returns:
            str: Generated IVR JavaScript code
        """
        try:
            logger.info("Starting conversion process")
            
            # Generate conversion prompt
            prompt = IVRPromptTemplate.create_conversion_prompt(mermaid_code)
            
            # Get completion from OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": IVRPromptTemplate.SYSTEM_ROLE + "\n\n" + 
                                 IVRPromptTemplate.CONVERSION_RULES
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent output
                max_tokens=4000
            )
            
            logger.info("Received response from OpenAI")
            ivr_code = response.choices[0].message.content.strip()
            
            # Validate and format the response
            ivr_code = self._process_response(ivr_code)
            
            return ivr_code
            
        except Exception as e:
            logger.error(f"Conversion failed: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

    def _process_response(self, ivr_code: str) -> str:
        """Process and validate OpenAI response"""
        try:
            # Ensure proper module.exports format
            if not ivr_code.startswith("module.exports = ["):
                ivr_code = f"module.exports = {ivr_code};"
            
            # Extract the array part
            json_str = ivr_code[16:-1].strip()  # Remove "module.exports = " and ";"
            nodes = json.loads(json_str)
            
            if not isinstance(nodes, list):
                raise ValueError("Generated code is not a valid node array")
            
            # Validate each node
            for node in nodes:
                node_type = self._determine_node_type(node)
                self.validator.validate_node(node, node_type)
            
            # Format the code
            formatted_code = self._format_ivr_code(nodes)
            
            logger.info("Validation and formatting successful")
            return formatted_code
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON validation failed: {str(e)}")
            raise ValueError("Generated code is not valid JSON")
        except Exception as e:
            logger.error(f"Response processing failed: {str(e)}")
            raise

    def _determine_node_type(self, node: dict) -> NodeType:
        """Determine the type of IVR node"""
        if 'playMenu' in node:
            return NodeType.MENU
        elif 'getDigits' in node and 'playPrompt' in node:
            return NodeType.INPUT
        elif 'setvar' in node and 'transfer' in str(node).lower():
            return NodeType.TRANSFER
        elif 'goto' in node and 'error' in str(node).lower():
            return NodeType.ERROR
        elif 'playPrompt' in node:
            return NodeType.PROMPT
        return NodeType.ACTION

    def _format_ivr_code(self, nodes: List[dict]) -> str:
        """Format IVR code with proper indentation and structure"""
        formatted_nodes = json.dumps(nodes, indent=4)
        return f"module.exports = {formatted_nodes};"

def convert_mermaid_to_ivr(mermaid_code: str, api_key: str) -> str:
    """
    Convenience wrapper for Mermaid to IVR conversion
    
    Args:
        mermaid_code: Mermaid diagram syntax
        api_key: OpenAI API key
        
    Returns:
        str: Generated IVR JavaScript code
    """
    try:
        converter = OpenAIIVRConverter(api_key)
        return converter.convert_to_ivr(mermaid_code)
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        return '''module.exports = [
    {
        "label": "Problems",
        "log": "Error handler - conversion failed",
        "playPrompt": ["callflow:1351"],
        "goto": "Goodbye"
    }
];'''