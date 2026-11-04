import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Puerto fijo: Tauri conecta aquí en modo dev.
// Las variables globales compartidas viven en el .env RAÍZ del proyecto
// (BACKEND_URL/VITE_API_URL, firma Android, etc.).
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  envPrefix: ["VITE_", "TAURI_"],
  envDir: "..",
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    target: "es2021",
  },
  // vitest: entorno jsdom + globals (necesario para el auto-cleanup de Testing Library)
  test: {
    environment: "jsdom",
    globals: true,
  },
});
