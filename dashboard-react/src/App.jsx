import { useId, useMemo, useState } from 'react'
import './App.css'
import {
  BETTING_PLATFORMS,
  BETTING_STEPS,
  EQUITY_SERIES,
  MARKET_OPPORTUNITIES,
  NAV_ITEMS,
  OVERVIEW_METRICS,
  RECENT_TRADES,
  STRATEGY_ALLOCATION,
  TIER_OPTIONS,
  buildBacktest,
} from './data/mockData'
import { STRATEGY_CATALOG } from './data/strategyCatalog'

const I18N = {
  en: {
    brandSubtitle: 'Liquid Research Console',
    mode: 'Mode',
    modeValue: 'Paper Trading',
    health: 'Health: Stable',
    language: 'Language',
    nav: {
      overview: 'Overview',
      betting: 'Where to Bet',
      strategies: 'Strategies',
      markets: 'Markets',
      backtest: 'Backtest',
    },
    viewTitle: {
      overview: 'Portfolio Overview',
      betting: 'Where You Can Bet',
      strategies: 'Strategy Registry (All 100)',
      markets: 'Market Scanner',
      backtest: 'Backtest Lab',
    },
    viewSubtitle: {
      overview: 'Live account pulse and allocation map.',
      betting: 'Platforms, setup flow, and first-trade checklist.',
      strategies: 'Complete strategy inventory synced to repository files.',
      markets: 'Dynamic signal filters for current opportunities.',
      backtest: 'What-if simulation before deployment.',
    },
    topbarTag: 'React Dashboard',
    signals: 'Signals',
    live: 'Live',
    heroTag: 'Portfolio Pulse',
    heroTitle: 'Edge-driven prediction trading, surfaced in real time.',
    heroDesc: 'Current configuration emphasizes contrarian NO-bias stack plus high-probability yield harvesting.',
    heroStats: ['Signals 24h: 31', 'Win Streak: 7', 'Max Daily Loss Guard: 5%'],
    equityCurve: 'Equity Curve',
    sessions: 'Trailing 34 sessions',
    strategyAllocation: 'Strategy Allocation',
    weightedByRisk: 'Weighted by risk budget',
    recentTrades: 'Recent Trades',
    latestExec: 'Latest executions',
    active: 'Active',
    whereToBetHeading: 'Recommended Platforms',
    whereToBetSub: 'Use official links and verify region/policy eligibility before funding.',
    firstTradeHeading: 'How to place your first bet safely',
    firstTradeSub: 'Execution checklist',
    platform: 'Platform',
    region: 'Availability',
    notes: 'Notes',
    openSite: 'Open Site',
    strategySearch: 'Search strategy',
    strategyPlaceholder: 's01_reversing_stupidity',
    tier: 'Tier',
    strategyRegistry: 'Strategy Registry',
    rows: 'rows',
    strategyCols: {
      num: '#',
      id: 'ID',
      name: 'Name',
      tier: 'Tier',
      data: 'Required Data',
      path: 'Path',
    },
    allImplemented: 'All strategies shown are implemented in this repository.',
    scan: {
      minVolume: 'Min Volume',
      minEdge: 'Min Edge',
      run: 'Run Scan',
      last: 'Last scan',
      suggested: 'Suggested Strategy',
      volume: 'Volume',
      yesPrice: 'YES Price',
      edge: 'Edge',
      confidence: 'Confidence',
      expires: 'Expires In',
      emptyTitle: 'No opportunities at this threshold',
      emptyBody: 'Lower min volume or edge to widen scan results.',
    },
    backtest: {
      strategy: 'Strategy',
      initialBalance: 'Initial Balance',
      slippage: 'Slippage (%)',
      run: 'Recalculate Backtest',
      endingBalance: 'Ending Balance',
      annualReturn: 'Annual Return',
      riskAdjusted: 'Risk-adjusted',
      sharpe: 'Sharpe Ratio',
      highBetter: 'Higher is better',
      maxDd: 'Max Drawdown',
      peakToTrough: 'Peak-to-trough',
      equity: 'Backtest Equity',
      equitySub: '12-month simulation',
      summary: 'Execution Summary',
      summarySub: 'Scenario stats',
      trades: 'Trades',
      winRate: 'Win Rate',
      slippageInput: 'Slippage Input',
    },
  },
  kr: {
    brandSubtitle: '리퀴드 리서치 콘솔',
    mode: '모드',
    modeValue: '페이퍼 트레이딩',
    health: '상태: 안정적',
    language: '언어',
    nav: {
      overview: '개요',
      betting: '베팅 가이드',
      strategies: '전략',
      markets: '마켓',
      backtest: '백테스트',
    },
    viewTitle: {
      overview: '포트폴리오 개요',
      betting: '어디서 베팅할 수 있나',
      strategies: '전략 레지스트리 (전체 100개)',
      markets: '마켓 스캐너',
      backtest: '백테스트 랩',
    },
    viewSubtitle: {
      overview: '실시간 계좌 상태와 배분 현황입니다.',
      betting: '플랫폼, 세팅 순서, 첫 베팅 체크리스트를 제공합니다.',
      strategies: '저장소의 실제 파일과 동기화된 전체 전략 목록입니다.',
      markets: '현재 기회를 찾기 위한 동적 필터입니다.',
      backtest: '실전 투입 전 시나리오 검증용입니다.',
    },
    topbarTag: '리액트 대시보드',
    signals: '시그널',
    live: '실행 중',
    heroTag: '포트폴리오 펄스',
    heroTitle: '예측시장 엣지를 실시간으로 시각화합니다.',
    heroDesc: '현재 설정은 NO 역발상 스택과 고확률 수확 전략을 중심으로 구성되어 있습니다.',
    heroStats: ['24시간 시그널: 31', '연속 수익: 7', '일일 손실 가드: 5%'],
    equityCurve: '자산 곡선',
    sessions: '최근 34개 세션',
    strategyAllocation: '전략 배분',
    weightedByRisk: '리스크 예산 기준 가중치',
    recentTrades: '최근 체결',
    latestExec: '최신 실행 내역',
    active: '활성',
    whereToBetHeading: '추천 베팅 플랫폼',
    whereToBetSub: '공식 링크를 사용하고, 입금 전 지역/정책 제한을 확인하세요.',
    firstTradeHeading: '첫 베팅을 안전하게 진행하는 방법',
    firstTradeSub: '실행 체크리스트',
    platform: '플랫폼',
    region: '이용 가능 범위',
    notes: '설명',
    openSite: '사이트 열기',
    strategySearch: '전략 검색',
    strategyPlaceholder: 's01_reversing_stupidity',
    tier: '티어',
    strategyRegistry: '전략 레지스트리',
    rows: '행',
    strategyCols: {
      num: '#',
      id: 'ID',
      name: '이름',
      tier: '티어',
      data: '필요 데이터',
      path: '경로',
    },
    allImplemented: '표시된 모든 전략은 이 저장소에 구현된 파일 기준입니다.',
    scan: {
      minVolume: '최소 거래량',
      minEdge: '최소 엣지',
      run: '스캔 실행',
      last: '마지막 스캔',
      suggested: '추천 전략',
      volume: '거래량',
      yesPrice: 'YES 가격',
      edge: '엣지',
      confidence: '신뢰도',
      expires: '만료까지',
      emptyTitle: '현재 조건에서 기회가 없습니다',
      emptyBody: '최소 거래량 또는 엣지 조건을 낮춰보세요.',
    },
    backtest: {
      strategy: '전략',
      initialBalance: '초기 자본',
      slippage: '슬리피지 (%)',
      run: '백테스트 재계산',
      endingBalance: '최종 잔고',
      annualReturn: '연 수익률',
      riskAdjusted: '리스크 조정',
      sharpe: '샤프 비율',
      highBetter: '높을수록 좋음',
      maxDd: '최대 낙폭',
      peakToTrough: '고점 대비 하락폭',
      equity: '백테스트 자산 곡선',
      equitySub: '12개월 시뮬레이션',
      summary: '실행 요약',
      summarySub: '시나리오 통계',
      trades: '거래 수',
      winRate: '승률',
      slippageInput: '입력 슬리피지',
    },
  },
}

const MONEY = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 2,
})

const PCT = new Intl.NumberFormat('en-US', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

function fmtMoney(value) {
  return MONEY.format(value)
}

function fmtPct(value) {
  return PCT.format(value)
}

function fmtCompact(value) {
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value)
}

function priceColor(value) {
  return value >= 0 ? 'is-positive' : 'is-negative'
}

function nameByLang(item, lang) {
  if (lang === 'kr' && item.titleKr) {
    return item.titleKr
  }
  return item.titleEn
}

function GlassChart({ points }) {
  const gradientId = useId().replace(/:/g, '')
  const width = 680
  const height = 240
  const pad = 16
  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min || 1

  const polyline = points
    .map((point, index) => {
      const x = pad + (index / (points.length - 1)) * (width - pad * 2)
      const y = height - pad - ((point - min) / range) * (height - pad * 2)
      return `${x},${y}`
    })
    .join(' ')

  const area = `${pad},${height - pad} ${polyline} ${width - pad},${height - pad}`

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="line-chart" aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(80, 168, 255, 0.58)" />
          <stop offset="100%" stopColor="rgba(80, 168, 255, 0.04)" />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#${gradientId})`} />
      <polyline points={polyline} fill="none" stroke="rgba(56, 133, 240, 0.94)" strokeWidth="3" />
    </svg>
  )
}

function AllocationRing({ rows, activeLabel }) {
  const { segments } = rows.reduce(
    (accumulator, entry) => {
      const start = accumulator.offset
      const end = start + entry.value
      return {
        offset: end,
        segments: [...accumulator.segments, `${entry.color} ${start}% ${end}%`],
      }
    },
    { offset: 0, segments: [] },
  )

  return (
    <div className="allocation-wrap">
      <div className="allocation-ring" style={{ background: `conic-gradient(${segments.join(', ')})` }}>
        <div className="allocation-center">
          <p>{activeLabel}</p>
          <strong>92%</strong>
        </div>
      </div>
      <div className="legend-list">
        {rows.map((entry) => (
          <div key={entry.label} className="legend-row">
            <span className="legend-dot" style={{ backgroundColor: entry.color }} />
            <span>{entry.label}</span>
            <strong>{entry.value}%</strong>
          </div>
        ))}
      </div>
    </div>
  )
}

function Sidebar({ activeView, onViewChange, language, onLanguageChange, text }) {
  return (
    <aside className="glass sidebar">
      <div>
        <div className="brand-wrap">
          <div className="brand-mark">PM</div>
          <div>
            <h1>Polymarket Lab</h1>
            <p>{text.brandSubtitle}</p>
          </div>
        </div>

        <div className="language-switch" role="group" aria-label={text.language}>
          <span>{text.language}</span>
          <button
            className={`lang-btn ${language === 'en' ? 'active' : ''}`}
            type="button"
            onClick={() => onLanguageChange('en')}
          >
            EN
          </button>
          <button
            className={`lang-btn ${language === 'kr' ? 'active' : ''}`}
            type="button"
            onClick={() => onLanguageChange('kr')}
          >
            KR
          </button>
        </div>

        <nav className="nav-list" aria-label="Dashboard sections">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={`nav-btn ${item.id === activeView ? 'active' : ''}`}
              onClick={() => onViewChange(item.id)}
              type="button"
            >
              {text.nav[item.id]}
            </button>
          ))}
        </nav>
      </div>
      <div className="status-panel">
        <p>{text.mode}</p>
        <strong>{text.modeValue}</strong>
        <span>{text.health}</span>
      </div>
    </aside>
  )
}

function OverviewView({ text }) {
  return (
    <div className="view-grid">
      <section className="glass section hero-card">
        <div>
          <p className="eyebrow">{text.heroTag}</p>
          <h2>{text.heroTitle}</h2>
          <p className="subtle">{text.heroDesc}</p>
        </div>
        <div className="hero-stats">
          {text.heroStats.map((row) => (
            <span key={row}>{row}</span>
          ))}
        </div>
      </section>

      <section className="metric-grid">
        {OVERVIEW_METRICS.map((metric) => {
          const formatted =
            metric.format === 'currency' ? fmtMoney(metric.value) : Intl.NumberFormat('en-US').format(metric.value)
          const deltaLabel =
            metric.format === 'currency'
              ? `${metric.delta >= 0 ? '+' : ''}${fmtMoney(metric.delta)}`
              : `${metric.delta >= 0 ? '+' : ''}${metric.delta}`

          return (
            <article key={metric.id} className="glass metric-card">
              <p>{metric.label}</p>
              <strong>{formatted}</strong>
              <span className={priceColor(metric.delta)}>{deltaLabel}</span>
            </article>
          )
        })}
      </section>

      <section className="glass section">
        <div className="section-head">
          <h3>{text.equityCurve}</h3>
          <span>{text.sessions}</span>
        </div>
        <GlassChart points={EQUITY_SERIES} />
        <div className="section-footer">
          <span>Start: {fmtMoney(EQUITY_SERIES[0])}</span>
          <span>Now: {fmtMoney(EQUITY_SERIES[EQUITY_SERIES.length - 1])}</span>
        </div>
      </section>

      <section className="glass section">
        <div className="section-head">
          <h3>{text.strategyAllocation}</h3>
          <span>{text.weightedByRisk}</span>
        </div>
        <AllocationRing rows={STRATEGY_ALLOCATION} activeLabel={text.active} />
      </section>

      <section className="glass section full-span">
        <div className="section-head">
          <h3>{text.recentTrades}</h3>
          <span>{text.latestExec}</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Strategy</th>
                <th>Market</th>
                <th>Side</th>
                <th>Price</th>
                <th>Size</th>
                <th>PnL</th>
              </tr>
            </thead>
            <tbody>
              {RECENT_TRADES.map((trade) => (
                <tr key={trade.id}>
                  <td>{trade.time}</td>
                  <td>{trade.strategy}</td>
                  <td>{trade.market}</td>
                  <td>{trade.side}</td>
                  <td>{trade.price.toFixed(2)}</td>
                  <td>{trade.size}</td>
                  <td className={priceColor(trade.pnl)}>{fmtMoney(trade.pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function BettingView({ language, text }) {
  return (
    <div className="view-grid">
      <section className="glass section full-span">
        <div className="section-head">
          <h3>{text.whereToBetHeading}</h3>
          <span>{text.whereToBetSub}</span>
        </div>
        <div className="platform-grid">
          {BETTING_PLATFORMS.map((platform) => (
            <article key={platform.id} className="platform-card">
              <h4>{language === 'kr' ? platform.nameKr : platform.nameEn}</h4>
              <p>
                <strong>{text.region}:</strong> {language === 'kr' ? platform.regionKr : platform.regionEn}
              </p>
              <p>
                <strong>{text.notes}:</strong> {language === 'kr' ? platform.notesKr : platform.notesEn}
              </p>
              <a href={platform.url} target="_blank" rel="noreferrer">
                {text.openSite}
              </a>
            </article>
          ))}
        </div>
      </section>

      <section className="glass section full-span">
        <div className="section-head">
          <h3>{text.firstTradeHeading}</h3>
          <span>{text.firstTradeSub}</span>
        </div>
        <ol className="steps-list">
          {BETTING_STEPS[language].map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>
    </div>
  )
}

function StrategiesView({ language, text, search, tier, onSearchChange, onTierChange }) {
  const rows = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return STRATEGY_CATALOG.filter((row) => {
      const tierPass = tier === 'all' || row.tier === tier
      const nameEn = row.titleEn.toLowerCase()
      const nameKr = row.titleKr.toLowerCase()
      const textPass =
        needle === '' ||
        row.id.toLowerCase().includes(needle) ||
        nameEn.includes(needle) ||
        nameKr.includes(needle)
      return tierPass && textPass
    })
  }, [search, tier])

  return (
    <div className="view-grid">
      <section className="glass section full-span controls-row strategies-controls">
        <div className="control-group">
          <label htmlFor="strategy-search">{text.strategySearch}</label>
          <input
            id="strategy-search"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder={text.strategyPlaceholder}
          />
        </div>
        <div className="control-group">
          <label htmlFor="tier-filter">{text.tier}</label>
          <select id="tier-filter" value={tier} onChange={(event) => onTierChange(event.target.value)}>
            {TIER_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="glass section full-span">
        <div className="section-head">
          <h3>{text.strategyRegistry}</h3>
          <span>
            {rows.length} {text.rows}
          </span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{text.strategyCols.num}</th>
                <th>{text.strategyCols.id}</th>
                <th>{text.strategyCols.name}</th>
                <th>{text.strategyCols.tier}</th>
                <th>{text.strategyCols.data}</th>
                <th>{text.strategyCols.path}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.num}</td>
                  <td>{row.id}</td>
                  <td>{nameByLang(row, language)}</td>
                  <td>
                    <span className="pill">{row.tier}</span>
                  </td>
                  <td>{row.requiredData.length > 0 ? row.requiredData.join(', ') : 'none'}</td>
                  <td>{row.path}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="registry-note">{text.allImplemented}</p>
      </section>
    </div>
  )
}

function MarketsView({ text, minVolume, minEdge, onMinVolume, onMinEdge, lastScan, onScan }) {
  const filtered = useMemo(() => {
    return MARKET_OPPORTUNITIES.filter((market) => market.volume >= minVolume && market.edge >= minEdge)
  }, [minVolume, minEdge])

  return (
    <div className="view-grid">
      <section className="glass section full-span controls-row">
        <div className="control-group">
          <label htmlFor="min-volume">
            {text.scan.minVolume}: {fmtCompact(minVolume)}
          </label>
          <input
            id="min-volume"
            type="range"
            min="1000"
            max="90000"
            step="500"
            value={minVolume}
            onChange={(event) => onMinVolume(Number(event.target.value))}
          />
        </div>
        <div className="control-group">
          <label htmlFor="min-edge">
            {text.scan.minEdge}: {fmtPct(minEdge)}
          </label>
          <input
            id="min-edge"
            type="range"
            min="0.01"
            max="0.15"
            step="0.01"
            value={minEdge}
            onChange={(event) => onMinEdge(Number(event.target.value))}
          />
        </div>
        <div className="control-action">
          <button type="button" onClick={onScan}>
            {text.scan.run}
          </button>
          <span>
            {text.scan.last}: {lastScan.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </section>

      {filtered.map((market) => (
        <article key={market.id} className="glass section market-card">
          <div className="section-head">
            <h3>{market.question}</h3>
            <span>{market.category}</span>
          </div>
          <div className="market-grid">
            <div>
              <p>{text.scan.suggested}</p>
              <strong>{market.strategy}</strong>
            </div>
            <div>
              <p>{text.scan.volume}</p>
              <strong>{fmtMoney(market.volume)}</strong>
            </div>
            <div>
              <p>{text.scan.yesPrice}</p>
              <strong>{market.yesPrice.toFixed(2)}</strong>
            </div>
            <div>
              <p>{text.scan.edge}</p>
              <strong className="is-positive">{fmtPct(market.edge)}</strong>
            </div>
            <div>
              <p>{text.scan.confidence}</p>
              <strong>{fmtPct(market.confidence)}</strong>
            </div>
            <div>
              <p>{text.scan.expires}</p>
              <strong>{market.expiresIn}</strong>
            </div>
          </div>
        </article>
      ))}

      {filtered.length === 0 && (
        <section className="glass section full-span empty-state">
          <h3>{text.scan.emptyTitle}</h3>
          <p>{text.scan.emptyBody}</p>
        </section>
      )}
    </div>
  )
}

function BacktestView({ text, selectedStrategy, initialBalance, slippagePercent, result, onStrategy, onBalance, onSlippage, onRun }) {
  return (
    <div className="view-grid">
      <section className="glass section full-span controls-row">
        <div className="control-group">
          <label htmlFor="bt-strategy">{text.backtest.strategy}</label>
          <select id="bt-strategy" value={selectedStrategy} onChange={(event) => onStrategy(event.target.value)}>
            {STRATEGY_CATALOG.map((row) => (
              <option key={row.id} value={row.id}>
                {row.id}
              </option>
            ))}
          </select>
        </div>
        <div className="control-group">
          <label htmlFor="bt-balance">{text.backtest.initialBalance}</label>
          <input
            id="bt-balance"
            type="number"
            min="1000"
            step="500"
            value={initialBalance}
            onChange={(event) => onBalance(Number(event.target.value) || 0)}
          />
        </div>
        <div className="control-group">
          <label htmlFor="bt-slippage">{text.backtest.slippage}</label>
          <input
            id="bt-slippage"
            type="number"
            min="0"
            max="2"
            step="0.1"
            value={slippagePercent}
            onChange={(event) => onSlippage(Number(event.target.value) || 0)}
          />
        </div>
        <div className="control-action">
          <button type="button" onClick={onRun}>
            {text.backtest.run}
          </button>
        </div>
      </section>

      <section className="metric-grid full-span">
        <article className="glass metric-card">
          <p>{text.backtest.endingBalance}</p>
          <strong>{fmtMoney(result.endingBalance)}</strong>
          <span className={priceColor(result.endingBalance - result.initialBalance)}>
            {result.endingBalance >= result.initialBalance ? '+' : ''}
            {fmtMoney(result.endingBalance - result.initialBalance)}
          </span>
        </article>
        <article className="glass metric-card">
          <p>{text.backtest.annualReturn}</p>
          <strong>{fmtPct(result.annualReturn)}</strong>
          <span className="is-positive">{text.backtest.riskAdjusted}</span>
        </article>
        <article className="glass metric-card">
          <p>{text.backtest.sharpe}</p>
          <strong>{result.sharpe.toFixed(2)}</strong>
          <span>{text.backtest.highBetter}</span>
        </article>
        <article className="glass metric-card">
          <p>{text.backtest.maxDd}</p>
          <strong>{fmtPct(result.maxDrawdown)}</strong>
          <span className="is-negative">{text.backtest.peakToTrough}</span>
        </article>
      </section>

      <section className="glass section">
        <div className="section-head">
          <h3>{text.backtest.equity}</h3>
          <span>{text.backtest.equitySub}</span>
        </div>
        <GlassChart points={result.equity} />
      </section>

      <section className="glass section">
        <div className="section-head">
          <h3>{text.backtest.summary}</h3>
          <span>{text.backtest.summarySub}</span>
        </div>
        <div className="summary-grid">
          <div>
            <p>{text.backtest.strategy}</p>
            <strong>{result.strategyId}</strong>
          </div>
          <div>
            <p>{text.backtest.trades}</p>
            <strong>{result.trades}</strong>
          </div>
          <div>
            <p>{text.backtest.winRate}</p>
            <strong>{fmtPct(result.winRate)}</strong>
          </div>
          <div>
            <p>{text.backtest.slippageInput}</p>
            <strong>{slippagePercent.toFixed(1)}%</strong>
          </div>
        </div>
      </section>
    </div>
  )
}

function App() {
  const [language, setLanguage] = useState('en')
  const text = I18N[language]

  const [activeView, setActiveView] = useState('overview')
  const [strategySearch, setStrategySearch] = useState('')
  const [tierFilter, setTierFilter] = useState('all')

  const [minVolume, setMinVolume] = useState(5000)
  const [minEdge, setMinEdge] = useState(0.03)
  const [lastScan, setLastScan] = useState(() => new Date())

  const [selectedStrategy, setSelectedStrategy] = useState('s03_nothing_ever_happens')
  const [initialBalance, setInitialBalance] = useState(10000)
  const [slippagePercent, setSlippagePercent] = useState(0.5)
  const [backtestResult, setBacktestResult] = useState(() =>
    buildBacktest('s03_nothing_ever_happens', 10000, 0.005),
  )

  function renderView() {
    if (activeView === 'betting') {
      return <BettingView language={language} text={text} />
    }

    if (activeView === 'strategies') {
      return (
        <StrategiesView
          language={language}
          text={text}
          search={strategySearch}
          tier={tierFilter}
          onSearchChange={setStrategySearch}
          onTierChange={setTierFilter}
        />
      )
    }

    if (activeView === 'markets') {
      return (
        <MarketsView
          text={text}
          minVolume={minVolume}
          minEdge={minEdge}
          onMinVolume={setMinVolume}
          onMinEdge={setMinEdge}
          lastScan={lastScan}
          onScan={() => setLastScan(new Date())}
        />
      )
    }

    if (activeView === 'backtest') {
      return (
        <BacktestView
          text={text}
          selectedStrategy={selectedStrategy}
          initialBalance={initialBalance}
          slippagePercent={slippagePercent}
          result={backtestResult}
          onStrategy={setSelectedStrategy}
          onBalance={setInitialBalance}
          onSlippage={setSlippagePercent}
          onRun={() =>
            setBacktestResult(buildBacktest(selectedStrategy, initialBalance, slippagePercent / 100))
          }
        />
      )
    }

    return <OverviewView text={text} />
  }

  return (
    <div className="dashboard-root">
      <div className="bg-layer">
        <span className="blob blob-a" />
        <span className="blob blob-b" />
        <span className="blob blob-c" />
      </div>

      <div className="app-layout">
        <Sidebar
          activeView={activeView}
          onViewChange={setActiveView}
          language={language}
          onLanguageChange={setLanguage}
          text={text}
        />

        <main className="main-stage">
          <header className="glass topbar">
            <div>
              <p className="eyebrow">{text.topbarTag}</p>
              <h2>{text.viewTitle[activeView]}</h2>
              <p className="subtle">{text.viewSubtitle[activeView]}</p>
            </div>
            <div className="topbar-meta">
              <span>UTC {new Date().toISOString().slice(11, 16)}</span>
              <span>
                {text.signals}: {MARKET_OPPORTUNITIES.length}
              </span>
              <span className="live-pill">{text.live}</span>
            </div>
          </header>

          {renderView()}
        </main>
      </div>
    </div>
  )
}

export default App
