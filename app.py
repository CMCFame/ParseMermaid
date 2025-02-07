# app.py

import streamlit as st
import json

from parse_mermaid import parse_mermaid
from graph_to_ivr import graph_to_ivr

def main():
    st.title("Mermaid-to-IVR Converter (with Missing Pieces)")

    default_mermaid = """flowchart TD
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
        decline --> done
    """

    st.write("Paste your **Mermaid flowchart** below:")
    mermaid_text = st.text_area("Mermaid Diagram", default_mermaid, height=300)

    if st.button("Convert to IVR JS Code"):
        # 1) parse
        graph = parse_mermaid(mermaid_text)
        # 2) convert
        ivr_nodes = graph_to_ivr(graph)
        
        # 3) build final code
        ivr_code = "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"

        st.subheader("IVR JavaScript Code")
        st.code(ivr_code, language="javascript")
        st.success("Done! Copy the code above for your IVR.")

if __name__ == "__main__":
    main()
