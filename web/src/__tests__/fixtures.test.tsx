import { render, screen } from "@testing-library/react";
import { resetFakeDb } from "@/lib/fake/store";
import { AnswerView } from "@/components/chat/AnswerView";
import { ActSection } from "@/components/records/ActSection";
import { Judgment } from "@/components/records/Judgment";
import { askQuestion, getCase, getSection, getStats } from "@/lib/api/client";
import { applyEvent, newAnswer } from "@/lib/chat/state";
import { ANSWER_EIGHT, CITATIONS_EIGHT, FAKE_SECTIONS } from "@/lib/fake/data";
import * as fixtures from "@/lib/fake/fixtures";
import type { StreamEvent } from "@/lib/api/types";

async function run(q: string): Promise<StreamEvent[]> {
  const out: StreamEvent[] = [];
  for await (const ev of askQuestion("c", q)) out.push(ev);
  return out;
}
async function answerFor(q: string) {
  let s = newAnswer(q);
  for (const ev of await run(q)) s = applyEvent(s, ev);
  return s;
}

describe("realistic fixtures (real law is not tidy)", () => {
  it("a judgment of 48 paragraphs, one very long, one with an unbroken address, one a single line", async () => {
    const c = await getCase(fixtures.LONG_CASE_ID);
    expect(c.paragraphs).toHaveLength(48);
    const len = (n: number) => c.paragraphs[n - 1].text.length;
    expect(len(7)).toBeGreaterThan(2000);
    expect(len(4)).toBeLessThan(140);
    expect(c.paragraphs[12].text.split(/\s+/).some((w) => w.length > 120)).toBe(true);
    expect(c.citation_string!.length).toBeGreaterThan(80);
  });

  it("an Act with a 200-character title, and a section with nested sub-clauses", async () => {
    const long = await getSection(fixtures.LONG_ACT.slug, "7");
    expect(long.act_name.length).toBeGreaterThanOrEqual(200);
    const sub = await getSection(fixtures.SUBCLAUSE_ACT.slug, "12");
    for (const marker of ["(1)", "(a)", "(i)", "(A)", "(B)", "(2)"]) expect(sub.text).toContain(marker);
    expect(FAKE_SECTIONS.length).toBeGreaterThan(3);
  });

  it("eight citations, mixed marks, judgments and Acts", () => {
    expect(CITATIONS_EIGHT.map((c) => c.source_id)).toEqual(["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]);
    expect(new Set(CITATIONS_EIGHT.map((c) => c.status))).toEqual(new Set(["verified", "partly", "unchecked"]));
    expect(new Set(CITATIONS_EIGHT.map((c) => c.kind))).toEqual(new Set(["judgment", "act"]));
    for (const n of [1, 2, 3, 4, 5, 6, 7, 8]) expect(ANSWER_EIGHT).toContain(`[S${n}]`);
  });

  it("every record the eight citations point at can be opened", async () => {
    for (const c of CITATIONS_EIGHT) {
      if (c.kind === "judgment") await expect(getCase(c.record_id)).resolves.toBeTruthy();
      else await expect(getSection(c.act_slug!, c.section!)).resolves.toBeTruthy();
    }
  });

  it("the keyword 'eight' streams the 8-citation answer, with one citations event", async () => {
    const evs = await run("tell me eight things");
    expect(evs.filter((e) => e.event === "citations")).toHaveLength(1);
    const s = await answerFor("eight");
    expect(s.citations?.citations).toHaveLength(8);
    expect(s.text).toContain("[S8]");
  });

  it("the keyword 'removed' streams a result where the verifier removed a citation", async () => {
    const s = await answerFor("a removed one");
    expect(s.citations?.removed_count).toBe(1);
    expect(s.citations?.citations.map((c) => c.source_id)).toEqual(["S1", "S3"]);
    render(<AnswerView answer={s} />);
    expect(screen.getByText("One authority could not be verified and was removed.")).toBeInTheDocument();
  });

  it("empty and failure results", async () => {
    expect((await run("nothing"))[0]).toMatchObject({ event: "error", data: { code: "not_found_in_dataset" } });
    expect((await run("fail"))[0]).toMatchObject({ event: "error", data: { code: "service_unavailable" } });
    expect((await getStats("empty")).rows).toEqual([]);
  });

  it("the 8-citation answer still shows each tick with its words, the date, credit and notice", async () => {
    const s = await answerFor("eight");
    const { container } = render(<AnswerView answer={s} />);
    expect(container.querySelectorAll("li [data-mark]")).toHaveLength(8);
    expect(screen.getAllByText(/Record found in dataset \(data as of 2026-08-31\)/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Data as of 2026-08-31/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/CC BY 4.0/).length).toBeGreaterThan(0);
  });

  it("the reader renders the long judgment and the sub-clause section without losing text", async () => {
    const c = await getCase(fixtures.LONG_CASE_ID);
    const { container } = render(<Judgment c={c} highlight="p41" />);
    expect(container.querySelectorAll("p[id]")).toHaveLength(48);
    expect(container.querySelector('[data-cited="true"]')?.id).toBe("p41");
    const s = await getSection(fixtures.SUBCLAUSE_ACT.slug, "12");
    const r = render(<ActSection s={s} />);
    expect(r.container.textContent).toContain("(A) its governing document");
  });

  it("fixtures name no judge, party or advocate and carry no price", () => {
    const text = JSON.stringify([fixtures.LONG_CASE, fixtures.ANSWER_EIGHT, fixtures.CITATIONS_EIGHT, fixtures.CONVERSATION_TITLES]);
    expect(text).not.toMatch(/\b(judge|justice|bench|petitioner|respondent|appellant|advocate)\b/i);
    expect(text).not.toMatch(/₹|\brs\.?\s?\d/i);
  });
});

import { StatsView } from "@/components/records/StatsView";
import { MattersScreen } from "@/components/matters/MattersScreen";
import { HistoryScreen } from "@/components/matters/HistoryScreen";
import { CoverageView } from "@/components/records/CoverageView";
import { FAKE_COVERAGE, FAKE_STATS_EMPTY } from "@/lib/fake/data";
import { fakeDb } from "@/lib/fake/store";

describe("empty states are screens, not blank tables", () => {
  beforeEach(() => resetFakeDb());
  it("stats with no rows says so instead of an empty table", () => {
    const { container } = render(<StatsView stats={FAKE_STATS_EMPTY} />);
    expect(container.querySelector("table")).toBeNull();
    expect(screen.getByText("No outcome counts to show yet")).toBeInTheDocument();
    expect(screen.getAllByText(/CC BY 4.0/).length).toBeGreaterThan(0); // notices stay
  });
  it("no matters / no conversations", async () => {
    fakeDb.matters = [];
    render(<MattersScreen />);
    expect(await screen.findByText("You have no matters yet.")).toBeInTheDocument();
  });
  it("history with nothing saved offers a way to start", async () => {
    fakeDb.conversations = [];
    render(<HistoryScreen />);
    expect(await screen.findByText("No saved conversations yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ask a question" })).toHaveAttribute("href", "/");
  });
  it("coverage that lists nothing says so", () => {
    render(<CoverageView coverage={{ ...FAKE_COVERAGE, courts: [], instruments: [] }} />);
    expect(screen.getByText("Coverage has not been listed yet")).toBeInTheDocument();
  });
});
