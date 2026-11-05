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
// Fake mode only: how long each progress step is shown, so the panel can be seen.
export const FAKE_STEP_DELAY_MS = Number(process.env.NEXT_PUBLIC_FAKE_STEP_DELAY_MS ?? 120);
// The pricing page is behind a switch (O10: pricing is the owner's call). Off by default.
export const FEATURE_PRICING = process.env.NEXT_PUBLIC_FEATURE_PRICING === "true";
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

// There is no date here on purpose: the data-as-of line describes the content a page shows,
// comes from the API (core/coverage.json), and is never the release name (A146).
