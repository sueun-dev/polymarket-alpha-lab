export const NAV_ITEMS = [
  { id: 'overview', label: 'Overview' },
  { id: 'betting', label: 'Where to Bet' },
  { id: 'strategies', label: 'Strategies' },
  { id: 'markets', label: 'Markets' },
  { id: 'backtest', label: 'Backtest' },
]

export const BETTING_PLATFORMS = [
  {
    id: 'polymarket',
    nameEn: 'Polymarket',
    nameKr: 'Polymarket (폴리마켓)',
    url: 'https://polymarket.com',
    regionEn: 'Primary venue for this project. US access can be restricted by policy/jurisdiction.',
    regionKr: '이 프로젝트의 핵심 거래소. 미국 사용자는 정책/관할에 따라 접근 제한이 있을 수 있습니다.',
    notesEn: 'Best coverage for politics, macro, crypto, and event markets.',
    notesKr: '정치, 매크로, 크립토, 이벤트 시장 커버리지가 가장 넓습니다.',
  },
  {
    id: 'kalshi',
    nameEn: 'Kalshi',
    nameKr: 'Kalshi (칼시)',
    url: 'https://kalshi.com',
    regionEn: 'US-regulated prediction market, useful for cross-platform comparison.',
    regionKr: '미국 규제 기반 예측시장으로, 크로스 플랫폼 가격 비교에 유용합니다.',
    notesEn: 'Useful for settlement-rule checks and cross-platform arb monitoring.',
    notesKr: '정산 규칙 검증 및 크로스 플랫폼 차익 감시에 유용합니다.',
  },
]

export const BETTING_STEPS = {
  en: [
    'Pick your market and read resolution rules first.',
    'Decide YES or NO and place a small starter position.',
    'Only scale when edge, liquidity, and risk limits are clear.',
    'Track entry price, thesis, invalidation, and exit time in a log.',
  ],
  kr: [
    '먼저 시장의 정산 규칙을 읽고 이해합니다.',
    'YES 또는 NO를 선택하고 작은 금액으로 시작합니다.',
    '엣지, 유동성, 리스크 한도가 명확할 때만 비중을 늘립니다.',
    '진입가, 근거, 무효화 조건, 청산 시점을 로그에 기록합니다.',
  ],
}

export const OVERVIEW_METRICS = [
  { id: 'balance', label: 'Portfolio Value', value: 12482.47, delta: 3.42, format: 'currency' },
  { id: 'open_positions', label: 'Open Positions', value: 14, delta: 2, format: 'number' },
  { id: 'daily_pnl', label: "Today's P&L", value: 218.91, delta: 1.79, format: 'currency' },
  { id: 'active_strats', label: 'Active Strategies', value: 9, delta: 1, format: 'number' },
]

export const EQUITY_SERIES = [
  10000, 10040, 10065, 10022, 10115, 10180, 10240, 10310, 10265, 10355, 10430, 10520,
  10610, 10585, 10690, 10740, 10855, 10910, 10980, 11005, 11140, 11230, 11305, 11490,
  11580, 11625, 11720, 11870, 11940, 12055, 12140, 12220, 12310, 12482,
]

export const STRATEGY_ALLOCATION = [
  { label: 'S01 Reversing Stupidity', value: 24, color: '#4db6ff' },
  { label: 'S03 Nothing Ever Happens', value: 21, color: '#6be2c8' },
  { label: 'S10 Yes Bias', value: 18, color: '#8ed77f' },
  { label: 'S12 High Prob Harvest', value: 16, color: '#ffc76a' },
  { label: 'S39 Volume Momentum', value: 13, color: '#f8a3a0' },
  { label: 'Cash Buffer', value: 8, color: '#9eb4d6' },
]

export const RECENT_TRADES = [
  {
    id: 't-9001',
    time: '2026-03-01 14:31 ET',
    strategy: 's03_nothing_ever_happens',
    market: 'Will Russia invade another country in 2026?',
    side: 'BUY NO',
    price: 0.78,
    size: 210,
    pnl: 41.6,
  },
  {
    id: 't-9002',
    time: '2026-03-01 12:04 ET',
    strategy: 's12_high_prob_harvesting',
    market: 'Will the NYSE open on Monday March 2?',
    side: 'BUY YES',
    price: 0.96,
    size: 600,
    pnl: 18.2,
  },
  {
    id: 't-9003',
    time: '2026-03-01 09:42 ET',
    strategy: 's10_yes_bias',
    market: 'First ever BTC ETF inflow exceeds $1B in a day?',
    side: 'BUY NO',
    price: 0.44,
    size: 340,
    pnl: -9.6,
  },
  {
    id: 't-9004',
    time: '2026-02-28 23:16 ET',
    strategy: 's01_reversing_stupidity',
    market: 'MAGA rally attendance guaranteed to break record?',
    side: 'BUY NO',
    price: 0.27,
    size: 400,
    pnl: 31.1,
  },
]

export const MARKET_OPPORTUNITIES = [
  {
    id: 'm1',
    question: 'Will Trump be impeached by end of 2026?',
    category: 'politics',
    volume: 50210,
    yesPrice: 0.35,
    edge: 0.08,
    confidence: 0.65,
    strategy: 's03_nothing_ever_happens',
    expiresIn: '13h',
  },
  {
    id: 'm2',
    question: 'Will NYC temperature exceed 100F this July?',
    category: 'weather',
    volume: 3420,
    yesPrice: 0.08,
    edge: 0.11,
    confidence: 0.61,
    strategy: 's02_weather_noaa',
    expiresIn: '2d',
  },
  {
    id: 'm3',
    question: 'Will the S&P 500 crash by more than 20% in Q2?',
    category: 'finance',
    volume: 38770,
    yesPrice: 0.22,
    edge: 0.06,
    confidence: 0.6,
    strategy: 's01_reversing_stupidity',
    expiresIn: '8h',
  },
  {
    id: 'm4',
    question: 'Will Bitcoin reach $150k by end of 2026?',
    category: 'crypto',
    volume: 81200,
    yesPrice: 0.38,
    edge: 0.05,
    confidence: 0.55,
    strategy: 's39_volume_momentum',
    expiresIn: '5h',
  },
  {
    id: 'm5',
    question: 'Will the NYSE open on Monday March 2?',
    category: 'finance',
    volume: 6090,
    yesPrice: 0.96,
    edge: 0.02,
    confidence: 0.9,
    strategy: 's12_high_prob_harvesting',
    expiresIn: '17h',
  },
  {
    id: 'm6',
    question: 'Will there be a revolutionary AI breakthrough announcement in 2026?',
    category: 'tech',
    volume: 22110,
    yesPrice: 0.55,
    edge: 0.07,
    confidence: 0.58,
    strategy: 's10_yes_bias',
    expiresIn: '19h',
  },
]

export const TIER_OPTIONS = ['all', 'S', 'A', 'B', 'C']

export function buildBacktest(strategyId, initialBalance, slippagePct) {
  const baseProfiles = {
    s01_reversing_stupidity: { annual: 0.34, sharpe: 1.36, maxDd: 0.16, winRate: 0.62 },
    s03_nothing_ever_happens: { annual: 0.26, sharpe: 1.31, maxDd: 0.12, winRate: 0.64 },
    s10_yes_bias: { annual: 0.21, sharpe: 1.18, maxDd: 0.14, winRate: 0.6 },
    s12_high_prob_harvesting: { annual: 0.14, sharpe: 1.05, maxDd: 0.06, winRate: 0.74 },
    s39_volume_momentum: { annual: 0.19, sharpe: 1.02, maxDd: 0.2, winRate: 0.55 },
  }

  const profile = baseProfiles[strategyId] || {
    annual: 0.12,
    sharpe: 0.92,
    maxDd: 0.18,
    winRate: 0.53,
  }

  const slippagePenalty = slippagePct * 0.45
  const adjustedAnnual = Math.max(0.01, profile.annual - slippagePenalty)
  const adjustedSharpe = Math.max(0.2, profile.sharpe - slippagePct * 0.8)
  const endingBalance = initialBalance * (1 + adjustedAnnual)

  const points = []
  const months = 12
  for (let i = 0; i < months; i += 1) {
    const trend = initialBalance + ((endingBalance - initialBalance) / (months - 1)) * i
    const wobble = (Math.sin(i * 1.35) + Math.cos(i * 0.7)) * initialBalance * 0.008
    points.push(Math.max(initialBalance * 0.8, trend + wobble))
  }

  return {
    strategyId,
    initialBalance,
    endingBalance,
    annualReturn: adjustedAnnual,
    sharpe: adjustedSharpe,
    maxDrawdown: profile.maxDd + slippagePct * 0.12,
    winRate: profile.winRate,
    trades: Math.round(60 + adjustedAnnual * 150),
    equity: points,
  }
}
