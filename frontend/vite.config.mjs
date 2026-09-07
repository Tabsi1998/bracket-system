import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(rootDir, "src") },
  },
  server: {
    host: "0.0.0.0",
    port: 3000,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.VITE_DEV_BACKEND_URL || "http://127.0.0.1:8001",
        changeOrigin: true,
        ws: true,
      },
    },
  },
  preview: { host: "0.0.0.0", port: 3000, strictPort: true },
  build: {
    sourcemap: false,
    target: "es2022",
    rollupOptions: {
      output: {
        manualChunks(id) {
          const modulePath = id.replaceAll("\\", "/");
          if (!modulePath.includes("/node_modules/")) return undefined;
          if (modulePath.includes("/@tiptap/") || modulePath.includes("/prosemirror-")) return "editor";
          if (modulePath.includes("/recharts/") || modulePath.includes("/d3-")) return "charts";
          if (modulePath.includes("/@radix-ui/")) return "ui-radix";
          if (/\/node_modules\/(react|react-dom|scheduler)\//.test(modulePath)) return "react-core";
          return undefined;
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    clearMocks: true,
    restoreMocks: true,
    include: ["src/**/*.{test,spec}.{js,jsx,ts,tsx}"],
    coverage: { reporter: ["text", "lcov"] },
  },
});
