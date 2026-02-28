import streamlit as st

def render():
    st.header("Live Market Scanner")

    st.info("Connect to Polymarket API to scan live markets.")

    col1, col2 = st.columns(2)
    with col1:
        min_volume = st.number_input("Min Volume ($)", value=1000, step=500)
    with col2:
        min_edge = st.number_input("Min Edge (%)", value=5.0, step=1.0)

    if st.button("Scan Markets"):
        st.info("Market scanning requires API connection. Configure .env and start the bot.")

    st.markdown("---")
    st.subheader("Detected Opportunities")
    st.info("No opportunities detected. Start the bot to see live signals.")
