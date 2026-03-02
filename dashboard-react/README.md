# Polymarket React Dashboard

React.js dashboard with a liquid-glass visual style for:
- Overview
- Strategy monitor
- Market scanner
- Backtest lab

## Run

```bash
cd dashboard-react
npm install
npm run dev
```

Open the local URL printed by Vite (usually `http://localhost:5173`).

## Quality checks

```bash
npm run lint
npm run build
```

## Notes

- The UI is fully responsive for desktop and mobile.
- Data is currently provided via `src/data/mockData.js` so the app runs without backend wiring.
- You can connect real API calls by swapping mock data access for fetch requests in the view components.
