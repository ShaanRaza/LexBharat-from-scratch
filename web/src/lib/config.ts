// Settings read from environment variables (CLAUDE.md section 1: never hard-code the
// product name). NEXT_PUBLIC_* values are baked in at build time.
export const PRODUCT_NAME = process.env.NEXT_PUBLIC_PRODUCT_NAME ?? "Legal research";

// "Fake mode": no backend is called; the client returns canned data from lib/fake.
// Fails closed: off unless explicitly turned on, and never allowed in production, so a
// missing setting can never serve canned answers with ticks.
export const USE_FAKE_API = process.env.NEXT_PUBLIC_USE_FAKE_API === "true";
if (USE_FAKE_API && process.env.NODE_ENV === "production") {
  throw new Error("NEXT_PUBLIC_USE_FAKE_API must not be true in production");
}
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

// Frozen snapshot label (CLAUDE.md section 1). Shown on every page.
export const DATA_AS_OF = process.env.NEXT_PUBLIC_DATA_AS_OF ?? "v2026.08";
