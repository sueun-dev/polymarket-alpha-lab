# Polymarket React Dashboard

React.js dashboard with a liquid-glass visual style for:
- Overview
- Strategy monitor
- Market scanner
- Backtest lab

## Run

```bash
# terminal 1: live API backend
cd ..
python3 dashboard_api.py --host 127.0.0.1 --port 8001

# terminal 2: React app (port 3001)
cd dashboard-react
npm install
npm run dev
```

Open `http://localhost:3001`.

## Quality checks

```bash
npm run lint
npm run build
```

## Notes

- The UI is fully responsive for desktop and mobile.
- Live endpoints are served by `/api/*` from `dashboard_api.py` and proxied by Vite.
- `src/data/mockData.js` now contains only static navigation/platform text, not market metrics.
