import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The browser always talks to its own origin; Vite proxies /api to the backend, so no CORS is
// needed in development (DDR-98). In the e2e container the backend is http://api:8000.
const apiTarget = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";
// `ws: true` forwards the realtime WebSocket (/api/v1/realtime, DDR-115 (6)) with the same Origin and cookie.
const proxy = { "/api": { target: apiTarget, changeOrigin: false, ws: true } };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { host: "127.0.0.1", port: 5173, strictPort: true, proxy },
  preview: { proxy },
  build: { sourcemap: true },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});
