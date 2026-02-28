# strategies/tier_c/s99_portfolio_insurance.py
"""
S99: Portfolio Insurance via NO Positions

Identify markets whose YES outcome is positively correlated with
existing portfolio risk.  Buying NO tokens on those markets acts
as a hedge -- if the adverse event occurs, the NO position pays out
and offsets portfolio losses.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class PortfolioInsurance(BaseStrategy):
    name = "s99_portfolio_insurance"
    tier = "C"
    strategy_id = 99
    required_data = []

    CORRELATION_THRESHOLD = 0.50  # Minimum correlation to hedge
    MAX_NO_PRICE = 0.40  # Don't overpay for insurance

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        """Find markets correlating with existing portfolio exposure."""
        opportunities: List[Opportunity] = []
        for m in markets:
            if not m.active:
                continue
            no_price = self._get_no_price(m)
            if no_price is None or no_price > self.MAX_NO_PRICE:
                continue
            correlation = self._portfolio_correlation(m)
            if correlation is None or correlation < self.CORRELATION_THRESHOLD:
                continue
            opportunities.append(Opportunity(
                market_id=m.condition_id,
                question=m.question,
                market_price=no_price,
                category=m.category,
                metadata={
                    "tokens": m.tokens,
                    "correlation": correlation,
                    "no_price": no_price,
                },
            ))
        return opportunities

    def _get_no_price(self, market: Market) -> Optional[float]:
        for t in market.tokens:
            if t.get("outcome", "").lower() == "no":
                return float(t.get("price", 0))
        return None

    @staticmethod
    def _portfolio_correlation(market: Market) -> Optional[float]:
        """Return portfolio correlation from token metadata, if present."""
        for t in market.tokens:
            corr = t.get("portfolio_correlation")
            if corr is not None:
                return float(corr)
        return None

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        """Buy NO as a hedge against portfolio risk."""
        correlation = opportunity.metadata.get("correlation", 0)
        if correlation < self.CORRELATION_THRESHOLD:
            return None

        no_price = opportunity.metadata.get("no_price", opportunity.market_price)
        # Fair hedge value increases with correlation strength
        fair_value = min(0.99, no_price + correlation * 0.10)
        edge = fair_value - no_price
        if edge < 0.03:
            return None

        token_id = self._get_token_id(opportunity, "no")
        if not token_id:
            return None

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="buy",
            estimated_prob=fair_value,
            market_price=no_price,
            confidence=0.45,
            strategy_name=self.name,
            metadata={"correlation": correlation, "hedge_value": fair_value},
        )

    def _get_token_id(self, opportunity: Opportunity, outcome: str) -> Optional[str]:
        for t in opportunity.metadata.get("tokens", []):
            if t.get("outcome", "").lower() == outcome:
                return t.get("token_id", "")
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
