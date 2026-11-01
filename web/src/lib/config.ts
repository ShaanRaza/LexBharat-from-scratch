// All web settings in one place (rule 2: settings live in config, not code).
// NEXT_PUBLIC_* values are read at build time and can be seen by the browser,
// so never put a secret here.

export const config = {
  // 1 / "true" = use the built-in sample data (no backend needed).
  useFakeApi:
    process.env.NEXT_PUBLIC_USE_FAKE_API === "1" ||
    process.env.NEXT_PUBLIC_USE_FAKE_API === "true",
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  // The product name is a placeholder pending a trademark search.
  productName: process.env.NEXT_PUBLIC_PRODUCT_NAME || "Legal research",
  dataSnapshot: process.env.NEXT_PUBLIC_DATA_SNAPSHOT || "v2026.08",
} as const;
