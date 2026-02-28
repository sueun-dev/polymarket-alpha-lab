import streamlit as st

st.set_page_config(page_title="Polymarket Alpha Lab", page_icon="📊", layout="wide")

st.title("📊 Polymarket Alpha Lab")
st.markdown("---")

# Sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Overview", "Strategies", "Markets", "Backtest"])

if page == "Overview":
    from dashboard.pages.overview import render
    render()
elif page == "Strategies":
    from dashboard.pages.strategies import render
    render()
elif page == "Markets":
    from dashboard.pages.markets import render
    render()
elif page == "Backtest":
    from dashboard.pages.backtest_page import render
    render()
