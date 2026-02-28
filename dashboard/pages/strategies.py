import streamlit as st
import importlib
import sys
from pathlib import Path

def render():
    st.header("Strategy Performance")

    # Add project root to path
    project_root = str(Path(__file__).parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    try:
        from strategies import StrategyRegistry
        registry = StrategyRegistry()
        registry.discover()
        strategies = sorted(registry.get_all(), key=lambda s: s.strategy_id)

        if not strategies:
            st.warning("No strategies found.")
            return

        st.metric("Total Strategies", len(strategies))

        # Tier breakdown
        tiers = {}
        for s in strategies:
            tiers.setdefault(s.tier, []).append(s)

        for tier in ["S", "A", "B", "C"]:
            if tier in tiers:
                with st.expander(f"Tier {tier} ({len(tiers[tier])} strategies)", expanded=(tier == "S")):
                    for s in sorted(tiers[tier], key=lambda x: x.strategy_id):
                        data_str = ", ".join(s.required_data) if s.required_data else "None"
                        st.markdown(f"**#{s.strategy_id}** `{s.name}` — Data: {data_str}")

    except Exception as e:
        st.error(f"Error loading strategies: {e}")
