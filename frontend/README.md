# Frontend — React + Vite + TS on Catalyst Slate

SPA for the four pillars: geospatial hotspots (MapLibre), network/link analysis (Cytoscape),
predictive & anomaly (Recharts), and natural-language query.

## Local dev

```powershell
npm install
npm run dev        # http://localhost:5173  (proxies /api + /health to backend :9000)
npm run typecheck  # tsc --noEmit
npm run build      # tsc + vite build -> dist/
```

The backend must be running on :9000 (see `../backend/README.md`) and the synthetic
dataset generated (see `../data/generator`).

## Deploy to Slate

```powershell
npm run build
catalyst deploy        # Slate serves dist/ ; or connect the Git repo for auto-deploy
```

Maps use free OpenStreetMap raster tiles (no key, no Catalyst map service — none exists).
For production-grade vector tiles, swap `OSM_STYLE` in `src/pages/Hotspots.tsx` for a styled source.
