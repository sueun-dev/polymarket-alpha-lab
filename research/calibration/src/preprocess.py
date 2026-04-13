"""수집된 마켓 데이터의 전처리 및 카테고리 매핑."""

import re
from pathlib import Path

import pandas as pd

# 카테고리 매핑 키워드 — 단어 경계(\b)로 매칭해야 하는 짧은 키워드는 별도 표시
# (keyword, require_word_boundary)
CATEGORY_KEYWORDS: dict[str, list[tuple[str, bool]]] = {
    "Politics": [
        ("election", False), ("president", False), ("vote", False),
        ("trump", False), ("biden", False), ("democrat", False), ("republican", False),
        ("congress", False), ("senate", False), ("governor", False),
        ("political", False), ("policy", False), ("government", False),
        ("cabinet", False), ("legislation", False), ("supreme court", False),
        ("primaries", False), ("electoral", False), ("inauguration", False),
        ("impeach", False), ("parliament", False), ("minister", False), ("mayor", False),
        ("tariff", False), ("pardon", False), ("state of the union", False),
    ],
    "Crypto": [
        ("bitcoin", False), ("btc", True), ("ethereum", False), ("eth", True),
        ("crypto", False), ("token", False), ("blockchain", False),
        ("defi", True), ("nft", True), ("solana", False), ("sol", True),
        ("altcoin", False), ("binance", False), ("coinbase", False),
        ("stablecoin", False), ("usdt", True), ("usdc", True),
        ("airdrop", False), ("halving", False), ("xrp", True),
        ("fdv", True),
    ],
    "Sports": [
        ("nba", True), ("nfl", True), ("mlb", True), ("nhl", True),
        ("soccer", False), ("football", False), ("basketball", False),
        ("baseball", False), ("tennis", False), ("golf", False),
        ("ufc", True), ("mma", True), ("boxing", False), ("f1", True),
        ("formula 1", False), ("world cup", False), ("super bowl", False),
        ("championship", False), ("playoffs", False), ("olympics", False),
        ("premier league", False), ("goalscorer", False), ("grand prix", False),
        ("win on 20", False), ("beat", False), ("fc ", False),
        ("vs.", False), ("serie a", False), ("la liga", False),
        ("bundesliga", False), ("ligue 1", False), ("ncaa", False),
        ("finals", False),
    ],
    "Pop Culture": [
        ("oscar", False), ("grammy", False), ("emmy", False),
        ("movie", False), ("film", False), ("album", False), ("celebrity", False),
        ("taylor swift", False), ("entertainment", False), ("netflix", False),
        ("spotify", False), ("tiktok", False), ("youtube", False),
        ("reality tv", False), ("awards", False), ("box office", False),
        ("streaming", False), ("golden globe", False), ("sag award", False),
    ],
    "Science/Tech": [
        ("artificial intelligence", False), ("openai", False), ("gpt", True),
        ("spacex", False), ("nasa", True), ("climate", False), ("fda", True),
        ("vaccine", False), ("rocket", False), ("quantum", False),
        ("robot", False), ("semiconductor", False), ("neural", False),
        ("crispr", False), ("starship", False),
    ],
}


def _keyword_matches(text: str, keyword: str, word_boundary: bool) -> bool:
    """키워드가 텍스트에 매칭되는지 확인. word_boundary=True면 단어 경계 사용."""
    if word_boundary:
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))
    return keyword in text


def assign_category(question: str, api_category: str, tags: list) -> str:
    """마켓 질문과 메타데이터를 기반으로 상위 카테고리를 할당."""
    # 1. API category 직접 매핑
    if api_category:
        cat_lower = api_category.lower().strip()
        for category in CATEGORY_KEYWORDS:
            if cat_lower == category.lower():
                return category

    # 2. Question 텍스트에서 키워드 매칭 (점수 기반)
    q_lower = question.lower()
    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw, wb in keywords if _keyword_matches(q_lower, kw, wb))
        if score > 0:
            scores[category] = score

    if scores:
        return max(scores, key=scores.get)

    # 3. Tags에서 키워드 매칭
    if tags:
        tags_text = " ".join(
            t.lower() if isinstance(t, str) else str(t).lower() for t in tags
        )
        for category, keywords in CATEGORY_KEYWORDS.items():
            for kw, wb in keywords:
                if _keyword_matches(tags_text, kw, wb):
                    return category

    return "Other"


def preprocess(markets: list[dict]) -> pd.DataFrame:
    """원본 마켓 데이터를 분석용 DataFrame으로 변환."""
    df = pd.DataFrame(markets)

    if df.empty:
        print("Warning: No markets to preprocess.")
        return df

    # yes_price가 없는 행 제거 (price history 수집 실패)
    df = df.dropna(subset=["yes_price"])
    df = df[df["yes_price"] > 0].copy()

    # yes_price를 0~1 범위로 클리핑 (Brier Score에는 클리핑 불필요하나 극단값 보정)
    df["yes_price"] = df["yes_price"].clip(0.0, 1.0)

    # outcome_binary가 이미 있으면 사용, 없으면 계산
    if "outcome_binary" not in df.columns:
        df["outcome_binary"] = (df["outcome"] == "Yes").astype(int)

    # 카테고리 할당
    df["category_mapped"] = df.apply(
        lambda row: assign_category(
            row.get("question", ""),
            row.get("category", ""),
            row.get("tags", []),
        ),
        axis=1,
    )

    # 확률 구간(bin) 할당 — 10개 구간
    bins = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    labels = [
        "0-10%", "10-20%", "20-30%", "30-40%", "40-50%",
        "50-60%", "60-70%", "70-80%", "80-90%", "90-100%",
    ]
    df["prob_bin"] = pd.cut(df["yes_price"], bins=bins, labels=labels, include_lowest=True)

    # 날짜 파싱
    for col in ["end_date", "resolved_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    # 정렬
    df = df.sort_values("volume", ascending=False).reset_index(drop=True)

    print(f"Preprocessed: {len(df)} markets, {df['category_mapped'].nunique()} categories")
    print(f"Category distribution:\n{df['category_mapped'].value_counts().to_string()}")

    return df


def save_preprocessed(df: pd.DataFrame, output_path: str = "data/preprocessed.csv"):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"Saved preprocessed data to {path}")


def load_preprocessed(input_path: str = "data/preprocessed.csv") -> pd.DataFrame:
    return pd.read_csv(input_path)


if __name__ == "__main__":
    from src.fetch import load_raw_data

    markets = load_raw_data()
    df = preprocess(markets)
    save_preprocessed(df)
