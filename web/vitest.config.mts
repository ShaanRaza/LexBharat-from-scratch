import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Unit tests for the trust logic (ticks) and the chat hook.
export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    env: { NEXT_PUBLIC_USE_FAKE_API: "1" },
  },
});
