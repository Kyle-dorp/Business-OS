import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Kept separate from vite.config.js on purpose. The build config is what ships;
// this one only ever runs under `npm test`, so nothing here can change what a
// customer downloads.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.js"],
    restoreMocks: true,
    include: ["src/**/*.test.{js,jsx}"],
  },
});
