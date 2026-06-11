export const NAV_ITEMS = [
  { id: 'overview', label: 'Overview' },
  { id: 'sources', label: 'Data Sources' },
  { id: 'strategies', label: 'Strategies' },
  { id: 'markets', label: 'Markets' },
  { id: 'backtest', label: 'Backtest' },
]

export const DATA_SOURCES = [
  {
    id: 'polymarket',
    nameEn: 'Polymarket',
    nameKr: 'Polymarket (폴리마켓)',
    url: 'https://polymarket.com',
    regionEn: 'Primary public market-data source for this project.',
    regionKr: '이 프로젝트의 핵심 공개 시장 데이터 소스입니다.',
    notesEn: 'Used for market metadata, prices, volume, liquidity, and historical analysis.',
    notesKr: '시장 메타데이터, 가격, 거래량, 유동성, 히스토리 분석에 사용됩니다.',
  },
  {
    id: 'kalshi',
    nameEn: 'Kalshi',
    nameKr: 'Kalshi (칼시)',
    url: 'https://kalshi.com',
    regionEn: 'Reference source for cross-platform prediction-market comparison.',
    regionKr: '미국 규제 기반 예측시장으로, 크로스 플랫폼 가격 비교에 유용합니다.',
    notesEn: 'Used for settlement-rule checks and cross-platform price comparison research.',
    notesKr: '정산 규칙 검증 및 크로스 플랫폼 차익 감시에 유용합니다.',
  },
]

export const RESEARCH_STEPS = {
  en: [
    'Pick a market and read the resolution rules first.',
    'Compare market price with the strategy probability estimate.',
    'Check volume, liquidity, data freshness, and resolution-source risk.',
    'Log the thesis, invalidation condition, and observed outcome.',
  ],
  kr: [
    '먼저 시장의 정산 규칙을 읽고 이해합니다.',
    '시장 가격과 전략의 확률 추정치를 비교합니다.',
    '거래량, 유동성, 데이터 최신성, 정산 소스 리스크를 확인합니다.',
    '논리, 무효화 조건, 실제 결과를 기록합니다.',
  ],
}

export const TIER_OPTIONS = ['all', 'S', 'A', 'B', 'C']
