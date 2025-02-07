import streamlit as st
import json

from parse_mermaid import parse_mermaid
from graph_to_ivr import graph_to_ivr

def main():
    st.title("Mermaid-to-IVR Converter")

    default_mermaid = """flowchart TD
    all_hands["Please listen carefully\\nThis is an important all hands message"]
    custom_msg["Custom Message (if selected)"]
    available["Are you available?\\nIf yes press 1, if no press 3"]
    input{"input"}
    invalid_entry["Invalid entry\\nPlease try again"]
    accepted["Response accepted"]
    decline["Response declined"]
    disconnect["Hang up or main menu"]
    main_menu["Main Menu"]
    
    all_hands --> custom_msg
    custom_msg --> available
    available --> input
    input -->|"invalid input or no input"| invalid_entry
    invalid_entry -->|"retry"| input
    input -->|"1 - accept"| accepted
    input -->|"3 - decline"| decline
    accepted --> disconnect
    decline --> disconnect
    disconnect --> main_menu
    """

    st.write("Paste your **Mermaid flowchart** below (one at a time).")
    mermaid_text = st.text_area("Mermaid Diagram", default_mermaid, height=300)

    if st.button("Convert to IVR JS Code"):
        # 1) parse
        graph = parse_mermaid(mermaid_text)
        # 2) convert
        ivr_nodes = graph_to_ivr(graph)
        
        # 3) Build final code:
        # We'll do a quick JSON dump. 
        # If you want "module.exports = [...]", just do that:
        ivr_code = "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"

        st.subheader("IVR JavaScript Code")
        st.code(ivr_code, language="javascript")

        st.success("Done! Copy the code above as needed.")

if __name__ == "__main__":
    main()
