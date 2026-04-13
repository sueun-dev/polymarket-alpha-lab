"""Calibration, Brier Score, Bias 분석."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def compute_calibration(df: pd.DataFrame, group_col: str | None = None) -> pd.DataFrame:
    """확률 구간별 calibration 데이터를 계산.

    Args:
        df: 전처리된 DataFrame (yes_price, outcome_binary, prob_bin 필요).
        group_col: 그룹별 분석 시 컬럼명 (e.g., "category_mapped").

    Returns:
        구간별 calibration DataFrame.
    """
    bin_order = [
        "0-10%", "10-20%", "20-30%", "30-40%", "40-50%",
        "50-60%", "60-70%", "70-80%", "80-90%", "90-100%",
    ]
    bin_midpoints = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]

    groups = ["prob_bin"]
    if group_col:
        groups = [group_col, "prob_bin"]

    agg = df.groupby(groups, observed=True).agg(
        actual_rate=("outcome_binary", "mean"),
        count=("outcome_binary", "count"),
        avg_forecast=("yes_price", "mean"),
    ).reset_index()

    # bin 중앙값 매핑 (prob_bin을 string으로 변환 후 매핑)
    midpoint_map = dict(zip(bin_order, bin_midpoints))
    agg["prob_bin"] = agg["prob_bin"].astype(str)
    agg["bin_midpoint"] = agg["prob_bin"].map(midpoint_map)

    # 95% 신뢰구간 (Wilson score interval)
    ci_low, ci_high = [], []
    for _, row in agg.iterrows():
        n = row["count"]
        p = row["actual_rate"]
        if n > 0:
            lo, hi = _wilson_ci(p, n)
            ci_low.append(lo)
            ci_high.append(hi)
        else:
            ci_low.append(np.nan)
            ci_high.append(np.nan)

    agg["ci_low"] = ci_low
    agg["ci_high"] = ci_high

    # 편향 계산 — bin 중앙값이 아닌 실제 평균 예측값 대비
    agg["bias"] = agg["actual_rate"] - agg["avg_forecast"]

    return agg


def _wilson_ci(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score confidence interval for a proportion."""
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    spread = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denominator
    return max(0, center - spread), min(1, center + spread)


def compute_brier_score(df: pd.DataFrame, group_col: str | None = None) -> dict:
    """Brier Score 계산.

    Args:
        df: 전처리된 DataFrame.
        group_col: 그룹별 계산 시 컬럼명.

    Returns:
        Brier Score 딕셔너리.
    """
    results = {}

    # 전체 Brier Score
    overall = np.mean((df["yes_price"] - df["outcome_binary"]) ** 2)
    results["overall"] = {
        "brier_score": round(float(overall), 4),
        "n_markets": len(df),
    }

    # 기준선: base rate를 사용한 Brier Score
    base_rate = df["outcome_binary"].mean()
    baseline_brier = np.mean((base_rate - df["outcome_binary"]) ** 2)
    results["baseline"] = {
        "brier_score": round(float(baseline_brier), 4),
        "base_rate": round(float(base_rate), 4),
    }

    # Brier Skill Score (기준선 대비 개선도)
    if baseline_brier > 0:
        skill_score = 1 - overall / baseline_brier
    else:
        skill_score = 0.0
    results["skill_score"] = round(float(skill_score), 4)

    # 그룹별
    if group_col and group_col in df.columns:
        results["by_group"] = {}
        for name, group in df.groupby(group_col, observed=True):
            if len(group) < 5:
                continue
            brier = np.mean((group["yes_price"] - group["outcome_binary"]) ** 2)
            group_base_rate = group["outcome_binary"].mean()
            group_baseline = np.mean((group_base_rate - group["outcome_binary"]) ** 2)
            group_skill = 1 - brier / group_baseline if group_baseline > 0 else 0.0

            results["by_group"][str(name)] = {
                "brier_score": round(float(brier), 4),
                "n_markets": len(group),
                "base_rate": round(float(group_base_rate), 4),
                "skill_score": round(float(group_skill), 4),
                "reliable": len(group) >= 30,
            }

    return results


def compute_bias_analysis(calibration_df: pd.DataFrame) -> dict:
    """편향 방향 분석 요약.

    Args:
        calibration_df: compute_calibration()의 결과.

    Returns:
        편향 분석 요약 딕셔너리.
    """
    results = {}

    # 전체 calibration (group_col=None인 경우)
    overconfident_bins = calibration_df[calibration_df["bias"] < -0.02]
    underconfident_bins = calibration_df[calibration_df["bias"] > 0.02]

    results["summary"] = {
            "overconfident_bins": len(overconfident_bins),
            "underconfident_bins": len(underconfident_bins),
            "max_overconfidence": {
                "bin": str(overconfident_bins.loc[overconfident_bins["bias"].idxmin(), "prob_bin"])
                if len(overconfident_bins) > 0 else None,
                "bias": round(float(overconfident_bins["bias"].min()), 4)
                if len(overconfident_bins) > 0 else None,
            },
            "max_underconfidence": {
                "bin": str(underconfident_bins.loc[underconfident_bins["bias"].idxmax(), "prob_bin"])
                if len(underconfident_bins) > 0 else None,
                "bias": round(float(underconfident_bins["bias"].max()), 4)
                if len(underconfident_bins) > 0 else None,
            },
            "mean_absolute_bias": round(float(calibration_df["bias"].abs().mean()), 4),
    }

    return results


def run_analysis(df: pd.DataFrame) -> dict:
    """전체 분석 파이프라인 실행.

    Args:
        df: 전처리된 DataFrame.

    Returns:
        전체 분석 결과 딕셔너리.
    """
    print("Computing overall calibration...")
    cal_overall = compute_calibration(df)

    print("Computing category calibration...")
    cal_by_category = compute_calibration(df, group_col="category_mapped")

    print("Computing Brier scores...")
    brier = compute_brier_score(df, group_col="category_mapped")

    print("Computing bias analysis...")
    bias = compute_bias_analysis(cal_overall)

    results = {
        "calibration_overall": cal_overall.to_dict(orient="records"),
        "calibration_by_category": cal_by_category.to_dict(orient="records"),
        "brier_scores": brier,
        "bias_analysis": bias,
        "summary": {
            "total_markets": len(df),
            "categories": df["category_mapped"].value_counts().to_dict(),
            "date_range": {
                "earliest": str(df["resolved_at"].min()) if "resolved_at" in df.columns else None,
                "latest": str(df["resolved_at"].max()) if "resolved_at" in df.columns else None,
            },
        },
    }

    print(f"Analysis complete. Brier Score: {brier['overall']['brier_score']}")
    return results


def save_results(results: dict, output_path: str = "output/results.json"):
    """분석 결과를 JSON으로 저장."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"Results saved to {path}")


if __name__ == "__main__":
    from src.preprocess import load_preprocessed

    df = load_preprocessed()
    results = run_analysis(df)
    save_results(results)
