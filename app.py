# app.py
import streamlit as st
import json

from parse_mermaid import parse_mermaid
from graph_to_ivr import graph_to_ivr

def main():
    st.title("Mermaid-to-IVR Converter (Universal)")

    default_mermaid = """flowchart TD
    %% Example with subgraph, special arrow, shape, etc.
    subgraph sg1 [Subgraph #1]
      A((double circle)) --- B@{ shape: diamond, label: "Decision node" }
    end

    subgraph sg2
      X["Multi line? `**bold**`"] --o|invalid input| Y("Round node")
    end

    A -- "1 - accept" --> D
    B -- "3 - decline" --> E
    X -- "2 - no?" --> B
    Y --> A
    """

    st.write("Paste your **Mermaid flowchart** below:")
    mermaid_text = st.text_area("Mermaid Diagram", default_mermaid, height=400)

    if st.button("Convert to IVR JS Code"):
        try:
            parsed = parse_mermaid(mermaid_text)
            ivr_nodes = graph_to_ivr(parsed)
            ivr_code = "module.exports = " + json.dumps(ivr_nodes, indent=2) + ";"
            st.subheader("IVR JavaScript Code")
            st.code(ivr_code, language="javascript")
            st.success("Done! Copy the code above for your IVR.")
        except Exception as e:
            st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
