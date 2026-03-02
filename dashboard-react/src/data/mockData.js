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

export const TIER_OPTIONS = ['all', 'S', 'A', 'B', 'C']
