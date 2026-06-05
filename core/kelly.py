# core/kelly.py
class KellyCriterion:
    def __init__(self, fraction: float = 0.5, max_fraction: float = 0.06):
        self.fraction = fraction
        self.max_fraction = max_fraction

    def full_kelly(self, p: float, market_price: float) -> float:
        if p <= market_price:
            return 0.0
        f = (p - market_price) / (1 - market_price)
        return max(0.0, f)

    def half_kelly(self, p: float, market_price: float) -> float:
        return self.full_kelly(p, market_price) * 0.5

    def optimal_size(self, p: float, market_price: float) -> float:
        f = self.full_kelly(p, market_price) * self.fraction
        return min(f, self.max_fraction)

    def bet_amount(self, bankroll: float, p: float, market_price: float) -> float:
        """Kelly stake expressed in account currency (USDC dollars)."""
        f = self.optimal_size(p, market_price)
        return bankroll * f


def dollars_to_shares(dollars: float, price: float) -> float:
    """Convert a USDC dollar stake into a Polymarket share/contract count.

    Polymarket orders are denominated in shares, where each share costs
    ``price`` USDC and pays out $1 if the outcome resolves true, so the
    notional cost of an order is ``price * size``. Kelly sizing produces a
    dollar stake, so the order layer must divide by the per-share price to get
    the share count. Returns 0.0 for a non-positive price.
    """
    if price <= 0:
        return 0.0
    return dollars / price
