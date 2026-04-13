"""Calibration 분석 결과 시각화."""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

# 스타일 설정
sns.set_theme(style="whitegrid", font_scale=1.1)
COLORS = sns.color_palette("husl", 8)
CHART_DIR = Path("output/charts")

BIN_ORDER = [
    "0-10%", "10-20%", "20-30%", "30-40%", "40-50%",
    "50-60%", "60-70%", "70-80%", "80-90%", "90-100%",
]
BIN_MIDPOINTS = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]


def setup_output_dir():
    CHART_DIR.mkdir(parents=True, exist_ok=True)


def plot_overall_calibration(results: dict) -> str:
    """차트 1: 전체 Calibration Curve + 신뢰구간."""
    setup_output_dir()

    cal = pd.DataFrame(results["calibration_overall"])
    if cal.empty:
        print("No calibration data to plot.")
        return ""

    fig, ax = plt.subplots(figsize=(8, 8))

    # 대각선 (perfect calibration)
    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Perfect Calibration", linewidth=1.5)

    # 신뢰구간
    ax.fill_between(
        cal["bin_midpoint"], cal["ci_low"], cal["ci_high"],
        alpha=0.2, color=COLORS[0], label="95% CI",
    )

    # Calibration curve
    ax.plot(
        cal["bin_midpoint"], cal["actual_rate"],
        "o-", color=COLORS[0], markersize=8, linewidth=2.5,
        label="Polymarket Calibration",
    )

    # 각 점에 샘플 수 표시
    for _, row in cal.iterrows():
        ax.annotate(
            f'n={int(row["count"])}',
            (row["bin_midpoint"], row["actual_rate"]),
            textcoords="offset points", xytext=(0, 12),
            fontsize=8, ha="center", color="gray",
        )

    brier = results["brier_scores"]["overall"]["brier_score"]
    skill = results["brier_scores"]["skill_score"]
    n_total = results["summary"]["total_markets"]

    ax.set_xlabel("Predicted Probability (Market Price)", fontsize=13)
    ax.set_ylabel("Observed Frequency", fontsize=13)
    ax.set_title(
        f"Polymarket Calibration Curve\n"
        f"N={n_total:,} markets | Brier={brier:.4f} | Skill={skill:.4f}",
        fontsize=14, fontweight="bold",
    )
    ax.legend(loc="upper left", fontsize=11)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_aspect("equal")

    path = CHART_DIR / "01_overall_calibration.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return str(path)


def plot_category_calibration(results: dict) -> str:
    """차트 2: 카테고리별 Calibration Curves 오버레이."""
    setup_output_dir()

    cal = pd.DataFrame(results["calibration_by_category"])
    if cal.empty or "category_mapped" not in cal.columns:
        print("No category calibration data to plot.")
        return ""

    categories = sorted(cal["category_mapped"].unique())
    fig, ax = plt.subplots(figsize=(10, 8))

    ax.plot([0, 1], [0, 1], "k--", alpha=0.4, linewidth=1.5, label="Perfect")

    for i, cat in enumerate(categories):
        cat_data = cal[cal["category_mapped"] == cat].sort_values("bin_midpoint")
        if len(cat_data) < 3:
            continue
        n_total = int(cat_data["count"].sum())
        ax.plot(
            cat_data["bin_midpoint"], cat_data["actual_rate"],
            "o-", color=COLORS[i % len(COLORS)], markersize=6, linewidth=2,
            label=f"{cat} (n={n_total:,})", alpha=0.85,
        )

    ax.set_xlabel("Predicted Probability", fontsize=13)
    ax.set_ylabel("Observed Frequency", fontsize=13)
    ax.set_title("Calibration by Category", fontsize=14, fontweight="bold")
    ax.legend(loc="upper left", fontsize=10)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_aspect("equal")

    path = CHART_DIR / "02_category_calibration.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return str(path)


def plot_brier_scores(results: dict) -> str:
    """차트 3: 카테고리별 Brier Score 바 차트."""
    setup_output_dir()

    brier = results["brier_scores"]
    by_group = brier.get("by_group", {})
    if not by_group:
        print("No group Brier scores to plot.")
        return ""

    categories = []
    scores = []
    n_markets = []
    reliable = []

    for cat, data in sorted(by_group.items()):
        categories.append(cat)
        scores.append(data["brier_score"])
        n_markets.append(data["n_markets"])
        reliable.append(data["reliable"])

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = [COLORS[0] if r else "#cccccc" for r in reliable]
    bars = ax.barh(categories, scores, color=colors, edgecolor="white", height=0.6)

    # 값 표시
    for bar, score, n, rel in zip(bars, scores, n_markets, reliable):
        suffix = "" if rel else " *"
        ax.text(
            bar.get_width() + 0.002, bar.get_y() + bar.get_height() / 2,
            f"{score:.4f} (n={n:,}){suffix}",
            va="center", fontsize=10,
        )

    # 전체 기준선
    overall_brier = brier["overall"]["brier_score"]
    ax.axvline(overall_brier, color="red", linestyle="--", alpha=0.7, label=f"Overall: {overall_brier:.4f}")

    # Base rate 기준선
    baseline_brier = brier["baseline"]["brier_score"]
    ax.axvline(baseline_brier, color="gray", linestyle=":", alpha=0.7, label=f"Baseline: {baseline_brier:.4f}")

    ax.set_xlabel("Brier Score (lower = better)", fontsize=12)
    ax.set_title("Brier Score by Category", fontsize=14, fontweight="bold")
    ax.legend(fontsize=10)
    ax.set_xlim(0, max(scores) * 1.4)

    # 주석
    ax.text(
        0.98, 0.02, "* n < 30, for reference only",
        transform=ax.transAxes, fontsize=9, ha="right", color="gray",
    )

    path = CHART_DIR / "03_brier_scores.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return str(path)


def plot_bias_heatmap(results: dict) -> str:
    """차트 4: 편향 히트맵 (X: 확률 구간, Y: 카테고리)."""
    setup_output_dir()

    cal = pd.DataFrame(results["calibration_by_category"])
    if cal.empty or "category_mapped" not in cal.columns:
        print("No data for bias heatmap.")
        return ""

    # 피벗 테이블 생성
    pivot = cal.pivot_table(
        index="category_mapped", columns="prob_bin",
        values="bias", aggfunc="mean",
    )

    # 구간 순서 정렬
    available_bins = [b for b in BIN_ORDER if b in pivot.columns]
    pivot = pivot[available_bins]

    fig, ax = plt.subplots(figsize=(12, 6))

    sns.heatmap(
        pivot, ax=ax, cmap="RdYlGn", center=0,
        annot=True, fmt=".2f", linewidths=0.5,
        cbar_kws={"label": "Bias (positive = underconfident)"},
        vmin=-0.3, vmax=0.3,
    )

    ax.set_xlabel("Probability Bin", fontsize=12)
    ax.set_ylabel("Category", fontsize=12)
    ax.set_title(
        "Market Bias by Category and Probability Bin\n"
        "Green = Underconfident (market price too low) | Red = Overconfident (market price too high)",
        fontsize=13, fontweight="bold",
    )

    path = CHART_DIR / "04_bias_heatmap.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return str(path)


def plot_sample_distribution(df: pd.DataFrame) -> str:
    """차트 5: 확률 구간별 마켓 수 히스토그램."""
    setup_output_dir()

    fig, ax = plt.subplots(figsize=(10, 5))

    bin_counts = df["prob_bin"].value_counts().reindex(BIN_ORDER, fill_value=0)

    bars = ax.bar(
        range(len(BIN_ORDER)), bin_counts.values,
        color=COLORS[2], edgecolor="white", width=0.7,
    )

    for bar, count in zip(bars, bin_counts.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
            str(int(count)), ha="center", fontsize=10, fontweight="bold",
        )

    ax.set_xticks(range(len(BIN_ORDER)))
    ax.set_xticklabels(BIN_ORDER, rotation=45, ha="right")
    ax.set_xlabel("Probability Bin", fontsize=12)
    ax.set_ylabel("Number of Markets", fontsize=12)
    ax.set_title("Distribution of Markets by Predicted Probability", fontsize=14, fontweight="bold")

    path = CHART_DIR / "05_sample_distribution.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return str(path)


def create_summary_table(results: dict) -> str:
    """차트 6: Summary Stats 테이블."""
    setup_output_dir()

    brier = results["brier_scores"]
    by_group = brier.get("by_group", {})

    rows = []

    # 전체
    bias_data = results.get("bias_analysis", {}).get("summary", {})
    rows.append({
        "Category": "OVERALL",
        "N Markets": f'{brier["overall"]["n_markets"]:,}',
        "Brier Score": f'{brier["overall"]["brier_score"]:.4f}',
        "Skill Score": f'{brier["skill_score"]:.4f}',
        "Mean |Bias|": f'{bias_data.get("mean_absolute_bias", "N/A")}',
        "Max Bias Bin": bias_data.get("max_overconfidence", {}).get("bin", "N/A"),
    })

    # 카테고리별
    for cat, data in sorted(by_group.items()):
        reliable_marker = "" if data["reliable"] else " *"
        rows.append({
            "Category": f"{cat}{reliable_marker}",
            "N Markets": f'{data["n_markets"]:,}',
            "Brier Score": f'{data["brier_score"]:.4f}',
            "Skill Score": f'{data["skill_score"]:.4f}',
            "Mean |Bias|": "-",
            "Max Bias Bin": "-",
        })

    table_df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(12, max(3, len(rows) * 0.5 + 1.5)))
    ax.axis("off")

    table = ax.table(
        cellText=table_df.values,
        colLabels=table_df.columns,
        cellLoc="center",
        loc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)

    # 헤더 스타일
    for j in range(len(table_df.columns)):
        cell = table[0, j]
        cell.set_facecolor("#2C3E50")
        cell.set_text_props(color="white", fontweight="bold")

    # 첫 번째 행 (OVERALL) 강조
    for j in range(len(table_df.columns)):
        cell = table[1, j]
        cell.set_facecolor("#EBF5FB")

    ax.set_title(
        "Polymarket Calibration Summary",
        fontsize=14, fontweight="bold", pad=20,
    )

    path = CHART_DIR / "06_summary_table.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")
    return str(path)


def generate_all_charts(df: pd.DataFrame, results: dict) -> list[str]:
    """모든 차트 생성."""
    print("\n=== Generating Charts ===")
    charts = [
        plot_overall_calibration(results),
        plot_category_calibration(results),
        plot_brier_scores(results),
        plot_bias_heatmap(results),
        plot_sample_distribution(df),
        create_summary_table(results),
    ]
    charts = [c for c in charts if c]
    print(f"\nGenerated {len(charts)} charts in {CHART_DIR}/")
    return charts


if __name__ == "__main__":
    import json

    from src.preprocess import load_preprocessed

    df = load_preprocessed()
    with open("output/results.json") as f:
        results = json.load(f)
    generate_all_charts(df, results)
