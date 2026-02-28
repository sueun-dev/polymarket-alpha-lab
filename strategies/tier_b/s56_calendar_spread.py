# strategies/tier_b/s56_calendar_spread.py
"""
S56: Calendar Spread Theta Harvesting

Exploit time value differences between markets with different expiry dates
on similar events. Near-term markets have less time premium; far-term
markets carry excess theta. Sell the overpriced far-dated contract and buy
the near-dated one to harvest the time spread.
"""
from datetime import datetime
from typing import Dict, List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class CalendarSpread(BaseStrategy):
    name = "s56_calendar_spread"
    tier = "B"
    strategy_id = 56
    required_data = []

    MIN_PRICE_SPREAD = 0.05  # Minimum price difference to act
    MIN_DAYS_APART = 7       # Minimum days between expiry dates
    MIN_CONFIDENCE = 0.55

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets with different expiry dates on similar events."""
        # Group markets by base question (strip dates/specifics)
        groups: Dict[str, List[Market]] = {}
        for m in markets:
            if not m.active:
                continue
            if not m.end_date_iso:
                continue
            base_key = self._normalize_question(m.question)
            if base_key not in groups:
                groups[base_key] = []
            groups[base_key].append(m)

        opportunities: List[Opportunity] = []
        for base_key, group in groups.items():
            if len(group) < 2:
                continue
            # Sort by end date
            dated = []
            for m in group:
                end_dt = self._parse_date(m.end_date_iso)
                if end_dt is None:
                    continue
                yes_price = self._get_yes_price(m)
                if yes_price is None:
                    continue
                dated.append((m, end_dt, yes_price))
            dated.sort(key=lambda x: x[1])
            if len(dated) < 2:
                continue

            near_market, near_dt, near_price = dated[0]
            far_market, far_dt, far_price = dated[-1]
            days_apart = (far_dt - near_dt).days
            if days_apart < self.MIN_DAYS_APART:
                continue
            price_spread = far_price - near_price
            if abs(price_spread) < self.MIN_PRICE_SPREAD:
                continue

            opportunities.append(Opportunity(
                market_id=near_market.condition_id,
                question=f"Spread: {near_market.question}",
                market_price=near_price,
                category=near_market.category,
                metadata={
                    "near_market_id": near_market.condition_id,
                    "far_market_id": far_market.condition_id,
                    "near_price": near_price,
                    "far_price": far_price,
                    "price_spread": price_spread,
                    "days_apart": days_apart,
                    "near_tokens": near_market.tokens,
                    "far_tokens": far_market.tokens,
                },
            ))
        return opportunities

    def _normalize_question(self, question: str) -> str:
        """Strip dates and specifics to group similar questions."""
        q = question.lower()
        # Remove common date patterns
        for month in ["january", "february", "march", "april", "may", "june",
                       "july", "august", "september", "october", "november", "december"]:
            q = q.replace(month, "")
        # Remove digits
        q = "".join(c for c in q if not c.isdigit())
        return q.strip()

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    def _get_yes_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "yes":
                return float(t.get("price", 0))
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Exploit time value differences between near and far expiries."""
        near_price = opportunity.metadata.get("near_price", 0)
        far_price = opportunity.metadata.get("far_price", 0)
        price_spread = opportunity.metadata.get("price_spread", 0)

        if abs(price_spread) < self.MIN_PRICE_SPREAD:
            return None

        # Buy the cheaper leg (near-dated) as the primary signal
        near_tokens = opportunity.metadata.get("near_tokens", [])
        token_id = None
        for t in near_tokens:
            if t.get("outcome", "").lower() == "yes":
                token_id = t.get("token_id", "")
                break
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=near_price + abs(price_spread) * 0.5,
            market_price=near_price,
            confidence=self.MIN_CONFIDENCE,
            strategy_name=self.name,
            metadata={
                "spread": price_spread,
                "days_apart": opportunity.metadata.get("days_apart", 0),
                "far_market_id": opportunity.metadata.get("far_market_id", ""),
            },
        )

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
