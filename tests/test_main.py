# tests/test_main.py
from main import load_config

def test_load_config():
    config = load_config("config.yaml")
    assert "scanner" in config
    assert "signals" in config
    assert "bot" not in config
