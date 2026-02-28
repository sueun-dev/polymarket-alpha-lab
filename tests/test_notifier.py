# tests/test_notifier.py
import pytest
from unittest.mock import patch
from core.notifier import Notifier

def test_notifier_disabled():
    n = Notifier(telegram_enabled=False, discord_enabled=False)
    n.send("test")  # Should not raise

def test_trade_alert():
    n = Notifier()
    with patch.object(n, 'send') as mock_send:
        n.trade_alert("s01", "buy", "Test market", 0.55, 100)
        mock_send.assert_called_once()

def test_error_alert():
    n = Notifier()
    with patch.object(n, 'send') as mock_send:
        n.error_alert("something broke")
        mock_send.assert_called_once_with("\u274c *Error*: something broke", level="error")
