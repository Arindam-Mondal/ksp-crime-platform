import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local dev proxies API calls to the FastAPI backend on :9000.
// Catalyst Web Client Hosting serves the SPA under the "/app/" path, so assets must be
// referenced relative to that base (otherwise /assets/* 404s → blank screen).
export default defineConfig({
  base: "/app/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:9000",
      "/health": "http://localhost:9000",
    },
  },
});
