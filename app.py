import streamlit as st
import streamlit_mermaid as st_mermaid
import json
import yaml
from typing import Optional, Dict, Any
import tempfile
import os

from parse_mermaid import parse_mermaid, MermaidParser
from graph_to_ivr import graph_to_ivr, IVRTransformer

# Configuración de la página
st.set_page_config(
    page_title="Mermaid-to-IVR Converter",
    page_icon="🔄",
    layout="wide"
)

# Constantes y ejemplos
DEFAULT_MERMAID = '''flowchart TD
    start["Start of call"]
    available["Are you available?\nIf yes press 1, if no press 3"]
    input{"input"}
    invalid["Invalid entry. Please try again"]
    accept["Accept"]
    decline["Decline"]
    done["End Flow"]

    start --> available
    available --> input
    input -->|"invalid input\nor no input"| invalid
    invalid --> input
    input -->|"1 - accept"| accept
    input -->|"3 - decline"| decline
    accept --> done
    decline --> done'''

# Funciones auxiliares
def save_temp_file(content: str, suffix: str = '.js') -> str:
    """Guarda contenido en un archivo temporal y retorna la ruta."""
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
        f.write(content)
        return f.name

def load_example_flows() -> Dict[str, str]:
    """Carga flujos de ejemplo predefinidos."""
    return {
        "Simple Callout": DEFAULT_MERMAID,
        "PIN Change": '''flowchart TD
    start["Enter PIN"]
    validate{"Valid PIN?"}
    new_pin["Enter new PIN"]
    confirm["Confirm new PIN"]
    match{"PINs match?"}
    success["PIN changed successfully"]
    error["Invalid entry"]
    
    start --> validate
    validate -->|No| error
    validate -->|Yes| new_pin
    new_pin --> confirm
    confirm --> match
    match -->|No| error
    match -->|Yes| success''',
        "Transfer Flow": '''flowchart TD
    start["Transfer Request"]
    attempt{"Transfer\nAttempt"}
    success["Transfer Complete"]
    fail["Transfer Failed"]
    end["End Call"]
    
    start --> attempt
    attempt -->|Success| success
    attempt -->|Fail| fail
    success & fail --> end'''
    }

def validate_mermaid(mermaid_text: str) -> Optional[str]:
    """Valida el diagrama Mermaid y retorna mensaje de error si existe."""
    try:
        parser = MermaidParser()
        parser.parse(mermaid_text)
        return None
    except Exception as e:
        return f"Error validando diagrama: {str(e)}"

def format_ivr_code(ivr_nodes: list) -> str:
    """Formatea el código IVR con estilo consistente."""
    return "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"

def show_code_diff(original: str, converted: str):
    """Muestra una comparación del código original y convertido."""
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Mermaid Original")
        st.code(original, language="javascript")
    with col2:
        st.subheader("Código IVR Generado")
        st.code(converted, language="javascript")

def main():
    # Título y descripción
    st.title("🔄 Mermaid-to-IVR Converter")
    st.markdown("""
    Esta herramienta convierte diagramas Mermaid en código JavaScript para sistemas IVR.
    Soporta múltiples tipos de nodos, subgráficos y estilos.
    """)

    # Sidebar con opciones
    with st.sidebar:
        st.header("⚙️ Opciones")
        
        # Cargar ejemplo
        example_flows = load_example_flows()
        selected_example = st.selectbox(
            "Cargar ejemplo",
            ["Personalizado"] + list(example_flows.keys())
        )
        
        # Opciones de exportación
        st.subheader("Exportar")
        export_format = st.radio(
            "Formato de exportación",
            ["JavaScript", "JSON", "YAML"]
        )
        
        # Opciones avanzadas
        st.subheader("Opciones Avanzadas")
        add_standard_nodes = st.checkbox("Agregar nodos estándar", value=True)
        validate_diagram = st.checkbox("Validar diagrama", value=True)

    # Área principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Editor de Mermaid
        st.subheader("📝 Editor Mermaid")
        if selected_example != "Personalizado":
            mermaid_text = st.text_area(
                "Diagrama Mermaid",
                example_flows[selected_example],
                height=400
            )
        else:
            mermaid_text = st.text_area(
                "Diagrama Mermaid",
                DEFAULT_MERMAID,
                height=400
            )

    with col2:
        # Vista previa del diagrama actualizada
        st.subheader("👁️ Vista Previa")
        if mermaid_text:
            try:
                st_mermaid.st_mermaid(mermaid_text)
            except Exception as e:
                st.error(f"Error en la vista previa: {str(e)}")

    # Botón de conversión
    if st.button("🔄 Convertir a Código IVR"):
        with st.spinner("Convirtiendo..."):
            # Validación opcional
            if validate_diagram:
                error = validate_mermaid(mermaid_text)
                if error:
                    st.error(error)
                    return

            try:
                # Parsear y convertir
                graph = parse_mermaid(mermaid_text)
                ivr_nodes = graph_to_ivr(graph)
                
                # Formatear según el formato seleccionado
                if export_format == "JavaScript":
                    output = format_ivr_code(ivr_nodes)
                elif export_format == "JSON":
                    output = json.dumps(ivr_nodes, indent=2)
                else:  # YAML
                    output = yaml.dump(ivr_nodes, allow_unicode=True)

                # Mostrar resultado
                st.subheader("📤 Código Generado")
                st.code(output, language="javascript")
                
                # Opciones de descarga
                tmp_file = save_temp_file(output)
                with open(tmp_file, 'rb') as f:
                    st.download_button(
                        label="⬇️ Descargar Código",
                        data=f,
                        file_name=f"ivr_flow.{export_format.lower()}",
                        mime="text/plain"
                    )
                os.unlink(tmp_file)

                # Mostrar diferencias
                show_code_diff(mermaid_text, output)

            except Exception as e:
                st.error(f"Error en la conversión: {str(e)}")
                st.exception(e)

if __name__ == "__main__":
    main()