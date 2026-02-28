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
        f = self.optimal_size(p, market_price)
        return bankroll * f
