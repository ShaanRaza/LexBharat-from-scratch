// The ONLY file in web/ that talks to the backend (CLAUDE.md section 2 rule 3).
// Fake mode (NEXT_PUBLIC_USE_FAKE_API=true, the default) returns canned data.
import { API_BASE_URL, FAKE_STEP_DELAY_MS, USE_FAKE_API } from "@/lib/config";
import { FAKE_ANSWER_TEXT, FAKE_CASE, FAKE_CITATIONS, FAKE_ME, FAKE_PROVENANCE, FAKE_SECTIONS, FAKE_STATS } from "@/lib/fake/data";
import { createSseParser } from "./sse";
import type { ApiErrorBody, CaseOut, ConsentIn, FollowupsOut, ImproveOut, MeOut, SectionOut, StatsOut, StepEventData, StreamEvent } from "./types";

const BASE = `${API_BASE_URL}/api/v1`;

export class ApiError extends Error {
  constructor(public body: ApiErrorBody, public status: number) {
    super(body.message);
  }
}

// Supplies the Firebase token once auth exists. Until then requests go without one.
let tokenProvider: () => Promise<string | null> = async () => null;
export function setTokenProvider(fn: () => Promise<string | null>) {
  tokenProvider = fn;
}

async function headers(): Promise<Record<string, string>> {
  const t = await tokenProvider();
  return { "Content-Type": "application/json", ...(t ? { Authorization: `Bearer ${t}` } : {}) };
}

async function failure(res: Response): Promise<ApiError> {
  try {
    const j = await res.json();
    if (j?.error) return new ApiError(j.error, res.status);
  } catch {}
  return new ApiError({ code: "internal_error", message: "Request failed", request_id: "" }, res.status);
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: await headers() });
  if (!res.ok) throw await failure(res);
  return res.json() as Promise<T>;
}

export async function getCase(id: string): Promise<CaseOut> {
  if (USE_FAKE_API) {
    if (id === FAKE_CASE.record_id) return FAKE_CASE;
    throw new ApiError({ code: "not_found", message: "Not found", request_id: "fake" }, 404);
  }
  return getJson(`/cases/${encodeURIComponent(id)}`);
}

export async function getSection(act: string, n: string): Promise<SectionOut> {
  if (USE_FAKE_API) {
    const s = FAKE_SECTIONS.find((x) => x.act_slug === act && x.section === n);
    if (s) return s;
    throw new ApiError({ code: "not_found", message: "Not found", request_id: "fake" }, 404);
  }
  return getJson(`/acts/${encodeURIComponent(act)}/sections/${encodeURIComponent(n)}`);
}

export async function getStats(): Promise<StatsOut> {
  if (USE_FAKE_API) return FAKE_STATS;
  return getJson("/stats");
}

export async function getMe(): Promise<MeOut> {
  if (USE_FAKE_API) return FAKE_ME;
  return getJson("/me");
}

// Fake mode only: sample sections so the Act lookup page has something to click.
// Returns nothing against the real API (there is no Acts index route in docs/API.md).
export function sampleSections(): { act_slug: string; act_name: string; section: string }[] {
  return USE_FAKE_API ? FAKE_SECTIONS.map(({ act_slug, act_name, section }) => ({ act_slug, act_name, section })) : [];
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "POST", headers: await headers(), body: JSON.stringify(body) });
  if (!res.ok) throw await failure(res);
  return res.json() as Promise<T>;
}

// Next questions for a saved answer. Questions only: the page runs one like any other.
export async function getFollowups(conversationId: string, messageId: string | null): Promise<string[]> {
  if (USE_FAKE_API) return FAKE_FOLLOWUPS;
  if (!messageId) return [];
  const out = await postJson<FollowupsOut>(`/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}/followups`, {});
  return out.suggestions;
}

// "Improve my question": editable text for the input box. Not an answer, never cited.
export async function improveQuestion(text: string): Promise<ImproveOut> {
  if (USE_FAKE_API) {
    const t = text.trim().replace(/[?.!\s]+$/, "");
    return { text: `Sample improved wording: what is the law on ${t.toLowerCase()}?`, changed: true };
  }
  return postJson<ImproveOut>("/prompts/improve", { text });
}

export async function postConsent(c: ConsentIn): Promise<void> {
  if (USE_FAKE_API) return;
  const res = await fetch(`${BASE}/me/consents`, { method: "POST", headers: await headers(), body: JSON.stringify(c) });
  if (!res.ok) throw await failure(res);
}

export async function createConversation(): Promise<string> {
  if (USE_FAKE_API) return "fake-conversation";
  const res = await fetch(`${BASE}/conversations`, { method: "POST", headers: await headers(), body: JSON.stringify({ module: "research" }) });
  if (!res.ok) throw await failure(res);
  return (await res.json()).id as string;
}

// Streams one answer as typed events. Order on the wire: token*, citations once, done.
export async function* askQuestion(conversationId: string, content: string): AsyncGenerator<StreamEvent> {
  if (USE_FAKE_API) {
    yield* fakeStream(content);
    return;
  }
  const res = await fetch(`${BASE}/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { ...(await headers()), Accept: "text/event-stream" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok || !res.body) {
    const e = await failure(res);
    yield { event: "error", data: e.body };
    return;
  }
  const parse = createSseParser();
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    for (const ev of parse(dec.decode(value, { stream: true }))) yield ev;
  }
}

// Fake mode: typing "limit", "nothing", "highcourt" or "fail" in the question
// triggers the failure screens so they can be seen without a backend.
const FAKE_FOLLOWUPS = [
  "What is the difference between bail and anticipatory bail?",
  "Which factors does a court weigh when deciding bail?",
];
const pause = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
const FAKE_STEPS: StepEventData[] = [
  { step: "understanding", found: null, kept: null },
  { step: "searching", found: null, kept: null },
  { step: "checking", found: 23, kept: null },
  { step: "writing", found: 23, kept: 8 },
  { step: "verifying", found: null, kept: null },
];

async function* fakeStream(q: string): AsyncGenerator<StreamEvent> {
  const rid = "fake-request";
  const lower = q.toLowerCase();
  const err = (code: ApiErrorBody["code"]): StreamEvent => ({ event: "error", data: { code, message: code, request_id: rid } });
  if (lower.includes("limit")) return yield err("quota_exceeded");
  if (lower.includes("highcourt")) return yield err("out_of_scope");
  if (lower.includes("nothing")) return yield err("not_found_in_dataset");
  if (lower.includes("fail")) return yield err("service_unavailable");
  for (const ev of FAKE_STEPS) {
    yield { event: "step", data: ev };
    await pause(FAKE_STEP_DELAY_MS);
  }
  for (const word of FAKE_ANSWER_TEXT.split(/(?<=\s)/)) yield { event: "token", data: { text: word } };
  yield {
    event: "citations",
    data: { citations: FAKE_CITATIONS, removed_count: 0, data_as_of: FAKE_PROVENANCE.data_as_of, credit: FAKE_PROVENANCE.credit, notice: FAKE_PROVENANCE.notice },
  };
  yield { event: "done", data: { message_id: null, from_cache: false, refused: false } };
}
