import streamlit as st

def render():
    st.header("Backtest Results")

    st.subheader("Run Backtest")
    col1, col2 = st.columns(2)
    with col1:
        strategy_name = st.text_input("Strategy Name", value="s01_reversing_stupidity")
    with col2:
        initial_balance = st.number_input("Initial Balance ($)", value=10000.0, step=1000.0)

    data_file = st.file_uploader("Upload Historical Data (CSV)", type=["csv"])

    if st.button("Run Backtest"):
        if data_file is None:
            st.warning("Please upload a CSV file with columns: timestamp, condition_id, question, yes_price, no_price, volume")
        else:
            st.info("Backtest execution coming soon. Use CLI: `python main.py backtest`")

    st.markdown("---")
    st.subheader("Performance Metrics")
    st.info("Run a backtest to see performance metrics (Sharpe, MDD, Win Rate, etc.)")
