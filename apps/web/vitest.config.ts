import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

// Vitest configuration for the web app's unit/component tests.
// jsdom environment: the auth layer (storage, provider, login form)
// needs a browser-like DOM and localStorage; vitest runs them entirely
// in Node — no Next.js server, no real backend (fetch is mocked).
// The `@/` alias mirrors tsconfig.json paths.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.{ts,tsx}"],
    globals: true,
    setupFiles: ["tests/setup.ts"],
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
});
