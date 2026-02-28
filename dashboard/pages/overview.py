import streamlit as st

def render():
    st.header("Portfolio Overview")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Balance", "$10,000.00", "+$0.00")
    with col2:
        st.metric("Active Positions", "0")
    with col3:
        st.metric("Today's P&L", "$0.00", "0.0%")
    with col4:
        st.metric("Active Strategies", "0")

    st.markdown("---")
    st.subheader("Equity Curve")
    st.info("Start the bot to see live equity data. Run: `python main.py run`")

    st.subheader("Recent Trades")
    st.info("No trades yet. Configure strategies in config.yaml and start the bot.")

    st.subheader("Strategy Allocation")
    st.info("Enable strategies in config.yaml to see allocation breakdown.")
