import streamlit as st

def render():
    st.header("Strategy Research Overview")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Research Corpus", "100 strategies")
    with col2:
        st.metric("Execution Layer", "Removed")
    with col3:
        st.metric("Order Placement", "None")
    with col4:
        st.metric("Mode", "Read-only")

    st.markdown("---")
    st.subheader("Strategy Signals")
    st.info("Use `python main.py scan` to run a one-shot read-only strategy scan.")

    st.subheader("Backtests")
    st.info("Use `python main.py backtest` to evaluate strategies on historical data.")

    st.subheader("Strategy Catalog")
    st.info("Use `python main.py list` to inspect the full strategy registry.")
