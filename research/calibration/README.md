# Polymarket Calibration Analysis

How accurate are Polymarket's prediction markets? This project collects resolved binary markets and measures whether market prices actually correspond to real-world probabilities.

If a market trades at 70%, does the event actually happen 70% of the time? That's **calibration** — and this tool measures it.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Full pipeline: fetch data from API → preprocess → analyze → generate charts
python run.py

# Re-run analysis on cached data (skip API calls)
python run.py --skip-fetch

# Customize
python run.py --max-markets 2000 --min-volume 5000
```

## What It Does

### 1. Data Collection (`src/fetch.py`)

Fetches resolved binary (Yes/No) markets from the Polymarket Gamma API, then enriches each market with its **pre-resolution price** from the CLOB price history API.

The pre-resolution price is the last non-settlement trading price within 7 days of resolution — not the final settlement price (which is always 0 or 1). This distinction is critical for calibration analysis and is non-trivial to extract.

### 2. Preprocessing (`src/preprocess.py`)

- Filters to binary Yes/No markets with minimum volume threshold
- Assigns categories (Politics, Crypto, Sports, Pop Culture, Science/Tech) via keyword matching with word-boundary awareness
- Bins predicted probabilities into deciles (0-10%, 10-20%, ..., 90-100%)

### 3. Analysis (`src/analyze.py`)

- **Calibration Curve**: For each probability bin, compares predicted probability to observed frequency
- **Brier Score**: Single-number accuracy metric (0 = perfect, 1 = worst)
- **Brier Skill Score**: Improvement over a naive base-rate forecast
- **Bias Analysis**: Direction and magnitude of miscalibration per bin
- **Wilson Score Confidence Intervals**: 95% CIs for each bin's observed frequency

### 4. Visualization (`src/visualize.py`)

Generates 6 publication-ready charts:

| Chart | Description |
|-------|-------------|
| Overall Calibration Curve | Predicted vs. observed with 95% CI |
| Category Calibration | Per-category curves overlaid |
| Brier Score Comparison | Bar chart by category |
| Bias Heatmap | Category x probability bin heatmap |
| Sample Distribution | Histogram of markets per probability bin |
| Summary Table | Key metrics in tabular format |

## Output

```
output/
├── charts/
│   ├── 01_overall_calibration.png
│   ├── 02_category_calibration.png
│   ├── 03_brier_scores.png
│   ├── 04_bias_heatmap.png
│   ├── 05_sample_distribution.png
│   └── 06_summary_table.png
└── results.json          # Full analysis results
```

## Methodology Notes

### Pre-Resolution Price Extraction

Polymarket's `outcomePrices` field contains settlement prices (0 or 1), not the last trading price. The `lastTradePrice` field is also contaminated by post-resolution trades (~94% are near 0 or 1).

This tool solves this by querying the CLOB API's price history endpoint and extracting the last price between 0.02-0.98 within 7 days of resolution. Markets where no valid pre-resolution price can be found are excluded.

### Brier Score

```
Brier Score = (1/N) * sum((forecast - outcome)^2)
```

Where `forecast` is the market price (0-1) and `outcome` is the actual result (0 or 1). Lower is better.

### Calibration

Markets are grouped into 10 probability bins. For each bin, we compare:
- **Expected**: average predicted probability in the bin
- **Observed**: fraction of events that actually occurred (resolved Yes)

Perfect calibration = the diagonal line (predicted probability equals observed frequency).

## Limitations

- Sample size varies by run. Small bins (N < 30) should be interpreted with caution.
- Pre-resolution price uses daily-resolution price history. For very short-lived markets, this may miss intraday price movements.
- Category assignment is keyword-based and may misclassify edge cases.
- This analysis uses the last available price, not a time-weighted average — results may differ with alternative price selection methods.

## Requirements

- Python 3.10+
- See `requirements.txt` for dependencies

## License

MIT
