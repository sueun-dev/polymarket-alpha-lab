from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard_api import Runtime, run_live_scan


def fmt_price(value) -> str:
    try:
        if value is None:
            return "-"
        return f"{float(value):.4f}"
    except Exception:
        return "-"


def main() -> None:
    parser = argparse.ArgumentParser(description="Live S01 manual-entry report from public Polymarket APIs.")
    parser.add_argument("--min-edge", type=float, default=0.03)
    parser.add_argument("--min-volume", type=float, default=10000)
    parser.add_argument("--max-markets", type=int, default=300)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()

    runtime = Runtime()
    rows = run_live_scan(
        runtime=runtime,
        min_edge=args.min_edge,
        min_volume=args.min_volume,
        max_markets=args.max_markets,
        limit=args.limit,
        strategy_names=["s01_reversing_stupidity"],
    )

    print(f"S01 live manual report | rows={len(rows)} | min_edge={args.min_edge:.2f} | min_volume={args.min_volume:.0f}")
    print("-" * 100)
    for index, row in enumerate(rows, start=1):
        plan = row.get("manualPlan") or {}
        print(f"[{index}] {row['question']}")
        print(f"    url: {row.get('marketUrl') or '-'}")
        print(
            f"    market: yes={fmt_price(row.get('yesPrice'))} "
            f"no={fmt_price(row.get('noPrice'))} "
            f"edge={fmt_price(row.get('edge'))} conf={fmt_price(row.get('confidence'))}"
        )
        print(
            f"    plan: status={plan.get('status', '-')} "
            f"trigger_yes>={fmt_price(plan.get('trigger_yes_price_gte'))} "
            f"trigger_no<={fmt_price(plan.get('trigger_no_price_lte'))} "
            f"limit<={fmt_price(plan.get('recommended_limit_no_price', plan.get('suggested_limit_no_price')))} "
            f"max={fmt_price(plan.get('do_not_chase_above_no_price'))}"
        )
        print(
            f"    quote: ask={fmt_price(plan.get('best_ask_no_price'))} "
            f"bid={fmt_price(plan.get('best_bid_no_price'))} "
            f"spread={fmt_price(plan.get('spread_no_price'))} "
            f"size={fmt_price(plan.get('size'))}"
        )
        print(f"    instruction: {plan.get('instruction_kr', '-')}")
        print("-" * 100)


if __name__ == "__main__":
    main()
