// Settings read from environment variables (CLAUDE.md section 1: never hard-code the
// product name). NEXT_PUBLIC_* values are baked in at build time.
export const PRODUCT_NAME = process.env.NEXT_PUBLIC_PRODUCT_NAME ?? "Legal research";

// "Fake mode": no backend is called; the client returns canned data from lib/fake.
export const USE_FAKE_API = (process.env.NEXT_PUBLIC_USE_FAKE_API ?? "true") === "true";
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

// Frozen snapshot label (CLAUDE.md section 1). Shown on every page.
export const DATA_AS_OF = process.env.NEXT_PUBLIC_DATA_AS_OF ?? "v2026.08";
