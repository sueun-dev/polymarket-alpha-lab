import { useEffect, useId, useMemo, useState } from 'react'
import './App.css'
import { BETTING_PLATFORMS, BETTING_STEPS, NAV_ITEMS, TIER_OPTIONS } from './data/mockData'

const API_BASE = '/api'

const I18N = {
  en: {
    brandSubtitle: 'Live Research Console',
    mode: 'Mode',
    modeValue: 'Live Data Feed',
    health: 'Health: Live',
    language: 'Language',
    nav: {
      overview: 'Overview',
      betting: 'Where to Bet',
      strategies: 'Strategies',
      markets: 'Markets',
      backtest: 'Backtest',
    },
    viewTitle: {
      overview: 'Live Market Overview',
      betting: 'Where You Can Bet',
      strategies: 'Strategy Registry (All 100)',
      markets: 'Live Opportunity Scanner',
      backtest: 'Historical Backtest (Live Data)',
    },
    viewSubtitle: {
      overview: 'Real-time data from Polymarket API and strategy runtime scans.',
      betting: 'Platforms, setup flow, and first-trade checklist.',
      strategies: 'Complete strategy inventory synced to repository files.',
      markets: 'Signal filters over live markets and live strategy logic.',
      backtest: 'Runs on real historical markets from Polymarket APIs.',
    },
    topbarTag: 'React + Live API',
    signals: 'Signals',
    live: 'Live',
    heroTag: 'Live Pulse',
    heroTitle: 'No mock data. Everything is pulled from live sources.',
    heroDesc: 'Overview and scanner are sourced from live market data and strategy scans at request time.',
    heroStats: ['Source: gamma-api.polymarket.com', 'Signals: strategy runtime scan', 'Backtest: historical API fetch'],
    cards: {
      marketCount: 'Active Markets',
      totalVolume: 'Total Volume',
      avgLiquidity: 'Avg Liquidity',
      signalCount: 'Live Signals',
    },
    equityCurve: 'Volume Curve (Top Markets)',
    sessions: 'Live market volume distribution',
    strategyAllocation: 'Signal Allocation by Strategy',
    weightedByRisk: 'Derived from live scan results',
    recentTrades: 'Top Live Signals',
    latestExec: 'From live strategy analyze() output',
    active: 'Active',
    loading: 'Loading live data...',
    refresh: 'Refresh',
    whereToBetHeading: 'Recommended Platforms',
    whereToBetSub: 'Use official links and verify region/policy eligibility before funding.',
    firstTradeHeading: 'How to place your first bet safely',
    firstTradeSub: 'Execution checklist',
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
      status: 'Status',
      data: 'Required Data',
      path: 'Path',
    },
    strategyStates: {
      implemented: 'implemented',
      placeholder: 'placeholder',
    },
    allImplemented: 'Rows are parsed from local strategy files at request time.',
    strategyDetail: {
      title: 'Strategy Detail',
      hint: 'Click a row to open the popup detail.',
      close: 'Close',
      name: 'Name',
      overview: 'Overview',
      scanLogic: 'Scan Logic',
      analyzeLogic: 'Signal Logic',
      keyParams: 'Key Parameters',
      paramName: 'Name',
      paramValue: 'Value',
      none: 'none',
      noSelection: 'Select a strategy row to view details.',
    },
    scan: {
      minVolume: 'Min Volume',
      minEdge: 'Min Edge',
      run: 'Run Scan',
      last: 'Last scan',
      suggested: 'Strategy',
      volume: 'Volume',
      side: 'Side',
      marketPrice: 'Market Price',
      edge: 'Edge',
      confidence: 'Confidence',
      expires: 'End Date',
      plan: 'Plan',
      openMarket: 'Open market',
      manualOnly: 'Manual-only',
      waitForEntry: 'Wait for entry',
      enterNow: 'Enter now',
      skipChase: 'Skip chase',
      trigger: 'Trigger',
      limitPrice: 'Limit',
      maxChase: 'Max chase',
      takeProfit: 'Take profit',
      reviewBelow: 'Review below',
      emptyTitle: 'No opportunities at this threshold',
      emptyBody: 'Lower min volume or edge to widen scan results.',
    },
    backtest: {
      strategy: 'Strategy',
      initialBalance: 'Initial Balance',
      slippage: 'Slippage (%)',
      run: 'Run Live Backtest',
      endingBalance: 'Ending Balance',
      annualReturn: 'Total Return',
      riskAdjusted: 'From historical data',
      sharpe: 'Sharpe Ratio',
      highBetter: 'Higher is better',
      maxDd: 'Max Drawdown',
      peakToTrough: 'Peak-to-trough',
      equity: 'Backtest Equity',
      equitySub: 'Generated from live historical fetch',
      summary: 'Execution Summary',
      summarySub: 'Runtime stats',
      trades: 'Trades',
      winRate: 'Win Rate',
      slippageInput: 'Slippage Input',
      pointsUsed: 'Historical Points',
    },
  },
  kr: {
    brandSubtitle: '실시간 리서치 콘솔',
    mode: '모드',
    modeValue: '실시간 데이터 피드',
    health: '상태: 실시간',
    language: '언어',
    nav: {
      overview: '개요',
      betting: '베팅 가이드',
      strategies: '전략',
      markets: '마켓',
      backtest: '백테스트',
    },
    viewTitle: {
      overview: '실시간 마켓 개요',
      betting: '어디서 베팅할 수 있나',
      strategies: '전략 레지스트리 (전체 100개)',
      markets: '실시간 기회 스캐너',
      backtest: '히스토리 기반 백테스트 (실데이터)',
    },
    viewSubtitle: {
      overview: 'Polymarket API와 전략 런타임 스캔 기반 실시간 데이터입니다.',
      betting: '플랫폼, 세팅 순서, 첫 베팅 체크리스트를 제공합니다.',
      strategies: '저장소의 실제 전략 파일과 동기화된 전체 목록입니다.',
      markets: '실시간 시장 + 실전략 로직 결과를 필터링합니다.',
      backtest: 'Polymarket 과거 시장 API 기반으로 실행됩니다.',
    },
    topbarTag: 'React + Live API',
    signals: '시그널',
    live: '실행 중',
    heroTag: '라이브 상태',
    heroTitle: '모의 데이터 없이 실데이터만 표시합니다.',
    heroDesc: '개요와 스캐너는 요청 시점의 실시간 시장 데이터/전략 스캔 결과를 사용합니다.',
    heroStats: ['출처: gamma-api.polymarket.com', '시그널: 전략 런타임 스캔', '백테스트: 히스토리 API'],
    cards: {
      marketCount: '활성 마켓 수',
      totalVolume: '총 거래량',
      avgLiquidity: '평균 유동성',
      signalCount: '실시간 시그널 수',
    },
    equityCurve: '거래량 곡선 (상위 마켓)',
    sessions: '실시간 거래량 분포',
    strategyAllocation: '전략별 시그널 배분',
    weightedByRisk: '실시간 스캔 결과 기반',
    recentTrades: '상위 실시간 시그널',
    latestExec: '실전략 analyze() 결과',
    active: '활성',
    loading: '실시간 데이터 로딩 중...',
    refresh: '새로고침',
    whereToBetHeading: '추천 베팅 플랫폼',
    whereToBetSub: '공식 링크를 사용하고, 입금 전 지역/정책 제한을 확인하세요.',
    firstTradeHeading: '첫 베팅을 안전하게 진행하는 방법',
    firstTradeSub: '실행 체크리스트',
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
      status: '상태',
      data: '필요 데이터',
      path: '경로',
    },
    strategyStates: {
      implemented: '구현됨',
      placeholder: '플레이스홀더',
    },
    allImplemented: '행 데이터는 요청 시 실제 전략 파일을 파싱해 생성됩니다.',
    strategyDetail: {
      title: '전략 상세',
      hint: '행을 클릭하면 팝업으로 상세를 볼 수 있습니다.',
      close: '닫기',
      name: '이름',
      overview: '개요',
      scanLogic: '스캔 로직',
      analyzeLogic: '시그널 로직',
      keyParams: '핵심 파라미터',
      paramName: '항목',
      paramValue: '값',
      none: '없음',
      noSelection: '상세를 보려면 전략 행을 선택하세요.',
    },
    scan: {
      minVolume: '최소 거래량',
      minEdge: '최소 엣지',
      run: '스캔 실행',
      last: '마지막 스캔',
      suggested: '전략',
      volume: '거래량',
      side: '방향',
      marketPrice: '시장 가격',
      edge: '엣지',
      confidence: '신뢰도',
      expires: '종료일',
      plan: '실행 플랜',
      openMarket: '마켓 열기',
      manualOnly: '수동 전용',
      waitForEntry: '대기',
      enterNow: '지금 진입',
      skipChase: '추격 금지',
      trigger: '트리거',
      limitPrice: '지정가',
      maxChase: '상단 한도',
      takeProfit: '익절 검토',
      reviewBelow: '재검토 구간',
      emptyTitle: '현재 조건에서 기회가 없습니다',
      emptyBody: '최소 거래량 또는 엣지 조건을 낮춰보세요.',
    },
    backtest: {
      strategy: '전략',
      initialBalance: '초기 자본',
      slippage: '슬리피지 (%)',
      run: '실데이터 백테스트 실행',
      endingBalance: '최종 잔고',
      annualReturn: '총 수익률',
      riskAdjusted: '히스토리 데이터 기반',
      sharpe: '샤프 비율',
      highBetter: '높을수록 좋음',
      maxDd: '최대 낙폭',
      peakToTrough: '고점 대비 하락폭',
      equity: '백테스트 자산 곡선',
      equitySub: '실시간 히스토리 페치로 생성',
      summary: '실행 요약',
      summarySub: '런타임 통계',
      trades: '거래 수',
      winRate: '승률',
      slippageInput: '입력 슬리피지',
      pointsUsed: '히스토리 포인트',
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
  return MONEY.format(value || 0)
}

function fmtPct(value) {
  return PCT.format(value || 0)
}

function fmtPrice(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '-'
  }
  return Number(value).toFixed(3)
}

function fmtCompact(value) {
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value || 0)
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

function detailByLang(item, lang, field) {
  if (!item) {
    return ''
  }
  const krField = `${field}Kr`
  if (lang === 'kr' && item[krField]) {
    return item[krField]
  }
  return item[field] || ''
}

function planStatusLabel(plan, text) {
  switch (plan?.status) {
    case 'enter_now':
      return text.scan.enterNow
    case 'skip_chase':
      return text.scan.skipChase
    default:
      return text.scan.waitForEntry
  }
}

function compactManualSummary(plan, text) {
  if (!plan) {
    return '-'
  }
  const limit = fmtPrice(plan.recommended_limit_no_price || plan.suggested_limit_no_price)
  if (plan.status === 'wait') {
    return `${text.scan.waitForEntry}: YES >= ${fmtPrice(plan.trigger_yes_price_gte)} / NO <= ${fmtPrice(plan.trigger_no_price_lte)}`
  }
  if (plan.status === 'skip_chase') {
    return `${text.scan.skipChase}: NO > ${fmtPrice(plan.do_not_chase_above_no_price)}`
  }
  return `NO <= ${limit}`
}

async function fetchJson(path) {
  const response = await fetch(path)
  if (!response.ok) {
    let detail = ''
    try {
      const data = await response.json()
      detail = data.error || JSON.stringify(data)
    } catch {
      detail = await response.text()
    }
    throw new Error(`${response.status} ${detail}`)
  }
  return response.json()
}

function GlassChart({ points }) {
  const gradientId = useId().replace(/:/g, '')
  const safe = points && points.length >= 2 ? points : [0, 0]
  const width = 680
  const height = 240
  const pad = 16
  const min = Math.min(...safe)
  const max = Math.max(...safe)
  const range = max - min || 1

  const polyline = safe
    .map((point, index) => {
      const x = pad + (index / (safe.length - 1)) * (width - pad * 2)
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
  if (!rows || rows.length === 0) {
    return <p className="registry-note">No signal allocation yet.</p>
  }

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
          <strong>{rows.length}</strong>
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

function OverviewView({ text, data, loading, error, onRefresh }) {
  const metrics = [
    { key: 'marketCount', label: text.cards.marketCount, value: data?.marketCount ?? 0, fmt: 'number' },
    { key: 'totalVolume', label: text.cards.totalVolume, value: data?.totalVolume ?? 0, fmt: 'money' },
    { key: 'avgLiquidity', label: text.cards.avgLiquidity, value: data?.avgLiquidity ?? 0, fmt: 'money' },
    { key: 'signalCount', label: text.cards.signalCount, value: data?.signalCount ?? 0, fmt: 'number' },
  ]

  const allocationRows = useMemo(() => {
    const palette = ['#4db6ff', '#6be2c8', '#8ed77f', '#ffc76a', '#f8a3a0', '#9eb4d6']
    const counts = {}
    for (const signal of data?.topSignals || []) {
      counts[signal.strategy] = (counts[signal.strategy] || 0) + 1
    }
    const entries = Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)

    const total = entries.reduce((acc, row) => acc + row[1], 0) || 1
    return entries.map((row, index) => ({
      label: row[0],
      value: Math.round((row[1] / total) * 100),
      color: palette[index % palette.length],
    }))
  }, [data?.topSignals])

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
          <button type="button" className="refresh-btn" onClick={onRefresh}>
            {text.refresh}
          </button>
        </div>
      </section>

      <section className="metric-grid">
        {metrics.map((metric) => (
          <article key={metric.key} className="glass metric-card">
            <p>{metric.label}</p>
            <strong>
              {metric.fmt === 'money'
                ? fmtMoney(metric.value)
                : Intl.NumberFormat('en-US').format(metric.value)}
            </strong>
          </article>
        ))}
      </section>

      <section className="glass section">
        <div className="section-head">
          <h3>{text.equityCurve}</h3>
          <span>{text.sessions}</span>
        </div>
        <GlassChart points={data?.volumeCurve || []} />
      </section>

      <section className="glass section">
        <div className="section-head">
          <h3>{text.strategyAllocation}</h3>
          <span>{text.weightedByRisk}</span>
        </div>
        <AllocationRing rows={allocationRows} activeLabel={text.active} />
      </section>

      <section className="glass section full-span">
        <div className="section-head">
          <h3>{text.recentTrades}</h3>
          <span>{text.latestExec}</span>
        </div>

        {loading && <p className="registry-note">{text.loading}</p>}
        {error && <p className="is-negative registry-note">{error}</p>}

        {!loading && !error && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Question</th>
                  <th>Side</th>
                  <th>Price</th>
                  <th>Edge</th>
                  <th>Confidence</th>
                  <th>{text.scan.plan}</th>
                  <th>Volume</th>
                </tr>
              </thead>
              <tbody>
                {(data?.topSignals || []).map((signal, index) => (
                  <tr key={`${signal.marketId}-${signal.strategy}-${index}`}>
                    <td>{signal.strategy}</td>
                    <td>{signal.question}</td>
                    <td>{signal.side}</td>
                    <td>{fmtPrice(signal.marketPrice)}</td>
                    <td className={priceColor(signal.edge)}>{fmtPct(signal.edge)}</td>
                    <td>{fmtPct(signal.confidence)}</td>
                    <td className="plan-cell">
                      <div className="plan-cell-wrap">
                        <span className={`plan-pill plan-${signal.manualPlan?.status || 'wait'}`}>
                          {planStatusLabel(signal.manualPlan, text)}
                        </span>
                        <span>{compactManualSummary(signal.manualPlan, text)}</span>
                        {signal.marketUrl && (
                          <a href={signal.marketUrl} target="_blank" rel="noreferrer" className="market-link">
                            {text.scan.openMarket}
                          </a>
                        )}
                      </div>
                    </td>
                    <td>{fmtMoney(signal.volume || 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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

function StrategiesView({
  language,
  text,
  rows,
  loading,
  error,
  search,
  tier,
  selectedId,
  onSelect,
  onSearchChange,
  onTierChange,
  onRefresh,
}) {
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return rows.filter((row) => {
      const tierPass = tier === 'all' || row.tier === tier
      const textPass =
        needle === '' ||
        row.id.toLowerCase().includes(needle) ||
        row.titleEn.toLowerCase().includes(needle) ||
        row.titleKr.toLowerCase().includes(needle)
      return tierPass && textPass
    })
  }, [rows, search, tier])

  const selected = useMemo(() => {
    if (!selectedId) {
      return null
    }
    return filtered.find((row) => row.id === selectedId) || rows.find((row) => row.id === selectedId) || null
  }, [filtered, rows, selectedId])

  const [isDetailOpen, setIsDetailOpen] = useState(false)

  useEffect(() => {
    if (!isDetailOpen) {
      return undefined
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') {
        setIsDetailOpen(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isDetailOpen])

  function openDetail(strategyId) {
    onSelect(strategyId)
    setIsDetailOpen(true)
  }

  function closeDetail() {
    setIsDetailOpen(false)
  }

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
        <div className="control-action">
          <button type="button" onClick={onRefresh}>
            {text.refresh}
          </button>
        </div>
      </section>

      <section className="glass section full-span">
        <div className="section-head">
          <h3>{text.strategyRegistry}</h3>
          <span>
            {filtered.length} {text.rows}
          </span>
        </div>
        {loading && <p className="registry-note">{text.loading}</p>}
        {error && <p className="registry-note is-negative">{error}</p>}

        {!loading && !error && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{text.strategyCols.num}</th>
                  <th>{text.strategyCols.id}</th>
                  <th>{text.strategyCols.name}</th>
                  <th>{text.strategyCols.tier}</th>
                  <th>{text.strategyCols.status}</th>
                  <th>{text.strategyCols.data}</th>
                  <th>{text.strategyCols.path}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr
                    key={row.id}
                    className={row.id === selectedId ? 'strategy-row-selected' : 'strategy-row'}
                    onClick={() => openDetail(row.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        openDetail(row.id)
                      }
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    <td>{row.num}</td>
                    <td>{row.id}</td>
                    <td>{nameByLang(row, language)}</td>
                    <td>
                      <span className="pill">{row.tier}</span>
                    </td>
                    <td>
                      <span className={`status-badge ${row.isPlaceholder ? 'status-watch' : 'status-active'}`}>
                        {row.isPlaceholder ? text.strategyStates.placeholder : text.strategyStates.implemented}
                      </span>
                    </td>
                    <td>{row.requiredData.length > 0 ? row.requiredData.join(', ') : text.strategyDetail.none}</td>
                    <td>{row.path}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="registry-note detail-hint">{text.strategyDetail.hint}</p>
        <p className="registry-note">{text.allImplemented}</p>
      </section>

      {isDetailOpen && selected && (
        <div
          className="strategy-modal-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeDetail()
            }
          }}
        >
          <section className="strategy-modal glass" role="dialog" aria-modal="true" aria-labelledby="strategy-detail-title">
            <header className="strategy-modal-head">
              <div>
                <p className="eyebrow">{selected.id}</p>
                <h3 id="strategy-detail-title">{nameByLang(selected, language)}</h3>
                <p className="subtle">{text.strategyDetail.title}</p>
              </div>
              <button type="button" className="modal-close-btn" onClick={closeDetail}>
                {text.strategyDetail.close}
              </button>
            </header>

            <div className="strategy-modal-body">
              <div className="strategy-meta-grid">
                <div>
                  <p>ID</p>
                  <strong>{selected.id}</strong>
                </div>
                <div>
                  <p>{text.strategyDetail.name}</p>
                  <strong>{nameByLang(selected, language)}</strong>
                </div>
                <div>
                  <p>{text.strategyCols.tier}</p>
                  <strong>{selected.tier}</strong>
                </div>
                <div>
                  <p>{text.strategyCols.status}</p>
                  <strong>{selected.isPlaceholder ? text.strategyStates.placeholder : text.strategyStates.implemented}</strong>
                </div>
                <div>
                  <p>{text.strategyCols.data}</p>
                  <strong>{selected.requiredData.length > 0 ? selected.requiredData.join(', ') : text.strategyDetail.none}</strong>
                </div>
                <div>
                  <p>{text.strategyCols.path}</p>
                  <strong>{selected.path}</strong>
                </div>
              </div>

              <div className="strategy-text-block">
                <h4>{text.strategyDetail.overview}</h4>
                <p>{detailByLang(selected, language, 'overview') || text.strategyDetail.none}</p>
              </div>

              <div className="strategy-text-block">
                <h4>{text.strategyDetail.scanLogic}</h4>
                <p>{detailByLang(selected, language, 'scanLogic') || text.strategyDetail.none}</p>
              </div>

              <div className="strategy-text-block">
                <h4>{text.strategyDetail.analyzeLogic}</h4>
                <p>{detailByLang(selected, language, 'analyzeLogic') || text.strategyDetail.none}</p>
              </div>

              <div className="strategy-text-block">
                <h4>{text.strategyDetail.keyParams}</h4>
                {selected.keyParams && selected.keyParams.length > 0 ? (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>{text.strategyDetail.paramName}</th>
                          <th>{text.strategyDetail.paramValue}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selected.keyParams.map((item) => (
                          <tr key={`${selected.id}-${item.name}`}>
                            <td>{item.name}</td>
                            <td>{item.value}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p>{text.strategyDetail.none}</p>
                )}
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}

function MarketsView({ text, rows, loading, error, minVolume, minEdge, onMinVolume, onMinEdge, lastScan, onScan }) {
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
            max="500000"
            step="1000"
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
            min="0.0"
            max="0.4"
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
            {text.scan.last}: {lastScan ? lastScan.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-'}
          </span>
        </div>
      </section>

      {loading && <section className="glass section full-span"><p className="registry-note">{text.loading}</p></section>}
      {error && <section className="glass section full-span"><p className="registry-note is-negative">{error}</p></section>}

      {!loading && !error && rows.length === 0 && (
        <section className="glass section full-span empty-state">
          <h3>{text.scan.emptyTitle}</h3>
          <p>{text.scan.emptyBody}</p>
        </section>
      )}

      {!loading && !error && rows.map((market, index) => (
        <article key={`${market.marketId}-${market.strategy}-${index}`} className="glass section market-card">
          <div className="section-head">
            <div className="market-headline">
              <h3>{market.question}</h3>
              {market.marketUrl && (
                <a href={market.marketUrl} target="_blank" rel="noreferrer" className="market-link">
                  {text.scan.openMarket}
                </a>
              )}
            </div>
            <span>{market.category}</span>
          </div>
          <div className="market-grid">
            <div>
              <p>{text.scan.suggested}</p>
              <strong>{market.strategy}</strong>
            </div>
            <div>
              <p>{text.scan.volume}</p>
              <strong>{fmtMoney(market.volume || 0)}</strong>
            </div>
            <div>
              <p>{text.scan.side}</p>
              <strong>{market.side}</strong>
            </div>
            <div>
              <p>{text.scan.marketPrice}</p>
              <strong>{fmtPrice(market.marketPrice)}</strong>
            </div>
            <div>
              <p>{text.scan.edge}</p>
              <strong className={priceColor(market.edge)}>{fmtPct(market.edge)}</strong>
            </div>
            <div>
              <p>{text.scan.confidence}</p>
              <strong>{fmtPct(market.confidence)}</strong>
            </div>
            <div>
              <p>{text.scan.expires}</p>
              <strong>{market.endDateIso || '-'}</strong>
            </div>
          </div>
          {market.manualPlan && (
            <div className="manual-plan">
              <div className="manual-plan-head">
                <div>
                  <p>{text.scan.plan}</p>
                  <strong>{text.scan.manualOnly}</strong>
                </div>
                <span className={`plan-pill plan-${market.manualPlan.status || 'wait'}`}>
                  {planStatusLabel(market.manualPlan, text)}
                </span>
              </div>
              <div className="manual-grid">
                <div>
                  <p>{text.scan.trigger}</p>
                  <strong>YES &gt;= {fmtPrice(market.manualPlan.trigger_yes_price_gte)}</strong>
                  <span>NO &lt;= {fmtPrice(market.manualPlan.trigger_no_price_lte)}</span>
                </div>
                <div>
                  <p>{text.scan.limitPrice}</p>
                  <strong>NO &lt;= {fmtPrice(market.manualPlan.recommended_limit_no_price || market.manualPlan.suggested_limit_no_price)}</strong>
                  <span>
                    ask {fmtPrice(market.manualPlan.best_ask_no_price || market.manualPlan.reference_no_entry_price)}
                    {market.manualPlan.size ? ` · size ${fmtPrice(market.manualPlan.size)}` : ''}
                    {market.manualPlan.size_basis_bankroll_usd ? ` · basis ${fmtMoney(market.manualPlan.size_basis_bankroll_usd)}` : ''}
                  </span>
                </div>
                <div>
                  <p>{text.scan.maxChase}</p>
                  <strong>{fmtPrice(market.manualPlan.do_not_chase_above_no_price)}</strong>
                  <span>{market.manualPlan.quote_source === 'clob_orderbook' ? 'live orderbook' : 'market snapshot'}</span>
                </div>
                <div>
                  <p>{text.scan.takeProfit}</p>
                  <strong>{fmtPrice(market.manualPlan.take_profit_no_price_gte)}</strong>
                  <span>{text.scan.reviewBelow}: {fmtPrice(market.manualPlan.review_if_no_price_lte)}</span>
                </div>
              </div>
              <p className="manual-instruction">{market.manualPlan.instruction_kr}</p>
            </div>
          )}
        </article>
      ))}
    </div>
  )
}

function BacktestView({ text, strategyOptions, state, onStateChange, result, loading, error, onRun }) {
  return (
    <div className="view-grid">
      <section className="glass section full-span controls-row">
        <div className="control-group">
          <label htmlFor="bt-strategy">{text.backtest.strategy}</label>
          <select
            id="bt-strategy"
            value={state.strategy}
            onChange={(event) => onStateChange((prev) => ({ ...prev, strategy: event.target.value }))}
          >
            {strategyOptions.map((row) => (
              <option key={row.id} value={row.id}>{row.id}</option>
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
            value={state.initialBalance}
            onChange={(event) => onStateChange((prev) => ({ ...prev, initialBalance: Number(event.target.value) || 0 }))}
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
            value={state.slippagePercent}
            onChange={(event) => onStateChange((prev) => ({ ...prev, slippagePercent: Number(event.target.value) || 0 }))}
          />
        </div>
        <div className="control-action">
          <button type="button" onClick={onRun}>{text.backtest.run}</button>
        </div>
      </section>

      {loading && <section className="glass section full-span"><p className="registry-note">{text.loading}</p></section>}
      {error && <section className="glass section full-span"><p className="registry-note is-negative">{error}</p></section>}

      {!loading && !error && result && (
        <>
          <section className="metric-grid full-span">
            <article className="glass metric-card">
              <p>{text.backtest.endingBalance}</p>
              <strong>{fmtMoney(result.endingBalance)}</strong>
              <span className={priceColor(result.endingBalance - result.initialBalance)}>
                {fmtMoney((result.endingBalance || 0) - (result.initialBalance || 0))}
              </span>
            </article>
            <article className="glass metric-card">
              <p>{text.backtest.annualReturn}</p>
              <strong>{fmtPct(result.annualReturn)}</strong>
              <span className="is-positive">{text.backtest.riskAdjusted}</span>
            </article>
            <article className="glass metric-card">
              <p>{text.backtest.sharpe}</p>
              <strong>{Number(result.sharpe || 0).toFixed(2)}</strong>
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
            <GlassChart points={result.equity || []} />
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
                <strong>{state.slippagePercent.toFixed(1)}%</strong>
              </div>
              <div>
                <p>{text.backtest.pointsUsed}</p>
                <strong>{result.pointsUsed}</strong>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

function App() {
  const [language, setLanguage] = useState('en')
  const text = I18N[language]

  const [activeView, setActiveView] = useState('overview')

  const [overview, setOverview] = useState(null)
  const [overviewLoading, setOverviewLoading] = useState(false)
  const [overviewError, setOverviewError] = useState('')

  const [strategies, setStrategies] = useState([])
  const [strategiesLoading, setStrategiesLoading] = useState(false)
  const [strategiesError, setStrategiesError] = useState('')
  const [strategySearch, setStrategySearch] = useState('')
  const [tierFilter, setTierFilter] = useState('all')
  const [selectedStrategyId, setSelectedStrategyId] = useState('')

  const [opportunities, setOpportunities] = useState([])
  const [oppsLoading, setOppsLoading] = useState(false)
  const [oppsError, setOppsError] = useState('')
  const [minVolume, setMinVolume] = useState(5000)
  const [minEdge, setMinEdge] = useState(0.03)
  const [lastScan, setLastScan] = useState(null)

  const [backtestState, setBacktestState] = useState({
    strategy: 's03_nothing_ever_happens',
    initialBalance: 10000,
    slippagePercent: 0.5,
  })
  const [backtest, setBacktest] = useState(null)
  const [backtestLoading, setBacktestLoading] = useState(false)
  const [backtestError, setBacktestError] = useState('')

  useEffect(() => {
    void loadOverview()
    void loadStrategies()
    void loadOpportunities(minVolume, minEdge)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (strategies.length > 0 && !strategies.find((row) => row.id === backtestState.strategy)) {
      setBacktestState((prev) => ({ ...prev, strategy: strategies[0].id }))
    }
    if (strategies.length > 0 && !strategies.find((row) => row.id === selectedStrategyId)) {
      setSelectedStrategyId(strategies[0].id)
    }
  }, [strategies, backtestState.strategy, selectedStrategyId])

  async function loadOverview() {
    setOverviewLoading(true)
    setOverviewError('')
    try {
      const data = await fetchJson(`${API_BASE}/overview?max_markets=160`)
      setOverview(data)
    } catch (error) {
      setOverviewError(String(error.message || error))
    } finally {
      setOverviewLoading(false)
    }
  }

  async function loadStrategies() {
    setStrategiesLoading(true)
    setStrategiesError('')
    try {
      const data = await fetchJson(`${API_BASE}/strategies`)
      setStrategies(data.rows || [])
    } catch (error) {
      setStrategiesError(String(error.message || error))
    } finally {
      setStrategiesLoading(false)
    }
  }

  async function loadOpportunities(volume, edge) {
    setOppsLoading(true)
    setOppsError('')
    try {
      const query = new URLSearchParams({
        min_volume: String(volume),
        min_edge: String(edge),
        max_markets: '180',
        limit: '60',
      })
      const data = await fetchJson(`${API_BASE}/opportunities?${query.toString()}`)
      setOpportunities(data.rows || [])
      setLastScan(new Date())
    } catch (error) {
      setOppsError(String(error.message || error))
    } finally {
      setOppsLoading(false)
    }
  }

  async function runBacktest() {
    setBacktestLoading(true)
    setBacktestError('')
    try {
      const query = new URLSearchParams({
        strategy: backtestState.strategy,
        initial_balance: String(backtestState.initialBalance),
        slippage_pct: String(backtestState.slippagePercent),
        max_markets: '40',
      })
      const data = await fetchJson(`${API_BASE}/backtest?${query.toString()}`)
      setBacktest(data)
    } catch (error) {
      setBacktestError(String(error.message || error))
    } finally {
      setBacktestLoading(false)
    }
  }

  function renderView() {
    if (activeView === 'betting') {
      return <BettingView language={language} text={text} />
    }

    if (activeView === 'strategies') {
      return (
        <StrategiesView
          language={language}
          text={text}
          rows={strategies}
          loading={strategiesLoading}
          error={strategiesError}
          search={strategySearch}
          tier={tierFilter}
          selectedId={selectedStrategyId}
          onSelect={setSelectedStrategyId}
          onSearchChange={setStrategySearch}
          onTierChange={setTierFilter}
          onRefresh={() => void loadStrategies()}
        />
      )
    }

    if (activeView === 'markets') {
      return (
        <MarketsView
          text={text}
          rows={opportunities}
          loading={oppsLoading}
          error={oppsError}
          minVolume={minVolume}
          minEdge={minEdge}
          onMinVolume={setMinVolume}
          onMinEdge={setMinEdge}
          lastScan={lastScan}
          onScan={() => void loadOpportunities(minVolume, minEdge)}
        />
      )
    }

    if (activeView === 'backtest') {
      return (
        <BacktestView
          text={text}
          strategyOptions={strategies}
          state={backtestState}
          onStateChange={setBacktestState}
          result={backtest}
          loading={backtestLoading}
          error={backtestError}
          onRun={() => void runBacktest()}
        />
      )
    }

    return (
      <OverviewView
        text={text}
        data={overview}
        loading={overviewLoading}
        error={overviewError}
        onRefresh={() => void loadOverview()}
      />
    )
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
              <span>{text.signals}: {opportunities.length}</span>
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
