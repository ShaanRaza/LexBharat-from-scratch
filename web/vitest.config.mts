import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: { tsconfigPaths: true },
  test: { env: { NEXT_PUBLIC_USE_FAKE_API: "true", NEXT_PUBLIC_FAKE_STEP_DELAY_MS: "0", NEXT_PUBLIC_FAKE_DB: "minimal" }, environment: "jsdom", setupFiles: ["./vitest.setup.ts"], globals: true },
});
