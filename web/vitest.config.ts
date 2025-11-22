import { defineConfig } from "vitest/config"
import { fileURLToPath } from "url"
import path from "path"

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["tests/unit/**/*.test.{ts,tsx}", "tests/unit/**/*.spec.{ts,tsx}"],
    exclude: ["tests/e2e/**"],
    coverage: { reporter: ["text", "json", "html"] },
  },
})