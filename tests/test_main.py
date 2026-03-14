# tests/test_main.py
import pytest
from main import apply_strategy_runtime_config, build_manual_instruction, load_config
from core.models import Opportunity
from strategies.tier_s.s01_reversing_stupidity import ReversingStupidity

def test_load_config():
    config = load_config("config.yaml")
    assert "bot" in config
    assert "risk" in config
    assert "ai_judge" in config
    assert config["bot"]["mode"] == "paper"


def test_build_manual_instruction_for_s01():
    strategy = ReversingStupidity()
    opp = Opportunity(
        market_id="0x1",
        question="Will Trump win?",
        market_price=0.80,
        metadata={
            "tokens": [
                {"token_id": "y1", "outcome": "Yes", "price": "0.80"},
                {"token_id": "n1", "outcome": "No", "price": "0.20"},
            ]
        },
    )
    signal = strategy.analyze(opp)
    assert signal is not None
    message = build_manual_instruction(strategy, signal, size=100.0)
    assert message is not None
    assert "NO limit <=" in message


def test_apply_strategy_runtime_config_updates_kelly_fraction():
    strategy = ReversingStupidity()
    assert strategy.kelly.fraction == 0.25

    apply_strategy_runtime_config([strategy], {"risk": {"kelly_fraction": 0.5}})

    assert strategy.kelly.fraction == 0.5
