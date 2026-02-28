# tests/test_main.py
import pytest
from main import load_config

def test_load_config():
    config = load_config("config.yaml")
    assert "bot" in config
    assert "risk" in config
    assert config["bot"]["mode"] == "paper"
