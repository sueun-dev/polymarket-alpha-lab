import streamlit as st

def render():
    st.header("Read-only Market Scanner")

    st.info("Scan public Polymarket data and generate strategy signals without placing orders.")

    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Min Volume ($)", value=1000, step=500)
    with col2:
        st.number_input("Min Edge (%)", value=5.0, step=1.0)

    if st.button("Scan Markets"):
        st.info("Use the CLI for now: `python main.py scan --limit 20`.")

    st.markdown("---")
    st.subheader("Detected Signals")
    st.info("No scan has been run in this Streamlit page yet.")
