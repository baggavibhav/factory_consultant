import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The production build is written into the Python package so `fca serve`
// can host it without Node.js installed.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/fca/web",
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
