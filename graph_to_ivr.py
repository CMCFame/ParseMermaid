from typing import Dict, List, Optional, Any
import re
from parse_mermaid import Node, Edge, NodeType

# Mapeo más extenso de frases comunes a prompts de audio
AUDIO_PROMPTS = {
    "Invalid entry. Please try again": "callflow:1009",
    "Goodbye message": "callflow:1029",
    "Please enter your PIN": "callflow:1008",
    "An accepted response has been recorded": "callflow:1167",
    "Your response is being recorded as a decline": "callflow:1021",
    "Please contact your local control center": "callflow:1705",
    "To speak to a dispatcher": "callflow:1645",
    "We were not able to complete the transfer": "callflow:1353",
}

class IVRTransformer:
    def __init__(self):
        self.standard_nodes = {
            "start": {
                "label": "Start",
                "maxLoop": ["Main", 3, "Problems"],
                "nobarge": "1",
                "log": "Entry point to call flow"
            },
            "problems": {
                "label": "Problems",
                "gosub": ["SaveCallResult", 1198, "Error Out"],
                "goto": "Goodbye"
            },
            "goodbye": {
                "label": "Goodbye",
                "log": "Goodbye message",
                "playPrompt": ["callflow:1029"],
                "nobarge": "1",
                "goto": "hangup"
            }
        }
        
        self.result_codes = {
            "accept": (1001, "Accept"),
            "decline": (1002, "Decline"),
            "not_home": (1006, "Not Home"),
            "qualified_no": (1145, "QualNo"),
            "error": (1198, "Error Out")
        }

    def transform(self, graph: Dict) -> List[Dict[str, Any]]:
        """
        Transforma el grafo parseado en una lista de nodos IVR.
        """
        nodes_dict = graph['nodes']
        edges = graph['edges']
        styles = graph.get('styles', {})
        subgraphs = graph.get('subgraphs', {})

        ivr_nodes = []
        
        # Agregar nodo inicial si es necesario
        if not any(n.raw_text.lower().startswith('start') for n in nodes_dict.values()):
            ivr_nodes.append(self.standard_nodes["start"])

        # Procesar cada nodo
        for node_id, node in nodes_dict.items():
            ivr_node = self._transform_node(node, edges, styles)
            if ivr_node:
                ivr_nodes.append(ivr_node)

        # Agregar nodos estándar si no existen
        if not any(n["label"] == "Problems" for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes["problems"])
        if not any(n["label"] == "Goodbye" for n in ivr_nodes):
            ivr_nodes.append(self.standard_nodes["goodbye"])

        return ivr_nodes

    def _transform_node(self, node: Node, edges: List[Edge], styles: Dict) -> Optional[Dict]:
        """
        Transforma un nodo individual al formato IVR.
        """
        node_id = node.id
        raw_text = node.raw_text
        node_type = node.node_type
        
        # Construir nodo base
        ivr_node = {
            "label": self._to_title_case(node_id),
            "log": raw_text
        }

        # Aplicar estilos
        for style_class in node.style_classes:
            if style_class in styles:
                self._apply_style(ivr_node, styles[style_class])

        # Manejar nodos de decisión (rhombus)
        if node_type == NodeType.RHOMBUS:
            self._handle_decision_node(ivr_node, node, edges)
        else:
            self._handle_action_node(ivr_node, node, edges)

        # Agregar comandos especiales basados en el texto o tipo
        self._add_special_commands(ivr_node, raw_text)

        return ivr_node

    def _handle_decision_node(self, ivr_node: Dict, node: Node, edges: List[Edge]):
        """
        Configura un nodo de decisión con getDigits y branch.
        """
        out_edges = [e for e in edges if e.from_id == node.id]
        
        ivr_node["getDigits"] = {
            "numDigits": 1,
            "maxTries": 3,
            "maxTime": 7,
            "validChoices": "",
            "errorPrompt": "callflow:1009",
            "nonePrompt": "callflow:1009"
        }

        branch_map = {}
        digit_choices = []

        for edge in out_edges:
            if edge.label:
                # Detectar patrones en las etiquetas
                digit_match = re.match(r'^(\d+)\s*-\s*(.*)', edge.label)
                if digit_match:
                    digit, action = digit_match.groups()
                    branch_map[digit] = self._to_title_case(edge.to_id)
                    digit_choices.append(digit)
                elif re.search(r'invalid|no input', edge.label, re.IGNORECASE):
                    branch_map["error"] = self._to_title_case(edge.to_id)
                    branch_map["none"] = self._to_title_case(edge.to_id)
                else:
                    branch_map[edge.label] = self._to_title_case(edge.to_id)

        if digit_choices:
            ivr_node["getDigits"]["validChoices"] = "|".join(digit_choices)
        ivr_node["branch"] = branch_map

    def _handle_action_node(self, ivr_node: Dict, node: Node, edges: List[Edge]):
        """
        Configura un nodo de acción con playPrompt y otros comandos.
        """
        out_edges = [e for e in edges if e.from_id == node.id]
        
        # Buscar prompt de audio conocido o usar TTS
        audio_prompt = self._find_audio_prompt(node.raw_text)
        if audio_prompt:
            ivr_node["playPrompt"] = [audio_prompt]
        else:
            ivr_node["playPrompt"] = [f"tts:{node.raw_text}"]

        # Si hay una única salida, agregar goto
        if len(out_edges) == 1:
            ivr_node["goto"] = self._to_title_case(out_edges[0].to_id)

    def _add_special_commands(self, ivr_node: Dict, raw_text: str):
        """
        Agrega comandos especiales basados en el texto del nodo.
        """
        # Detectar comandos gosub basados en el texto
        text_lower = raw_text.lower()
        
        for key, (code, name) in self.result_codes.items():
            if key in text_lower:
                ivr_node["gosub"] = ["SaveCallResult", code, name]
                break

        # Agregar nobarge para ciertos tipos de mensajes
        if any(keyword in text_lower for keyword in ["goodbye", "recorded", "message", "please"]):
            ivr_node["nobarge"] = "1"

        # Detectar transferencias
        if "transfer" in text_lower:
            ivr_node.update({
                "setvar": {"transfer_ringback": "callflow:2223"},
                "include": "../../util/xfer.js",
                "gosub": "XferCall"
            })

    def _find_audio_prompt(self, text: str) -> Optional[str]:
        """
        Busca un prompt de audio que coincida con el texto.
        """
        # Primero buscar coincidencia exacta
        if text in AUDIO_PROMPTS:
            return AUDIO_PROMPTS[text]

        # Luego buscar coincidencia parcial
        text_lower = text.lower()
        for key, prompt in AUDIO_PROMPTS.items():
            if key.lower() in text_lower:
                return prompt

        return None

    @staticmethod
    def _apply_style(ivr_node: Dict, style: str):
        """
        Aplica estilos Mermaid al nodo IVR.
        """
        style_parts = style.split(',')
        for part in style_parts:
            if 'fill' in part:
                # Los estilos de relleno podrían mapear a diferentes comportamientos
                pass
            if 'stroke' in part:
                # Los estilos de borde podrían mapear a diferentes comportamientos
                pass

    @staticmethod
    def _to_title_case(s: str) -> str:
        """
        Convierte strings como 'node_id' a 'Node Id'.
        """
        return ' '.join(word.capitalize() for word in s.replace('_', ' ').split())

def graph_to_ivr(graph: Dict) -> List[Dict[str, Any]]:
    """
    Función wrapper para mantener compatibilidad con código existente.
    """
    transformer = IVRTransformer()
    return transformer.transform(graph)