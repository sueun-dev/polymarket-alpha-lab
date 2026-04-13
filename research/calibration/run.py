"""Polymarket Calibration Analysis — 전체 파이프라인.

Usage:
    python run.py              # 전체 파이프라인 (fetch → preprocess → analyze → visualize)
    python run.py --skip-fetch # API 호출 건너뛰기 (이미 데이터가 있을 때)
"""

import argparse
import sys
from pathlib import Path

from src.fetch import fetch_resolved_markets, load_raw_data, save_raw_data
from src.preprocess import preprocess, save_preprocessed
from src.analyze import run_analysis, save_results
from src.visualize import generate_all_charts


def main():
    parser = argparse.ArgumentParser(description="Polymarket Calibration Analysis")
    parser.add_argument(
        "--skip-fetch", action="store_true",
        help="Skip API fetch, use existing data/resolved_markets.json",
    )
    parser.add_argument(
        "--max-markets", type=int, default=5000,
        help="Maximum number of markets to fetch (default: 5000)",
    )
    parser.add_argument(
        "--min-volume", type=float, default=1000.0,
        help="Minimum volume filter in USD (default: 1000)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Polymarket Calibration Analysis")
    print("=" * 60)

    # Step 1: Fetch
    if args.skip_fetch:
        data_path = Path("data/resolved_markets.json")
        if not data_path.exists():
            print(f"Error: {data_path} not found. Run without --skip-fetch first.")
            sys.exit(1)
        print("\n[1/4] Loading existing data...")
        markets = load_raw_data()
        print(f"  Loaded {len(markets)} markets from cache")
    else:
        print("\n[1/4] Fetching data from Polymarket API...")
        markets = fetch_resolved_markets(
            max_markets=args.max_markets,
            min_volume=args.min_volume,
        )
        save_raw_data(markets)

    if not markets:
        print("Error: No markets collected. Exiting.")
        sys.exit(1)

    # Step 2: Preprocess
    print("\n[2/4] Preprocessing data...")
    df = preprocess(markets)
    save_preprocessed(df)

    if df.empty:
        print("Error: No valid markets after preprocessing. Exiting.")
        sys.exit(1)

    # Step 3: Analyze
    print("\n[3/4] Running analysis...")
    results = run_analysis(df)
    save_results(results)

    # Step 4: Visualize
    print("\n[4/4] Generating charts...")
    charts = generate_all_charts(df, results)

    # Summary
    print("\n" + "=" * 60)
    print("  Analysis Complete!")
    print("=" * 60)
    brier = results["brier_scores"]
    print(f"  Total markets analyzed: {results['summary']['total_markets']:,}")
    print(f"  Overall Brier Score:    {brier['overall']['brier_score']:.4f}")
    print(f"  Brier Skill Score:      {brier['skill_score']:.4f}")
    print(f"  Baseline Brier:         {brier['baseline']['brier_score']:.4f}")
    print(f"  Charts generated:       {len(charts)}")
    print(f"\n  Results: output/results.json")
    print(f"  Charts:  output/charts/")
    print("=" * 60)


if __name__ == "__main__":
    main()
