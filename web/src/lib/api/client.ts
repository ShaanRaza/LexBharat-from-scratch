// The ONLY file in web/ that talks to the backend (CLAUDE.md section 2 rule 3).
// Fake mode (NEXT_PUBLIC_USE_FAKE_API=true, the default) returns canned data.
import { API_BASE_URL, FAKE_STEP_DELAY_MS, USE_FAKE_API } from "@/lib/config";
import { fakeAnswerFor, FAKE_ANSWER_TEXT, FAKE_CASES, FAKE_CITATIONS, FAKE_COVERAGE, FAKE_ME, FAKE_PROVENANCE, FAKE_SECTIONS, FAKE_STATS, FAKE_STATS_EMPTY } from "@/lib/fake/data";
import { fakeConversationDetail, fakeDb, fakeRecordTurn, fakeStoredAnswer, fakeVariant, nextId, persistFakeDb, withCounts } from "@/lib/fake/store";
import { createSseParser } from "./sse";
import type { ApiErrorBody, CaseOut, ShareCreated, ShareLink, SharedAnswerOut, ConsentIn, ConversationDetail, ConversationOut, CoverageOut, FollowupsOut, HistoryHit, MatterDeleteMode, MatterDeleted, MatterDetail, MatterKind, MatterOut, MatterStatus, ImproveOut, MeOut, SectionOut, StatsOut, StepEventData, StreamEvent } from "./types";

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
    const c = FAKE_CASES[id];
    if (c) return c;
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

export async function getStats(variant?: string): Promise<StatsOut> {
  if (USE_FAKE_API) return variant === "empty" ? FAKE_STATS_EMPTY : FAKE_STATS;
  return getJson("/stats");
}

// What the dataset covers (public). The sentence and the lists come from the API.
export async function getCoverage(): Promise<CoverageOut> {
  if (USE_FAKE_API) return FAKE_COVERAGE;
  return getJson("/coverage");
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

export async function createConversation(matterId: string | null = null): Promise<string> {
  if (USE_FAKE_API) {
    const id = nextId("fake-conv");
    const now = new Date().toISOString();
    fakeDb.conversations.unshift({ id, module: "research", title: null, message_count: 0, matter_id: matterId, created_at: now, updated_at: now });
    persistFakeDb();
    return id;
  }
  const res = await fetch(`${BASE}/conversations`, { method: "POST", headers: await headers(), body: JSON.stringify({ module: "research", matter_id: matterId }) });
  if (!res.ok) throw await failure(res);
  return (await res.json()).id as string;
}

// Streams one answer as typed events. Order on the wire: token*, citations once, done.
export async function* askQuestion(conversationId: string, content: string): AsyncGenerator<StreamEvent> {
  if (USE_FAKE_API) {
    const assistantId = fakeRecordTurn(conversationId, content);
    yield* fakeStream(content, assistantId);
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

async function* fakeStream(q: string, assistantId: string | null = null): AsyncGenerator<StreamEvent> {
  const rid = "fake-request";
  const lower = q.toLowerCase();
  const err = (code: ApiErrorBody["code"]): StreamEvent => ({ event: "error", data: { code, message: code, request_id: rid } });
  if (lower.includes("limit")) return yield err("quota_exceeded");
  if (lower.includes("highcourt")) return yield err("out_of_scope");
  if (lower.includes("nothing")) return yield err("not_found_in_dataset");
  if (lower.includes("notheld")) {
    // A source the dataset does not hold: a refusal with its own message key (O7).
    return yield {
      event: "done",
      data: { message_id: null, from_cache: false, refused: true, reason: "out_of_scope", message_key: "out_of_scope:not_in_dataset" },
    };
  }
  if (lower.includes("fail")) return yield err("service_unavailable");
  for (const ev of FAKE_STEPS) {
    yield { event: "step", data: ev };
    await pause(FAKE_STEP_DELAY_MS);
  }
  const variant = fakeAnswerFor(q);
  for (const word of variant.text.split(/(?<=\s)/)) yield { event: "token", data: { text: word } };
  yield {
    event: "citations",
    data: { citations: variant.citations, removed_count: variant.removed, data_as_of: FAKE_PROVENANCE.data_as_of, credit: FAKE_PROVENANCE.credit, notice: FAKE_PROVENANCE.notice },
  };
  const shaped = lower.includes("upload");
  yield { event: "done", data: { message_id: shaped ? FAKE_SHAPED_MESSAGE_ID : (assistantId ?? nextId("fake-msg")), from_cache: false, refused: false } };
}

// ---- Matters and history (PRD-v2 O11, section 4.2) ----------------------------------
async function sendJson<T>(method: "PATCH" | "DELETE", path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method, headers: await headers(), body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) throw await failure(res);
  return res.json() as Promise<T>;
}
// A fake answer the server would refuse to share (shaped by an upload).
export const FAKE_SHAPED_MESSAGE_ID = "fake-shaped-msg";
const notFound = () => new ApiError({ code: "not_found", message: "Not found", request_id: "fake" }, 404);

export async function listMatters(status: MatterStatus | "all" = "active"): Promise<MatterOut[]> {
  if (USE_FAKE_API) {
    if (fakeVariant() === "empty") return [];
    return fakeDb.matters.filter((m) => status === "all" || m.status === status).map(withCounts);
  }
  return (await getJson<{ items: MatterOut[] }>(`/matters?status=${status}`)).items;
}

export async function createMatter(title: string, kind: MatterKind): Promise<MatterOut> {
  if (USE_FAKE_API) {
    const now = new Date().toISOString();
    const m: MatterOut = { id: nextId("fake-matter"), title: title.trim(), kind, status: "active", archived_at: null, created_at: now, updated_at: now, conversation_count: 0, document_count: 0 };
    fakeDb.matters.unshift(m);
    persistFakeDb();
    return m;
  }
  return postJson<MatterOut>("/matters", { title, kind });
}

export async function getMatter(id: string): Promise<MatterDetail> {
  if (USE_FAKE_API) {
    const m = fakeDb.matters.find((x) => x.id === id);
    if (!m) throw notFound();
    return { ...withCounts(m), conversations: fakeDb.conversations.filter((c) => c.matter_id === id) };
  }
  return getJson<MatterDetail>(`/matters/${encodeURIComponent(id)}`);
}

export async function updateMatter(id: string, change: { title?: string; status?: MatterStatus }): Promise<MatterOut> {
  if (USE_FAKE_API) {
    const m = fakeDb.matters.find((x) => x.id === id);
    if (!m) throw notFound();
    if (change.title !== undefined) m.title = change.title.trim();
    if (change.status !== undefined) {
      m.archived_at = change.status === "archived" ? new Date().toISOString() : null;
      m.status = change.status;
    }
    persistFakeDb();
    return withCounts(m);
  }
  return sendJson<MatterOut>("PATCH", `/matters/${encodeURIComponent(id)}`, change);
}

// `mode` has no default on purpose: the user is asked which one they mean.
export async function deleteMatter(id: string, mode: MatterDeleteMode): Promise<MatterDeleted> {
  if (USE_FAKE_API) {
    if (!fakeDb.matters.some((m) => m.id === id)) throw notFound();
    let conversations_deleted = 0;
    if (mode === "everything") {
      const gone = fakeDb.conversations.filter((c) => c.matter_id === id);
      conversations_deleted = gone.length;
      fakeDb.conversations = fakeDb.conversations.filter((c) => c.matter_id !== id);
      gone.forEach((c) => delete fakeDb.messages[c.id]);
    } else {
      fakeDb.conversations.forEach((c) => c.matter_id === id && (c.matter_id = null));
    }
    fakeDb.matters = fakeDb.matters.filter((m) => m.id !== id);
    persistFakeDb();
    return { mode, documents_deleted: 0, conversations_deleted };
  }
  return sendJson<MatterDeleted>("DELETE", `/matters/${encodeURIComponent(id)}?mode=${mode}`);
}

export async function moveConversation(conversationId: string, matterId: string | null): Promise<ConversationOut> {
  if (USE_FAKE_API) {
    const c = fakeDb.conversations.find((x) => x.id === conversationId);
    if (!c || (matterId && !fakeDb.matters.some((m) => m.id === matterId))) throw notFound();
    c.matter_id = matterId;
    persistFakeDb();
    return c;
  }
  return sendJson<ConversationOut>("PATCH", `/conversations/${encodeURIComponent(conversationId)}`, { matter_id: matterId });
}

export async function listConversations(): Promise<ConversationOut[]> {
  if (USE_FAKE_API) return fakeVariant() === "empty" ? [] : fakeDb.conversations.filter((c) => c.message_count > 0);
  return (await getJson<{ items: ConversationOut[] }>("/conversations?limit=50")).items;
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  if (USE_FAKE_API) {
    const c = fakeConversationDetail(id);
    if (!c) throw notFound();
    return c;
  }
  return getJson<ConversationDetail>(`/conversations/${encodeURIComponent(id)}`);
}

// Search the user's OWN saved work. The server filters on the user; the browser sends
// only the words.
export async function searchHistory(q: string): Promise<HistoryHit[]> {
  if (USE_FAKE_API) {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    const hits: HistoryHit[] = [];
    for (const c of fakeDb.conversations) {
      for (const m of fakeDb.messages[c.id] ?? []) {
        if (words.length && words.every((w) => m.content.toLowerCase().includes(w))) {
          hits.push({ kind: "message", conversation_id: c.id, message_id: m.id, matter_id: c.matter_id, title: c.title, snippet: m.content.slice(0, 160), created_at: m.created_at });
        }
      }
    }
    return hits;
  }
  return (await getJson<{ items: HistoryHit[] }>(`/history/search?q=${encodeURIComponent(q)}`)).items;
}

// ---- Share a saved answer by link (O14) ---------------------------------------------
// Only an answer built purely from the public dataset can be shared: the server refuses
// (403, with the reason) when an upload or a saved matter fact shaped it.
export async function shareMessage(messageId: string): Promise<ShareCreated> {
  if (USE_FAKE_API) {
    if (messageId === FAKE_SHAPED_MESSAGE_ID) {
      throw new ApiError({ code: "forbidden", message: "This answer used your uploaded document, so it cannot be shared.", request_id: "fake" }, 403);
    }
    const token = `fake-token-${nextId("t")}-${"x".repeat(30)}`;
    const now = new Date();
    const expires = new Date(now.getTime() + 30 * 86400_000).toISOString();
    const row = { id: nextId("fake-share"), message_id: messageId, token, created_at: now.toISOString(), expires_at: expires, revoked_at: null };
    fakeDb.shares.unshift(row);
    persistFakeDb();
    return { id: row.id, token, path: `/s/${token}`, expires_at: expires };
  }
  return postJson<ShareCreated>(`/messages/${encodeURIComponent(messageId)}/share`, {});
}

export async function listShares(): Promise<ShareLink[]> {
  if (USE_FAKE_API) return fakeVariant() === "empty" ? [] : fakeDb.shares.map(({ token: _t, ...rest }) => rest); // eslint-disable-line @typescript-eslint/no-unused-vars
  return (await getJson<{ items: ShareLink[] }>("/share")).items;
}

export async function revokeShare(id: string): Promise<void> {
  if (USE_FAKE_API) {
    const r = fakeDb.shares.find((x) => x.id === id && !x.revoked_at);
    if (!r) throw notFound();
    r.revoked_at = new Date().toISOString();
    persistFakeDb();
    return;
  }
  await sendJson<{ ok: boolean }>("DELETE", `/share/${encodeURIComponent(id)}`);
}

// The PUBLIC read. Never cached: a revoked link must be gone on the very next request.
export async function getShared(token: string): Promise<SharedAnswerOut> {
  if (USE_FAKE_API) {
    const r = fakeDb.shares.find((x) => x.token === token);
    if (!r || r.revoked_at || new Date(r.expires_at) < new Date()) throw notFound();
    const stored = fakeStoredAnswer(r.message_id);
    return {
      question: stored?.question ?? "What is bail?",
      text: stored?.answer.content ?? FAKE_ANSWER_TEXT,
      citations: stored?.answer.citations ?? FAKE_CITATIONS,
      expires_at: r.expires_at,
      provenance: FAKE_PROVENANCE,
    };
  }
  const res = await fetch(`${BASE}/s/${encodeURIComponent(token)}`, { cache: "no-store" });
  if (!res.ok) throw await failure(res);
  return res.json() as Promise<SharedAnswerOut>;
}
