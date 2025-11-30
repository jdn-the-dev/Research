import requests
from typing import Optional
from settings import load_settings


class TelegramNotifier:
    """
    Loads Telegram configuration from settings and provides methods
    to check thresholds and send messages.
    """
    def __init__(self):
        config = load_settings()
        self.token: str = config.get("telegram_token", "")
        self.chat_id: str = config.get("telegram_chat_id", "")
        self.threshold: float = config.get("alert_threshold", 0.0)
        self.base_url: str = f"https://api.telegram.org/bot{self.token}/"

    def is_configured(self) -> bool:
        """Returns True if both token and chat_id are set."""
        return bool(self.token and self.chat_id)

    def should_alert(self, change: float) -> bool:
        """
        Determines if a given percent change meets or exceeds the configured threshold.
        """
        return abs(change) >= self.threshold

    def send_message(self, text: str) -> bool:
        """
        Sends a text message to the configured Telegram chat.
        Returns True on success, False otherwise.
        """
        if not self.is_configured():
            return False
        url = self.base_url + "sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except requests.RequestException:
            return False


# module-level notifier instance
notifier = TelegramNotifier()


def alert_change(symbol: str, change: float, price: float) -> None:
    """
    If the change exceeds threshold, formats and sends a Telegram alert.
    """
    if notifier.should_alert(change):
        direction = "up" if change > 0 else "down"
        message = f"*{symbol}* moved *{change:.2f}%* {direction}, current price: ${price:.2f}"
        notifier.send_message(message)
