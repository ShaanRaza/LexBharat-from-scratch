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
