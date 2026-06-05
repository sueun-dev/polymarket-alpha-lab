# strategies/tier_s/s05_negrisk_rebalancing.py
"""
S05: NegRisk Rebalancing

In multi-outcome markets (3+ options), if the sum of all YES prices > $1.00,
the basket is overpriced and the edge is to take short exposure on the
overpriced outcome(s).

WARNING -- NOT EXECUTABLE / NOT RISK-FREE AS WRITTEN. This strategy is
currently a research stub and must not be enabled live without changes:

  * It emits ``side="sell"`` on the overpriced *YES* token. On the Polymarket
    CLOB you cannot naked-short a token you do not hold; short exposure is
    obtained by BUYING that outcome's NO token. The opportunity metadata only
    carries per-outcome YES tokens, so the NO token id needed to place a real
    order is not available here.
  * The signal's ``estimated_prob`` is below ``market_price``, so ``edge`` is
    negative and ``RiskManager.can_trade`` rejects it (the strategy never
    fires under the default risk checks). This is intentional belt-and-braces
    until a correct NO-token buy leg is wired in -- do not "fix" the edge sign
    without also fixing the order leg, or the bot will repeatedly attempt an
    un-executable YES sell.
  * It is not risk-free: capturing the negrisk spread requires simultaneously
    taking the NO side of every outcome, which this single-leg stub does not.
"""
from typing import List, Optional

from core.base_strategy import BaseStrategy
from core.models import Market, Opportunity, Signal, Order


class NegRiskRebalancing(BaseStrategy):
    name = "s05_negrisk_rebalancing"
    tier = "S"
    strategy_id = 5
    required_data = ["feature_engine"]

    MIN_OUTCOMES = 3
    MIN_OVERPRICE = 0.02  # 2% over $1.00

    def scan(self, markets: List[Market]) -> List[Opportunity]:
        opportunities = []
        for m in markets:
            if len(m.tokens) >= self.MIN_OUTCOMES:
                total_yes = sum(float(t.get("price", 0)) for t in m.tokens)
                if total_yes > 1.0 + self.MIN_OVERPRICE:
                    opportunities.append(Opportunity(
                        market_id=m.condition_id,
                        question=m.question,
                        market_price=total_yes,
                        category=m.category,
                        metadata={
                            "tokens": m.tokens,
                            "total_yes": total_yes,
                            "overprice": total_yes - 1.0,
                        },
                    ))
        return opportunities

    def analyze(self, opportunity: Opportunity) -> Optional[Signal]:
        tokens = opportunity.metadata.get("tokens", [])
        overprice = opportunity.metadata.get("overprice", 0)

        if overprice < self.MIN_OVERPRICE:
            return None

        # Identify the most overpriced outcome. NOTE: to actually trade this we
        # would need to BUY this outcome's NO token (not sell its YES token);
        # that NO token id is not present in the opportunity metadata. See the
        # module docstring -- this signal is deliberately non-executable.
        most_overpriced = max(tokens, key=lambda t: float(t.get("price", 0)))
        token_id = most_overpriced.get("token_id", "")
        yes_price = float(most_overpriced.get("price", 0))

        if not token_id:
            return None

        # Check volatility if feature engine available
        feature_engine = self.get_data("feature_engine")
        if feature_engine is not None:
            # Only trade in low-volatility environments where prices are stable
            # High volatility means the overprice might be temporary
            # For now, just mark that we have the capability
            # Real volatility check requires live CLOB price feeds
            pass

        return Signal(
            market_id=opportunity.market_id,
            token_id=token_id,
            side="sell",  # NOT executable: cannot naked-short YES; see docstring
            estimated_prob=yes_price - overprice / len(tokens),  # < market_price -> negative edge by design
            market_price=yes_price,
            confidence=0.9,
            strategy_name=self.name,
            metadata={"overprice": overprice, "total_yes": opportunity.market_price},
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
