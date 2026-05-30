import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Local dev proxies API calls to the FastAPI backend on :9000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:9000",
      "/health": "http://localhost:9000",
    },
  },
});
