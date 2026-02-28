# strategies/tier_a/s21_text_video_delay.py
"""
S21: Text-Video Delay Sports Trading

Text-based score updates (APIs, tickers, scoreboards) arrive 30-40 seconds
before video streams reach viewers. In live esports/sports markets, this
window lets you trade on outcomes the broader market hasn't seen yet.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class TextVideoDelay(BaseStrategy):
    name = "s21_text_video_delay"
    tier = "A"
    strategy_id = 21
    required_data = ["sports_feed"]

    LIVE_KEYWORDS = [
        "live", "match", "game", "dota", "csgo", "lol",
        "nba", "nfl", "esports", "tournament",
    ]

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find esports/sports live markets based on keyword matching."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            q_lower = m.question.lower()
            has_live_keyword = any(kw in q_lower for kw in self.LIVE_KEYWORDS)
            if not has_live_keyword:
                continue
            yes_price = self._get_yes_price(m)
            if yes_price is None:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=yes_price,
                category=m.category,
                metadata={"tokens": m.tokens, "volume": m.volume},
            ))
        return opportunities

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Placeholder -- requires real-time game API feed to detect score changes."""
        # In production: compare text-feed score to current market price.
        # If text feed shows a decisive event (goal, ace, round win) that
        # the video-watching crowd hasn't priced in yet, generate a signal.
        return None

    def execute(self, signal: Signal, size: float, client=None) -> Optional[Order]:
        if client is None:
            return None
        return client.place_order(
            token_id=signal.token_id,
            side=signal.side,
            price=signal.market_price,
            size=size,
            strategy_name=self.name,
        )
