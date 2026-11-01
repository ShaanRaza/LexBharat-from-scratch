// Guards for the design and privacy rules, so the whole CLASS of mistake fails a test.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const SRC = join(__dirname, "..");
function files(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? files(p) : [p];
  });
}
const code = files(SRC).filter((f) => /\.(tsx?|css)$/.test(f) && !f.includes("__tests__"));
const notTokens = code.filter((f) => !f.endsWith("design/tokens.css"));

describe("design tokens", () => {
  it("no hard-coded colour, inline style or arbitrary size outside tokens.css", () => {
    const bad: string[] = [];
    for (const f of notTokens.filter((f) => !f.endsWith("fake/data.ts"))) {
      const t = readFileSync(f, "utf8");
      if (/#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|style=\{|\b(bg|text|border)-\[|\b(p|m|w|h|gap)-\[/.test(t)) bad.push(f);
    }
    expect(bad).toEqual([]);
  });
  it("no font family named outside design/", () => {
    const bad = notTokens.filter((f) => !f.includes("/design/") && /font-family:(?!\s*var\()|next\/font/.test(readFileSync(f, "utf8")));
    expect(bad).toEqual([]);
  });
  it("no default Tailwind palette colours", () => {
    const bad = notTokens.filter((f) =>
      /\b(bg|text|border)-(white|black|slate|gray|zinc|red|green|blue|orange|amber|yellow|emerald)(-\d+)?\b/.test(readFileSync(f, "utf8")),
    );
    expect(bad).toEqual([]);
  });
});

describe("hard rules", () => {
  it("no product or collection name is hard-coded (read from config)", () => {
    const bad = code.filter((f) => /kanoon|lexbharat/i.test(readFileSync(f, "utf8")) && !f.endsWith("design/tokens.css"));
    expect(bad).toEqual([]);
  });
  it("only lib/api/client.ts calls fetch", () => {
    const bad = code.filter((f) => !f.endsWith("api/client.ts") && /\bfetch\(/.test(readFileSync(f, "utf8")));
    expect(bad).toEqual([]);
  });
  it("only the client and the fake data import lib/fake", () => {
    const bad = code.filter((f) => !f.endsWith("api/client.ts") && !f.includes("lib/fake/") && /from ["']@\/lib\/fake/.test(readFileSync(f, "utf8")));
    expect(bad).toEqual([]);
  });
  it("no import reaches into api/ or core/", () => {
    const bad = code.filter((f) => /from ["'](\.\.\/)+(api|core|adapters)\//.test(readFileSync(f, "utf8")));
    expect(bad).toEqual([]);
  });
  it("no judge, bench or party fields in the API types", () => {
    const t = readFileSync(join(SRC, "lib/api/types.ts"), "utf8").split("\n").filter((l) => !l.trim().startsWith("//")).join("\n");
    expect(t).not.toMatch(/judge|bench|petitioner|respondent|appellant|advocate/i);
  });
});
