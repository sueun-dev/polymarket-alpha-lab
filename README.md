# Polymarket Alpha Lab

Research repository + fully executable Python trading bot implementing 100 strategies for Polymarket prediction markets.

## Research Documents

| File | Language | Description |
|------|----------|-------------|
| `EN-polymarket-market-inefficiencies.md` | EN | Comprehensive market inefficiency research — past cases, academic foundations, live mispricings (as of Feb 2026), strategies, risks, and 100+ cited sources across EN/KR/CN |
| `EN-polymarket-top-100-strategies.md` | EN | Top 100 trading strategies curated from 600+ internet sources (Reddit, Twitter/X, Substack, Medium, academic papers, GitHub, KR/CN sources). Ranked by Tier S/A/B/C |
| `KR-polymarket-top-100-strategies.md` | KR | Same top 100 strategies document in Korean |

## Strategy Tiers

| Tier | # | Description |
|------|---|-------------|
| **S** | #1-10 | Verified alpha with documented profit records |
| **A** | #11-30 | Strong edge backed by data/research |
| **B** | #31-70 | Solid strategies with reasonable evidence |
| **C** | #71-100 | Experimental edge — innovative but needs validation |

## Trading Bot

All 100 strategies are implemented as executable Python modules with shared core infrastructure.

### Quick Start

```bash
# 1. Clone
git clone https://github.com/sueun-dev/polymarket-alpha-lab.git
cd polymarket-alpha-lab

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env with your API keys (Polymarket, NOAA, Kalshi, etc.)
# Edit config.yaml to enable/disable strategies and tune parameters

# 4. Run (paper trading mode by default)
python3 main.py run

# 5. List available strategies
python3 main.py list

# 6. Run specific strategies only
python3 main.py run --strategy s01_reversing_stupidity --strategy s03_nothing_ever_happens

# 7. Dry run (scan only, no orders)
python3 main.py run --dry-run

# 8. Run backtests
python3 main.py backtest --data-dir data/historical/

# 9. Launch dashboard
streamlit run dashboard/app.py
```

### Project Structure

```
core/               # Shared infrastructure
  client.py         # Polymarket CLOB API wrapper (paper + live modes)
  risk.py           # Portfolio risk management (position limits, daily loss)
  kelly.py          # Kelly Criterion position sizing (Half-Kelly default)
  scanner.py        # Market scanner with filtering & anomaly detection
  base_strategy.py  # Abstract base class for all strategies
  notifier.py       # Telegram / Discord notifications
  models.py         # Pydantic data models (Market, Signal, Order, etc.)
strategies/         # 100 strategy plugins (auto-discovered)
  tier_s/           # #1-#10: Verified alpha
  tier_a/           # #11-#30: Strong edge
  tier_b/           # #31-#70: Solid strategies
  tier_c/           # #71-#100: Experimental
backtest/           # Backtesting engine (slippage simulation, Sharpe/MDD)
dashboard/          # Streamlit web dashboard
data/               # External data collectors (NOAA, Kalshi, sentiment, etc.)
tests/              # 187 unit tests
config.yaml         # Strategy parameters & risk settings
.env.example        # Environment variable template
```

### Configuration

**Trading mode** — set in `config.yaml`:
- `paper` (default): Simulated trading, no real orders
- `live`: Connects to Polymarket CLOB API with real funds

**Risk parameters** — `config.yaml`:
- `max_position_pct`: Max % of portfolio per market (default 10%)
- `max_daily_loss`: Daily stop-loss threshold (default 5%)
- `max_open_positions`: Concurrent position limit (default 20)
- `kelly_fraction`: Kelly sizing fraction (default 0.5 = Half-Kelly)

### Tests

```bash
python3 -m pytest tests/ -v
# 187 tests, all passing
```

## How to Read the Research

1. Start with `EN-polymarket-market-inefficiencies.md` for the research foundation
2. Then read `EN-polymarket-top-100-strategies.md` (or KR version) for actionable strategies
3. Each strategy includes: source, evidence, execution steps, expected edge, and key risks

## Disclaimer

- All data is as of **2026-02-27**
- This repository is for **research purposes only** and does not constitute investment advice
- Prediction market trading involves risk of loss

---

# Polymarket Alpha Lab (한국어)

Polymarket 예측 시장의 비효율성과 트레이딩 전략을 분석한 리서치 + 100개 전략을 구현한 Python 트레이딩 봇 저장소입니다.

## 리서치 문서

| 파일 | 언어 | 설명 |
|------|------|------|
| `EN-polymarket-market-inefficiencies.md` | EN | 시장 비효율성 종합 연구 — 과거 사례, 학술 근거, 라이브 미스프라이싱 (2026년 2월 기준), 전략, 리스크, 영/한/중 100+개 출처 |
| `EN-polymarket-top-100-strategies.md` | EN | 인터넷 600+개 글에서 엄선한 Top 100 트레이딩 전략 (영어 버전) |
| `KR-polymarket-top-100-strategies.md` | KR | 동일한 Top 100 전략 문서 (한국어 버전) |

## 전략 티어

| 티어 | 번호 | 설명 |
|------|------|------|
| **S** | #1-10 | 검증된 알파 — 실제 수익 기록 존재 |
| **A** | #11-30 | 강한 엣지 — 데이터/연구 기반 |
| **B** | #31-70 | 견고한 전략 — 합리적 증거 존재 |
| **C** | #71-100 | 실험적 엣지 — 혁신적이나 검증 필요 |

## 트레이딩 봇

100개 전략이 모두 실행 가능한 Python 모듈로 구현되어 있습니다.

### 빠른 시작

```bash
# 1. 클론
git clone https://github.com/sueun-dev/polymarket-alpha-lab.git
cd polymarket-alpha-lab

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 설정
cp .env.example .env
# .env에 API 키 입력 (Polymarket, NOAA, Kalshi 등)
# config.yaml에서 전략 활성화/비활성화 및 파라미터 조정

# 4. 실행 (기본: 페이퍼 트레이딩)
python3 main.py run

# 5. 전략 목록 확인
python3 main.py list

# 6. 특정 전략만 실행
python3 main.py run --strategy s01_reversing_stupidity --strategy s03_nothing_ever_happens

# 7. 드라이런 (스캔만, 주문 없음)
python3 main.py run --dry-run

# 8. 백테스트 실행
python3 main.py backtest --data-dir data/historical/

# 9. 대시보드 실행
streamlit run dashboard/app.py
```

### 설정

**트레이딩 모드** — `config.yaml`:
- `paper` (기본): 시뮬레이션, 실제 주문 없음
- `live`: Polymarket CLOB API 연결, 실제 자금 사용

**리스크 파라미터** — `config.yaml`:
- `max_position_pct`: 마켓당 최대 포트폴리오 비율 (기본 10%)
- `max_daily_loss`: 일일 손실 한도 (기본 5%)
- `max_open_positions`: 동시 포지션 한도 (기본 20개)
- `kelly_fraction`: 켈리 비율 (기본 0.5 = Half-Kelly)

### 테스트

```bash
python3 -m pytest tests/ -v
# 187개 테스트 전체 통과
```

## 읽는 방법

1. `EN-polymarket-market-inefficiencies.md`로 리서치 기반 파악
2. `KR-polymarket-top-100-strategies.md` (또는 EN 버전)으로 실행 가능한 전략 확인
3. 각 전략에는 출처, 증거, 실행 방법, 예상 엣지, 핵심 리스크 포함

## 참고

- 모든 데이터는 **2026-02-27** 기준입니다
- 본 저장소는 **연구 목적**이며 투자 조언이 아닙니다
- 예측 시장 트레이딩에는 손실 위험이 수반됩니다
