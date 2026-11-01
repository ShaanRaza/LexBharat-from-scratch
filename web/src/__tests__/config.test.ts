describe("fake mode guard", () => {
  afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });
  it("defaults to off when unset", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_FAKE_API", "");
    vi.resetModules();
    expect((await import("@/lib/config")).USE_FAKE_API).toBe(false);
  });
  it("refuses to start in production with fake mode on", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_FAKE_API", "true");
    vi.stubEnv("NODE_ENV", "production");
    vi.resetModules();
    await expect(import("@/lib/config")).rejects.toThrow(/production/);
  });
});

describe("product name comes from config", () => {
  afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });
  it("uses NEXT_PUBLIC_PRODUCT_NAME when set", async () => {
    vi.stubEnv("NEXT_PUBLIC_PRODUCT_NAME", "LexBharat");
    vi.resetModules();
    expect((await import("@/lib/config")).PRODUCT_NAME).toBe("LexBharat");
  });
  it("falls back to a neutral word, never a brand", async () => {
    vi.stubEnv("NEXT_PUBLIC_PRODUCT_NAME", undefined as unknown as string);
    delete process.env.NEXT_PUBLIC_PRODUCT_NAME;
    vi.resetModules();
    expect((await import("@/lib/config")).PRODUCT_NAME).toBe("Legal research");
  });
});
