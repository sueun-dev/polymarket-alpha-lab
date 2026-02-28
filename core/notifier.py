# core/notifier.py
import os
import logging
import httpx

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, telegram_enabled: bool = False, discord_enabled: bool = False):
        self.telegram_enabled = telegram_enabled
        self.discord_enabled = discord_enabled
        self._telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self._discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")

    def send(self, message: str, level: str = "info") -> None:
        logger.log(getattr(logging, level.upper(), logging.INFO), message)
        if self.telegram_enabled:
            self._send_telegram(message)
        if self.discord_enabled:
            self._send_discord(message)

    def _send_telegram(self, message: str) -> None:
        if not self._telegram_token or not self._telegram_chat_id:
            return
        try:
            url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"
            httpx.post(url, json={"chat_id": self._telegram_chat_id, "text": message, "parse_mode": "Markdown"})
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")

    def _send_discord(self, message: str) -> None:
        if not self._discord_webhook:
            return
        try:
            httpx.post(self._discord_webhook, json={"content": message})
        except Exception as e:
            logger.error(f"Discord send failed: {e}")

    def trade_alert(self, strategy: str, side: str, market: str, price: float, size: float) -> None:
        self.send(f"\U0001f514 *Trade*: {strategy} | {side.upper()} {size:.0f}x @ ${price:.2f} | {market}")

    def opportunity_alert(self, strategy: str, market: str, edge: float) -> None:
        self.send(f"\U0001f4ca *Opportunity*: {strategy} | Edge: {edge:.1%} | {market}")

    def error_alert(self, message: str) -> None:
        self.send(f"\u274c *Error*: {message}", level="error")
