#!/usr/bin/env python3
"""
Strategy Combination Analysis
==============================
Tests combinations of 2-3 strategies together and measures:
  - Coverage: How many markets get signals from the combo
  - Complementarity: Do they cover different market types (not overlapping)?
  - Risk profile: Are they diversified (some contrarian, some momentum, some arb)?
  - Confidence aggregation: Average confidence when multiple agree on same market
  - Correlation: Low signal correlation = better combo
  - Practical feasibility: Can they actually run together?
"""
import sys
import os
import itertools
import json
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.models import Market, Opportunity, Signal

# ---------------------------------------------------------------------------
# Strategy metadata registry -- classifies each strategy's edge type, domain,
# latency requirements, data dependencies, and risk profile.
# ---------------------------------------------------------------------------

STRATEGY_META = {
    # === Tier S ===
    "s01_reversing_stupidity": {
        "id": "S01", "tier": "S",
        "edge_type": "contrarian",
        "domains": ["politics", "drama", "general"],
        "latency": "low",       # can run hourly
        "risk_style": "contrarian",
        "data_deps": ["base_rates", "news"],
        "description": "Bet against emotionally overheated markets",
    },
    "s02_weather_noaa": {
        "id": "S02", "tier": "S",
        "edge_type": "data_driven",
        "domains": ["weather"],
        "latency": "low",
        "risk_style": "data_edge",
        "data_deps": ["noaa"],
        "description": "NOAA weather data vs market mispricing",
    },
    "s03_nothing_ever_happens": {
        "id": "S03", "tier": "S",
        "edge_type": "base_rate",
        "domains": ["politics", "drama", "general"],
        "latency": "low",
        "risk_style": "contrarian",
        "data_deps": ["base_rates"],
        "description": "Systematically bet NO on dramatic outcomes (70% resolve NO)",
    },
    "s04_cross_platform_arb": {
        "id": "S04", "tier": "S",
        "edge_type": "arbitrage",
        "domains": ["politics", "general", "crypto"],
        "latency": "medium",
        "risk_style": "arbitrage",
        "data_deps": ["kalshi"],
        "description": "Cross-platform arb: Polymarket vs Kalshi",
    },
    "s05_negrisk_rebalancing": {
        "id": "S05", "tier": "S",
        "edge_type": "arbitrage",
        "domains": ["multi_outcome"],
        "latency": "medium",
        "risk_style": "arbitrage",
        "data_deps": ["feature_engine"],
        "description": "NegRisk rebalancing on multi-outcome markets",
    },
    "s06_btc_latency_arb": {
        "id": "S06", "tier": "S",
        "edge_type": "latency",
        "domains": ["crypto"],
        "latency": "high",      # needs sub-second
        "risk_style": "arbitrage",
        "data_deps": ["cex_feed"],
        "description": "BTC price latency arb (CEX vs Polymarket)",
    },
    "s10_yes_bias": {
        "id": "S10", "tier": "S",
        "edge_type": "base_rate",
        "domains": ["general", "drama"],
        "latency": "low",
        "risk_style": "contrarian",
        "data_deps": [],
        "description": "Exploit YES bias -- most markets resolve NO",
    },
    # === Tier A ===
    "s12_high_prob_harvesting": {
        "id": "S12", "tier": "A",
        "edge_type": "yield",
        "domains": ["general"],
        "latency": "low",
        "risk_style": "passive",
        "data_deps": [],
        "description": "Buy near-certain contracts (95-99c) for yield",
    },
    "s15_news_mean_reversion": {
        "id": "S15", "tier": "A",
        "edge_type": "mean_reversion",
        "domains": ["politics", "general", "drama"],
        "latency": "medium",
        "risk_style": "mean_reversion",
        "data_deps": ["news"],
        "description": "Fade 15%+ price moves on news overreaction",
    },
    "s19_kelly_framework": {
        "id": "S19", "tier": "A",
        "edge_type": "meta_sizing",
        "domains": ["general"],
        "latency": "low",
        "risk_style": "meta",
        "data_deps": [],
        "description": "Kelly criterion position sizing wrapper",
    },
    "s28_portfolio_agent": {
        "id": "S28", "tier": "A",
        "edge_type": "meta_portfolio",
        "domains": ["general"],
        "latency": "low",
        "risk_style": "meta",
        "data_deps": [],
        "description": "Portfolio-level Kelly allocation across markets",
    },
    "s30_sportsbook_arb": {
        "id": "S30", "tier": "A",
        "edge_type": "arbitrage",
        "domains": ["sports"],
        "latency": "medium",
        "risk_style": "arbitrage",
        "data_deps": ["sportsbook"],
        "description": "Cross-platform sportsbook arb (DraftKings/Betfair)",
    },
    # === Tier B ===
    "s39_volume_momentum": {
        "id": "S39", "tier": "B",
        "edge_type": "momentum",
        "domains": ["general", "politics", "crypto"],
        "latency": "medium",
        "risk_style": "momentum",
        "data_deps": [],
        "description": "Follow volume spikes and price momentum",
    },
    "s45_twitter_sentiment_reversal": {
        "id": "S45", "tier": "B",
        "edge_type": "sentiment",
        "domains": ["politics", "drama", "crypto", "general"],
        "latency": "medium",
        "risk_style": "contrarian",
        "data_deps": ["twitter_sentiment"],
        "description": "Fade extreme Twitter sentiment",
    },
    "s49_stablecoin_yield": {
        "id": "S49", "tier": "B",
        "edge_type": "yield",
        "domains": ["general", "crypto"],
        "latency": "low",
        "risk_style": "passive",
        "data_deps": [],
        "description": "Yield farming via high-prob prediction markets",
    },
    "s51_weather_microbet": {
        "id": "S51", "tier": "B",
        "edge_type": "data_driven",
        "domains": ["weather"],
        "latency": "low",
        "risk_style": "diversified_micro",
        "data_deps": ["noaa"],
        "description": "Diversified $1-$3 micro-bets on weather markets",
    },
    "s53_onchain_orderflow": {
        "id": "S53", "tier": "B",
        "edge_type": "flow",
        "domains": ["general", "crypto"],
        "latency": "medium",
        "risk_style": "momentum",
        "data_deps": ["dune"],
        "description": "On-chain order flow / whale tracking",
    },
    # === Tier C ===
    "s100_meta_strategy": {
        "id": "S100", "tier": "C",
        "edge_type": "meta_ensemble",
        "domains": ["general"],
        "latency": "low",
        "risk_style": "meta",
        "data_deps": [],
        "description": "Weighted ensemble of multiple sub-strategy signals",
    },
}


# ---------------------------------------------------------------------------
# Synthetic market data -- covers many market types and scenarios
# ---------------------------------------------------------------------------

def create_synthetic_markets() -> List[Market]:
    """Create synthetic markets covering weather, politics, crypto, sports,
    dramatic events, high-prob, multi-outcome, etc."""
    markets = []
    market_id = 0

    def _mk(question, category, yes_price, volume, liquidity=5000,
             end_date="2026-04-15T00:00:00Z", n_tokens=2,
             price_change_24h=None, active=True):
        nonlocal market_id
        market_id += 1
        cid = f"market_{market_id:04d}"

        if n_tokens == 2:
            tokens = [
                {"outcome": "Yes", "token_id": f"yes_{cid}", "price": str(yes_price)},
                {"outcome": "No", "token_id": f"no_{cid}", "price": str(round(1 - yes_price, 4))},
            ]
            if price_change_24h is not None:
                tokens[0]["price_change_24h"] = price_change_24h
        else:
            # Multi-outcome: distribute prices (intentionally slightly > 1.0)
            prices = []
            remaining = yes_price  # use yes_price as "top outcome" price
            prices.append(remaining)
            for i in range(1, n_tokens):
                if i < n_tokens - 1:
                    p = round((1.0 - remaining) / (n_tokens - i) + 0.02, 4)
                else:
                    p = round(max(0.05, 1.0 - sum(prices) + 0.03), 4)
                prices.append(p)
            tokens = [
                {"outcome": f"Option_{j+1}", "token_id": f"opt{j}_{cid}", "price": str(p)}
                for j, p in enumerate(prices)
            ]

        return Market(
            condition_id=cid,
            question=question,
            tokens=tokens,
            end_date_iso=end_date,
            active=active,
            volume=volume,
            liquidity=liquidity,
            category=category,
        )

    # ---- Weather markets ----
    markets.append(_mk("Will NYC temperature exceed 100 degrees fahrenheit this July?",
                        "weather", 0.08, 3000))
    markets.append(_mk("Will it rain in Los Angeles on March 15?",
                        "weather", 0.12, 2500))
    markets.append(_mk("Will Chicago high temperature exceed 90 degrees in June?",
                        "weather", 0.10, 4000))
    markets.append(_mk("Will Miami see snow in 2026?",
                        "weather", 0.02, 8000))
    markets.append(_mk("Will Denver low temperature drop below 0 fahrenheit in March?",
                        "weather", 0.06, 1500))

    # ---- Political / dramatic markets ----
    markets.append(_mk("Will Trump be impeached by end of 2026?",
                        "politics", 0.35, 50000, price_change_24h=0.18))
    markets.append(_mk("Will Russia invade another country in 2026?",
                        "politics", 0.25, 30000))
    markets.append(_mk("Will the US government default on debt in 2026?",
                        "politics", 0.08, 45000))
    markets.append(_mk("Will Biden resign before 2027?",
                        "politics", 0.18, 25000))
    markets.append(_mk("Will there be a historic crash in the S&P 500 in Q2?",
                        "finance", 0.22, 60000, price_change_24h=-0.20))
    markets.append(_mk("Is war with China inevitable by 2027?",
                        "politics", 0.15, 35000))
    markets.append(_mk("MAGA rally attendance guaranteed to break record?",
                        "politics", 0.72, 15000))

    # ---- Crypto markets ----
    markets.append(_mk("Will BTC 15-minute candle close above $100k?",
                        "crypto", 0.45, 20000))
    markets.append(_mk("Will Bitcoin reach $150k by end of 2026?",
                        "crypto", 0.38, 80000, price_change_24h=0.12))
    markets.append(_mk("Will Ethereum flip Bitcoin in market cap?",
                        "crypto", 0.05, 15000))
    markets.append(_mk("First ever BTC ETF inflow exceeds $1B in a day?",
                        "crypto", 0.60, 25000))

    # ---- Sports markets ----
    markets.append(_mk("Will the Lakers win the NBA Championship 2026?",
                        "sports", 0.12, 40000))
    markets.append(_mk("Will Kansas City win the Super Bowl 2027?",
                        "sports", 0.18, 55000))
    markets.append(_mk("UFC Championship: Will the underdog win?",
                        "sports", 0.35, 12000))

    # ---- High-probability / yield markets ----
    markets.append(_mk("Will the sun rise tomorrow?",
                        "general", 0.97, 10000, end_date="2026-03-02T00:00:00Z"))
    markets.append(_mk("Will Bitcoin still exist on April 1, 2026?",
                        "crypto", 0.98, 8000, end_date="2026-04-01T00:00:00Z"))
    markets.append(_mk("Will the NYSE open on Monday March 2?",
                        "finance", 0.96, 6000, end_date="2026-03-03T00:00:00Z"))

    # ---- Multi-outcome markets ----
    markets.append(_mk("Who will win the 2026 World Cup?",
                        "sports", 0.25, 100000, n_tokens=5))
    markets.append(_mk("Which party wins the 2026 midterms: Rep/Dem/Other?",
                        "politics", 0.45, 70000, n_tokens=3))
    markets.append(_mk("Next Pope nationality: Italian/Latin American/African/European/Asian?",
                        "politics", 0.30, 50000, n_tokens=5))

    # ---- General / dramatic with volume spikes ----
    markets.append(_mk("Will an unprecedented breakthrough in fusion energy be announced?",
                        "science", 0.40, 20000, price_change_24h=0.25))
    markets.append(_mk("Will Elon Musk destroy Twitter by end of 2026?",
                        "drama", 0.30, 35000))
    markets.append(_mk("Will a revolutionary AI model surpass human reasoning?",
                        "tech", 0.55, 45000, price_change_24h=-0.18))

    # ---- Medium-volume general markets for momentum ----
    markets.append(_mk("Will global GDP growth exceed 4% in 2026?",
                        "finance", 0.32, 18000))
    markets.append(_mk("Will OpenAI IPO in 2026?",
                        "tech", 0.42, 22000))

    return markets


# ---------------------------------------------------------------------------
# Strategy instantiation helpers
# ---------------------------------------------------------------------------

def _import_strategy_class(name: str):
    """Dynamically import a strategy class by its registry name."""
    import importlib
    # Determine tier from metadata
    meta = STRATEGY_META.get(name)
    if not meta:
        return None
    tier_map = {"S": "tier_s", "A": "tier_a", "B": "tier_b", "C": "tier_c"}
    tier_dir = tier_map.get(meta["tier"], "tier_c")
    module_name = f"strategies.{tier_dir}.{name}"
    try:
        mod = importlib.import_module(module_name)
    except ImportError:
        return None
    # Find the BaseStrategy subclass
    from core.base_strategy import BaseStrategy
    for attr_name in dir(mod):
        attr = getattr(mod, attr_name)
        if isinstance(attr, type) and issubclass(attr, BaseStrategy) and attr is not BaseStrategy:
            return attr
    return None


def instantiate_strategies(names: List[str]):
    """Return dict of {name: instance} for the requested strategy names."""
    instances = {}
    for n in names:
        cls = _import_strategy_class(n)
        if cls is not None:
            instances[n] = cls()
    return instances


# ---------------------------------------------------------------------------
# Core analysis functions
# ---------------------------------------------------------------------------

def run_strategy_on_markets(strategy, markets: List[Market]) -> Dict:
    """Run a strategy's scan+analyze on synthetic markets.
    Returns dict with signal details."""
    try:
        opportunities = strategy.scan(markets)
    except Exception:
        opportunities = []

    signals = []
    scanned_market_ids = set()
    signal_market_ids = set()
    categories_covered = set()

    for opp in opportunities:
        scanned_market_ids.add(opp.market_id)
        try:
            sig = strategy.analyze(opp)
        except Exception:
            sig = None
        if sig is not None:
            signals.append(sig)
            signal_market_ids.add(sig.market_id)
            # Determine category from market
            for m in markets:
                if m.condition_id == sig.market_id:
                    categories_covered.add(m.category or "unknown")

    return {
        "scanned": len(scanned_market_ids),
        "signals": len(signals),
        "signal_market_ids": signal_market_ids,
        "categories": categories_covered,
        "signal_objects": signals,
        "avg_confidence": (
            sum(s.confidence for s in signals) / len(signals) if signals else 0
        ),
        "avg_edge": (
            sum(s.edge for s in signals) / len(signals) if signals else 0
        ),
    }


def analyze_combo(combo_names: List[str], markets: List[Market],
                  all_results: Dict) -> Dict:
    """Analyze a combination of strategies for synergy metrics."""
    combo_results = {n: all_results[n] for n in combo_names if n in all_results}
    if len(combo_results) < 2:
        return {}

    # --- Coverage ---
    union_market_ids = set()
    per_strategy_ids = {}
    for n, r in combo_results.items():
        per_strategy_ids[n] = r["signal_market_ids"]
        union_market_ids |= r["signal_market_ids"]

    coverage = len(union_market_ids)

    # --- Complementarity (Jaccard distance) ---
    pairs = list(itertools.combinations(combo_names, 2))
    overlaps = []
    for a, b in pairs:
        sa = per_strategy_ids.get(a, set())
        sb = per_strategy_ids.get(b, set())
        union = sa | sb
        inter = sa & sb
        if union:
            jaccard_sim = len(inter) / len(union)
        else:
            jaccard_sim = 0
        overlaps.append(jaccard_sim)
    avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0
    complementarity = 1.0 - avg_overlap  # higher = more complementary

    # --- Category diversity ---
    all_cats = set()
    per_strat_cats = {}
    for n, r in combo_results.items():
        per_strat_cats[n] = r["categories"]
        all_cats |= r["categories"]
    category_diversity = len(all_cats)

    # --- Risk profile diversity ---
    risk_styles = set()
    edge_types = set()
    for n in combo_names:
        meta = STRATEGY_META.get(n, {})
        risk_styles.add(meta.get("risk_style", "unknown"))
        edge_types.add(meta.get("edge_type", "unknown"))
    risk_diversity = len(risk_styles)
    edge_diversity = len(edge_types)

    # --- Confidence aggregation (when strategies agree on same market) ---
    market_signals = defaultdict(list)
    for n, r in combo_results.items():
        for sig in r["signal_objects"]:
            market_signals[sig.market_id].append(sig)

    agreement_count = 0
    agreement_confidence_sum = 0
    agreement_edge_sum = 0
    disagreement_count = 0
    for mid, sigs in market_signals.items():
        if len(sigs) >= 2:
            # Check if they agree on direction
            sides = set(s.side for s in sigs)
            if len(sides) == 1:
                agreement_count += 1
                agreement_confidence_sum += sum(s.confidence for s in sigs) / len(sigs)
                agreement_edge_sum += sum(s.edge for s in sigs) / len(sigs)
            else:
                disagreement_count += 1

    avg_agreement_confidence = (
        agreement_confidence_sum / agreement_count if agreement_count else 0
    )
    avg_agreement_edge = (
        agreement_edge_sum / agreement_count if agreement_count else 0
    )

    # --- Signal correlation (lower = better) ---
    # Approximate: ratio of overlap signals to total unique signals
    total_signals = sum(r["signals"] for r in combo_results.values())
    unique_signals = coverage
    if total_signals > 0:
        redundancy = 1.0 - (unique_signals / total_signals) if total_signals > unique_signals else 0
    else:
        redundancy = 0
    correlation_proxy = redundancy  # lower = better combo

    # --- Practical feasibility ---
    all_data_deps = set()
    latencies = []
    for n in combo_names:
        meta = STRATEGY_META.get(n, {})
        all_data_deps.update(meta.get("data_deps", []))
        latencies.append(meta.get("latency", "low"))

    # Penalize if high-latency + low-latency mixed (hard to orchestrate)
    has_high = "high" in latencies
    has_low = "low" in latencies
    latency_conflict = has_high and has_low
    feasibility_score = 1.0
    if latency_conflict:
        feasibility_score -= 0.20
    # Penalize heavy data dependencies
    if len(all_data_deps) > 4:
        feasibility_score -= 0.15
    elif len(all_data_deps) > 2:
        feasibility_score -= 0.05
    # Bonus if zero external deps
    if len(all_data_deps) == 0:
        feasibility_score += 0.10
    feasibility_score = max(0, min(1.0, feasibility_score))

    # --- Composite score ---
    # Weighted combination of all factors
    W_COVERAGE = 0.20
    W_COMPLEMENTARITY = 0.20
    W_RISK_DIV = 0.15
    W_CATEGORY_DIV = 0.10
    W_AGREEMENT_CONF = 0.10
    W_LOW_CORR = 0.15
    W_FEASIBILITY = 0.10

    # Normalize coverage to 0-1 (max possible = total markets)
    norm_coverage = min(coverage / len(markets), 1.0)
    norm_cat_div = min(category_diversity / 7, 1.0)  # 7 categories max
    norm_risk_div = min(risk_diversity / 5, 1.0)      # 5 risk styles max

    composite = (
        W_COVERAGE * norm_coverage
        + W_COMPLEMENTARITY * complementarity
        + W_RISK_DIV * norm_risk_div
        + W_CATEGORY_DIV * norm_cat_div
        + W_AGREEMENT_CONF * avg_agreement_confidence
        + W_LOW_CORR * (1.0 - correlation_proxy)
        + W_FEASIBILITY * feasibility_score
    )

    return {
        "combo": combo_names,
        "combo_ids": [STRATEGY_META.get(n, {}).get("id", n) for n in combo_names],
        "coverage": coverage,
        "total_markets": len(markets),
        "coverage_pct": round(coverage / len(markets) * 100, 1),
        "complementarity": round(complementarity, 3),
        "avg_overlap": round(avg_overlap, 3),
        "category_diversity": category_diversity,
        "categories": sorted(all_cats),
        "risk_styles": sorted(risk_styles),
        "risk_diversity": risk_diversity,
        "edge_types": sorted(edge_types),
        "edge_diversity": edge_diversity,
        "agreement_count": agreement_count,
        "disagreement_count": disagreement_count,
        "avg_agreement_confidence": round(avg_agreement_confidence, 3),
        "avg_agreement_edge": round(avg_agreement_edge, 4),
        "correlation_proxy": round(correlation_proxy, 3),
        "data_deps": sorted(all_data_deps),
        "latency_conflict": latency_conflict,
        "feasibility_score": round(feasibility_score, 2),
        "composite_score": round(composite, 4),
    }


# ---------------------------------------------------------------------------
# Named combo definitions
# ---------------------------------------------------------------------------

NAMED_COMBOS = {
    "Contrarian + Base Rate (S01+S03+S10)": [
        "s01_reversing_stupidity", "s03_nothing_ever_happens", "s10_yes_bias",
    ],
    "Arbitrage + Data-driven (S04+S05+S02)": [
        "s04_cross_platform_arb", "s05_negrisk_rebalancing", "s02_weather_noaa",
    ],
    "Sentiment + Mean Reversion (S15+S45+S01)": [
        "s15_news_mean_reversion", "s45_twitter_sentiment_reversal",
        "s01_reversing_stupidity",
    ],
    "High-frequency + Passive (S06+S12+S49)": [
        "s06_btc_latency_arb", "s12_high_prob_harvesting",
        "s49_stablecoin_yield",
    ],
    "Domain Specialist: Weather+Sports+Crypto (S02+S30+S06)": [
        "s02_weather_noaa", "s30_sportsbook_arb", "s06_btc_latency_arb",
    ],
    "Meta-Strategy Combos (S19+S28+S100)": [
        "s19_kelly_framework", "s28_portfolio_agent", "s100_meta_strategy",
    ],
    # Additional interesting combos
    "Contrarian + Momentum (S01+S39)": [
        "s01_reversing_stupidity", "s39_volume_momentum",
    ],
    "Arb + Yield (S04+S12)": [
        "s04_cross_platform_arb", "s12_high_prob_harvesting",
    ],
    "Weather Specialist (S02+S51)": [
        "s02_weather_noaa", "s51_weather_microbet",
    ],
    "Full Contrarian Stack (S01+S03+S10+S15)": [
        "s01_reversing_stupidity", "s03_nothing_ever_happens",
        "s10_yes_bias", "s15_news_mean_reversion",
    ],
    "Data Edge + Flow (S02+S53+S05)": [
        "s02_weather_noaa", "s53_onchain_orderflow", "s05_negrisk_rebalancing",
    ],
    "Yield + Contrarian (S12+S49+S03)": [
        "s12_high_prob_harvesting", "s49_stablecoin_yield",
        "s03_nothing_ever_happens",
    ],
    "Broad Market Coverage (S01+S02+S04+S30)": [
        "s01_reversing_stupidity", "s02_weather_noaa",
        "s04_cross_platform_arb", "s30_sportsbook_arb",
    ],
    "Contrarian + Arb Pair (S03+S05)": [
        "s03_nothing_ever_happens", "s05_negrisk_rebalancing",
    ],
    "Momentum + Sentiment + Yield (S39+S45+S49)": [
        "s39_volume_momentum", "s45_twitter_sentiment_reversal",
        "s49_stablecoin_yield",
    ],
}


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def print_divider(char="=", width=80):
    print(char * width)


def print_section(title):
    print()
    print_divider("=")
    print(f"  {title}")
    print_divider("=")
    print()


def print_individual_strategy_results(all_results: Dict, markets: List[Market]):
    print_section("INDIVIDUAL STRATEGY PERFORMANCE (Baseline)")
    header = f"{'Strategy':<35} {'Tier':>4} {'Scanned':>8} {'Signals':>8} {'Cats':>5} {'AvgConf':>8} {'AvgEdge':>8} {'EdgeType':<16}"
    print(header)
    print("-" * len(header))

    for name in sorted(all_results.keys(),
                       key=lambda n: (-all_results[n]["signals"], n)):
        r = all_results[name]
        meta = STRATEGY_META.get(name, {})
        cats = ",".join(sorted(r["categories"])) if r["categories"] else "-"
        print(f"{meta.get('id','?')}: {name:<30} {meta.get('tier','?'):>4} "
              f"{r['scanned']:>8} {r['signals']:>8} {len(r['categories']):>5} "
              f"{r['avg_confidence']:>8.3f} {r['avg_edge']:>8.4f} "
              f"{meta.get('edge_type','?'):<16}")
    print()


def print_combo_results(combo_analyses: List[Dict]):
    print_section("STRATEGY COMBINATION ANALYSIS")

    for i, ca in enumerate(combo_analyses, 1):
        combo_label = " + ".join(ca["combo_ids"])
        print(f"--- Combo {i}: {combo_label} ---")
        print(f"    Strategies:           {', '.join(ca['combo'])}")
        print(f"    Coverage:             {ca['coverage']} / {ca['total_markets']} markets ({ca['coverage_pct']}%)")
        print(f"    Complementarity:      {ca['complementarity']:.3f}  (1.0 = zero overlap)")
        print(f"    Category Diversity:   {ca['category_diversity']}  categories: {', '.join(ca['categories'])}")
        print(f"    Risk Styles:          {ca['risk_diversity']}  ({', '.join(ca['risk_styles'])})")
        print(f"    Edge Types:           {ca['edge_diversity']}  ({', '.join(ca['edge_types'])})")
        print(f"    Agreement Markets:    {ca['agreement_count']}  (disagreements: {ca['disagreement_count']})")
        print(f"    Avg Agree Confidence: {ca['avg_agreement_confidence']:.3f}")
        print(f"    Avg Agree Edge:       {ca['avg_agreement_edge']:.4f}")
        print(f"    Correlation Proxy:    {ca['correlation_proxy']:.3f}  (lower = better)")
        print(f"    Data Dependencies:    {', '.join(ca['data_deps']) if ca['data_deps'] else 'none'}")
        print(f"    Latency Conflict:     {'YES' if ca['latency_conflict'] else 'no'}")
        print(f"    Feasibility Score:    {ca['feasibility_score']:.2f}")
        print(f"    *** COMPOSITE SCORE:  {ca['composite_score']:.4f} ***")
        print()


def print_rankings(combo_analyses: List[Dict]):
    print_section("RANKINGS")

    # 1. Best Market Coverage
    print("  [1] BEST MARKET COVERAGE (signals across most market types)")
    print("  " + "-" * 70)
    by_coverage = sorted(combo_analyses, key=lambda x: -x["coverage"])
    for i, ca in enumerate(by_coverage[:5], 1):
        label = " + ".join(ca["combo_ids"])
        print(f"    #{i}  {label:<40}  coverage={ca['coverage']}/{ca['total_markets']} ({ca['coverage_pct']}%)  cats={ca['category_diversity']}")
    print()

    # 2. Best Risk-Adjusted Returns (edge_diversity * complementarity * feasibility)
    print("  [2] BEST RISK-ADJUSTED RETURNS (diversified edge sources)")
    print("  " + "-" * 70)

    def risk_adj_score(ca):
        return (ca["edge_diversity"] / 5) * ca["complementarity"] * ca["feasibility_score"] * (1 + ca["avg_agreement_edge"])

    by_risk = sorted(combo_analyses, key=lambda x: -risk_adj_score(x))
    for i, ca in enumerate(by_risk[:5], 1):
        label = " + ".join(ca["combo_ids"])
        score = risk_adj_score(ca)
        print(f"    #{i}  {label:<40}  risk_adj={score:.4f}  edge_types={ca['edge_diversity']}  compl={ca['complementarity']:.2f}")
    print()

    # 3. Lowest Correlation (best diversification)
    print("  [3] LOWEST CORRELATION (best diversification)")
    print("  " + "-" * 70)
    by_corr = sorted(combo_analyses, key=lambda x: x["correlation_proxy"])
    for i, ca in enumerate(by_corr[:5], 1):
        label = " + ".join(ca["combo_ids"])
        print(f"    #{i}  {label:<40}  corr={ca['correlation_proxy']:.3f}  compl={ca['complementarity']:.3f}  overlap={ca['avg_overlap']:.3f}")
    print()

    # 4. Practical Feasibility
    print("  [4] BEST PRACTICAL FEASIBILITY")
    print("  " + "-" * 70)

    def feasibility_rank(ca):
        return ca["feasibility_score"] * (1 if not ca["latency_conflict"] else 0.7) * (1.0 / max(1, len(ca["data_deps"])))

    by_feas = sorted(combo_analyses, key=lambda x: -feasibility_rank(x))
    for i, ca in enumerate(by_feas[:5], 1):
        label = " + ".join(ca["combo_ids"])
        score = feasibility_rank(ca)
        deps = ", ".join(ca["data_deps"]) if ca["data_deps"] else "none"
        print(f"    #{i}  {label:<40}  feas={score:.3f}  deps=[{deps}]  latency_conflict={'Y' if ca['latency_conflict'] else 'N'}")
    print()

    # 5. Overall Composite
    print("  [5] OVERALL COMPOSITE SCORE (all factors weighted)")
    print("  " + "-" * 70)
    by_composite = sorted(combo_analyses, key=lambda x: -x["composite_score"])
    for i, ca in enumerate(by_composite[:5], 1):
        label = " + ".join(ca["combo_ids"])
        print(f"    #{i}  {label:<40}  COMPOSITE={ca['composite_score']:.4f}")
        print(f"        coverage={ca['coverage_pct']}%  compl={ca['complementarity']:.2f}  "
              f"risk_div={ca['risk_diversity']}  cat_div={ca['category_diversity']}  "
              f"corr={ca['correlation_proxy']:.2f}  feas={ca['feasibility_score']:.2f}")
    print()


def print_recommendations(combo_analyses: List[Dict]):
    print_section("FINAL RECOMMENDATIONS")
    by_composite = sorted(combo_analyses, key=lambda x: -x["composite_score"])

    # Top overall
    top = by_composite[0]
    print(f"  BEST OVERALL COMBO:")
    print(f"    {' + '.join(top['combo_ids'])}")
    print(f"    Strategies: {', '.join(top['combo'])}")
    print(f"    Composite Score: {top['composite_score']:.4f}")
    print(f"    Why: coverage={top['coverage_pct']}%, {top['risk_diversity']} risk styles, "
          f"{top['category_diversity']} categories, complementarity={top['complementarity']:.2f}")
    print()

    # Best for beginners (high feasibility + good coverage)
    beginner_score = lambda ca: ca["feasibility_score"] * 0.5 + (ca["coverage"] / ca["total_markets"]) * 0.3 + (1 - ca["correlation_proxy"]) * 0.2
    by_beginner = sorted(combo_analyses, key=lambda x: -beginner_score(x))
    beg = by_beginner[0]
    print(f"  BEST FOR BEGINNERS (high feasibility + good coverage):")
    print(f"    {' + '.join(beg['combo_ids'])}")
    print(f"    Strategies: {', '.join(beg['combo'])}")
    print(f"    Feasibility: {beg['feasibility_score']:.2f}, Coverage: {beg['coverage_pct']}%")
    print()

    # Best for advanced traders (max diversification)
    adv_score = lambda ca: ca["complementarity"] * 0.3 + ca["edge_diversity"] / 5 * 0.3 + ca["risk_diversity"] / 5 * 0.2 + ca["category_diversity"] / 7 * 0.2
    by_adv = sorted(combo_analyses, key=lambda x: -adv_score(x))
    adv = by_adv[0]
    print(f"  BEST FOR ADVANCED TRADERS (max diversification):")
    print(f"    {' + '.join(adv['combo_ids'])}")
    print(f"    Strategies: {', '.join(adv['combo'])}")
    print(f"    Edge types: {', '.join(adv['edge_types'])}")
    print(f"    Risk styles: {', '.join(adv['risk_styles'])}")
    print(f"    Categories: {', '.join(adv['categories'])}")
    print()

    # Highest confidence when strategies agree
    by_conf = sorted([ca for ca in combo_analyses if ca["agreement_count"] > 0],
                     key=lambda x: -x["avg_agreement_confidence"])
    if by_conf:
        conf = by_conf[0]
        print(f"  HIGHEST CONFIDENCE WHEN STRATEGIES AGREE:")
        print(f"    {' + '.join(conf['combo_ids'])}")
        print(f"    Agreement on {conf['agreement_count']} markets, "
              f"avg confidence={conf['avg_agreement_confidence']:.3f}, "
              f"avg edge={conf['avg_agreement_edge']:.4f}")
    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    print_divider("#")
    print("  POLYMARKET STRATEGY COMBINATION ANALYSIS")
    print("  Testing synergy between 2-3 strategy combos")
    print_divider("#")

    # Create synthetic markets
    markets = create_synthetic_markets()
    print(f"\nSynthetic markets created: {len(markets)}")
    cats = defaultdict(int)
    for m in markets:
        cats[m.category] += 1
    print(f"Market categories: {dict(cats)}")

    # Instantiate all strategies used in combos
    all_strat_names = set()
    for combo in NAMED_COMBOS.values():
        all_strat_names.update(combo)

    print(f"\nInstantiating {len(all_strat_names)} unique strategies...")
    instances = instantiate_strategies(sorted(all_strat_names))
    print(f"Successfully instantiated: {len(instances)}")
    if len(instances) < len(all_strat_names):
        missing = all_strat_names - set(instances.keys())
        print(f"  (could not instantiate: {missing})")

    # Run each strategy individually
    print("\nRunning individual strategies on synthetic markets...")
    all_results = {}
    for name, strat in sorted(instances.items()):
        result = run_strategy_on_markets(strat, markets)
        all_results[name] = result

    print_individual_strategy_results(all_results, markets)

    # Analyze each named combo
    print(f"\nAnalyzing {len(NAMED_COMBOS)} named combos...")
    combo_analyses = []
    for combo_name, strat_names in NAMED_COMBOS.items():
        # Check all strategies are available
        available = [n for n in strat_names if n in all_results]
        if len(available) < 2:
            print(f"  SKIP: {combo_name} -- insufficient strategies available ({len(available)}/{len(strat_names)})")
            continue
        ca = analyze_combo(available, markets, all_results)
        if ca:
            ca["combo_label"] = combo_name
            combo_analyses.append(ca)

    # Print combo results
    # Sort by composite score
    combo_analyses.sort(key=lambda x: -x["composite_score"])
    print_combo_results(combo_analyses)

    # Print rankings
    print_rankings(combo_analyses)

    # Print final recommendations
    print_recommendations(combo_analyses)

    # Summary table
    print_section("SUMMARY TABLE (sorted by composite score)")
    header = f"{'#':>2} {'Combo':<45} {'Cov%':>5} {'Compl':>6} {'RiskD':>5} {'CatD':>5} {'Corr':>5} {'Feas':>5} {'SCORE':>7}"
    print(header)
    print("-" * len(header))
    for i, ca in enumerate(combo_analyses, 1):
        label = " + ".join(ca["combo_ids"])
        print(f"{i:>2} {label:<45} {ca['coverage_pct']:>5.1f} {ca['complementarity']:>6.3f} "
              f"{ca['risk_diversity']:>5} {ca['category_diversity']:>5} "
              f"{ca['correlation_proxy']:>5.3f} {ca['feasibility_score']:>5.2f} "
              f"{ca['composite_score']:>7.4f}")

    print()
    print_divider("#")
    print("  Analysis complete.")
    print_divider("#")


if __name__ == "__main__":
    main()
