// Sample data for the Launch pages in fake mode. Every value is SAMPLE: no real price (the
// plan text says "Sample"), no real user, no party or judge name.
import type { ConsentRow, EvalRun, HelpArticle, InventedRow, PlanOut, ReportRow, SpendRow } from "@/lib/api/types";

export const FAKE_PLANS: PlanOut[] = [
  { id: "free", name: "Sample Free", price_text: "Sample", current: true, limits: [{ label: "research answers a month", value: 5 }, { label: "uploads a month", value: 0 }] },
  { id: "student", name: "Sample Student", price_text: "Sample", current: false, limits: [{ label: "research answers a month", value: 40 }, { label: "uploads a month", value: 5 }] },
  { id: "pro", name: "Sample Pro", price_text: "Sample", current: false, limits: [{ label: "research answers a month", value: 150 }, { label: "uploads a month", value: 30 }] },
  { id: "chambers", name: "Sample Chambers", price_text: "Sample, per user, with a minimum number of users", current: false, limits: [{ label: "research answers a month per user", value: 150 }] },
];

export const FAKE_CONSENTS: ConsentRow[] = [
  { id: "consent-1", notice_version: "draft-0", purpose: "service", given_at: "2026-10-30T09:00:00Z", withdrawn_at: null },
];

export const FAKE_REPORTS: ReportRow[] = [
  { id: "rep-1", message_id: "fake-msg-9", reason: "citation", comment: "The citation does not match the sentence.", status: "new", created_at: "2026-11-01T10:00:00Z" },
  { id: "rep-2", message_id: "fake-msg-12", reason: "answer", comment: null, status: "in_review", created_at: "2026-10-31T16:20:00Z" },
  { id: "rep-3", message_id: "fake-msg-15", reason: "other", comment: "A very long comment that keeps going to see how the queue handles it: " + "the answer did not address the question that was asked. ".repeat(6), status: "new", created_at: "2026-10-31T11:05:00Z" },
];

export const FAKE_INVENTED: InventedRow[] = [
  { id: "inv-1", at: "2026-11-01T10:02:00Z", reason: "not retrieved", cited_text: "Sample v. Other Sample (2019) 4 SCC 100 was not one of the passages retrieved for this question." },
  { id: "inv-2", at: "2026-11-01T09:40:00Z", reason: "quote not found", cited_text: "\"A quotation that does not appear in the record.\"" },
  { id: "inv-3", at: "2026-10-31T15:12:00Z", reason: "claim not supported", cited_text: "The passage cited does not support the sentence it was attached to." },
];

export const FAKE_SPEND: SpendRow[] = [
  { day: "2026-11-02", answers: 41, helper_calls: 77, tokens_in: 214000, tokens_out: 52000, estimated_cost: null, cost_per_answer: null },
  { day: "2026-11-01", answers: 38, helper_calls: 64, tokens_in: 190000, tokens_out: 47000, estimated_cost: null, cost_per_answer: null },
];

export const FAKE_EVAL_TOTAL = 200;
export function fakeEvalAt(done: number): EvalRun {
  const passed = Math.floor(done * 0.96);
  return {
    id: "run-1",
    status: done >= FAKE_EVAL_TOTAL ? "done" : "running",
    total: FAKE_EVAL_TOTAL,
    done,
    passed,
    failures: Array.from({ length: Math.min(done - passed, 8) }, (_, i) => ({
      id: `q-${100 + i}`,
      kind: i % 2 ? "trap" : "real",
      detail: i % 2 ? "A citation that was not retrieved was kept." : "Expected a refusal; got an answer.",
    })),
  };
}

// Interface-only sample articles. They say nothing about the law.
export const FAKE_HELP: HelpArticle[] = [
  { slug: "ask-a-question", title: "Sample: asking a question", body: ["Sample article. Type your question in plain words and press Ask.", "Sample article. Each source in an answer has its own mark. Click a source to open it beside the answer."] },
  { slug: "matters", title: "Sample: keeping work in a matter", body: ["Sample article. A matter keeps related conversations together. Create one, then file a conversation under it."] },
  { slug: "share-a-link", title: "Sample: sharing an answer", body: ["Sample article. Use Share under a saved answer to make a link. You can switch a link off later under Shared links."] },
];

// Mutable copies the fake client edits (withdraw a consent, mark a report). `resetLaunchDb`
// gives tests a clean set.
export const launchDb = {
  consents: structuredClone(FAKE_CONSENTS),
  reports: structuredClone(FAKE_REPORTS),
  evalDone: -1, // -1 = no run yet
};
export function resetLaunchDb() {
  launchDb.consents = structuredClone(FAKE_CONSENTS);
  launchDb.reports = structuredClone(FAKE_REPORTS);
  launchDb.evalDone = -1;
}
