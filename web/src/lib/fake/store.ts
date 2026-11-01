// Fake mode only: a small in-memory "database" for matters and conversations, so every
// matters screen can be clicked through with no backend. Labelled sample data. It lives
// only in the page's memory; `resetFakeDb()` gives tests a clean copy.
import type { ConversationDetail, ConversationOut, MatterOut, StoredMessage } from "@/lib/api/types";
import { FAKE_ANSWER_TEXT, FAKE_CITATIONS, FAKE_PROVENANCE, fakeAnswerFor } from "@/lib/fake/data";
import { CONVERSATION_TITLES, LONG_MATTER_TITLE } from "@/lib/fake/fixtures";

type Db = {
  matters: MatterOut[];
  conversations: ConversationOut[];
  messages: Record<string, StoredMessage[]>;
  seq: number;
  shares: { id: string; message_id: string; token: string; created_at: string; expires_at: string; revoked_at: string | null }[];
};

const NOW = "2026-11-02T10:00:00Z";

// Tests use the small database so they stay exact; the browser gets the realistic one.
const MINIMAL = process.env.NEXT_PUBLIC_FAKE_DB === "minimal";

/** `?fake=empty` on a page: show that page's empty state (fake mode, browser only). */
export function fakeVariant(): string | null {
  try {
    return typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("fake");
  } catch {
    return null;
  }
}

function seed(): Db {
  const matter: MatterOut = {
    id: "fake-matter-1", title: "Sample matter", kind: "matter", status: "active",
    archived_at: null, created_at: NOW, updated_at: NOW, conversation_count: 0, document_count: 0,
  };
  const conv = (id: string, title: string, matter_id: string | null): ConversationOut => ({
    id, module: "research", title, message_count: 2, matter_id, created_at: NOW, updated_at: NOW,
  });
  const msgs = (q: string): StoredMessage[] => [
    { id: `${q}-u`, role: "user", content: q, from_cache: false, citations: [], created_at: NOW },
    { id: `${q}-a`, role: "assistant", content: FAKE_ANSWER_TEXT, from_cache: false, citations: FAKE_CITATIONS, created_at: NOW },
  ];
  const db: Db = {
    matters: [matter],
    conversations: [conv("fake-conv-1", "What is bail?", matter.id), conv("fake-conv-2", "Limitation for a cheque notice", null)],
    messages: { "fake-conv-1": msgs("What is bail?"), "fake-conv-2": msgs("Limitation for a cheque notice") },
    seq: 100,
    shares: [],
  };
  if (!MINIMAL) {
    // A matter with a very long title and 60 conversations, and one with none.
    db.matters.push(
      { ...matter, id: "fake-matter-long", title: LONG_MATTER_TITLE },
      { ...matter, id: "fake-matter-empty", title: "Sample matter with no conversations" },
    );
    CONVERSATION_TITLES.forEach((t, i) => {
      db.conversations.push(conv(`fake-conv-long-${i + 1}`, t, "fake-matter-long"));
    });
  }
  return db;
}

// Fake mode keeps its database in this browser's localStorage, so a second tab (for example
// one opening a shared link) sees what the first tab made. Tests use the small database and
// never touch localStorage. Every access is guarded: private windows throw.
const KEY = "fake-db-v1";
function load(): Db | null {
  if (MINIMAL || typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Db) : null;
  } catch {
    return null;
  }
}
export function persistFakeDb() {
  if (MINIMAL || typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(fakeDb));
  } catch {
    // storage full or blocked: the fake just stays in this tab's memory
  }
}

export let fakeDb: Db = load() ?? seed();
export const resetFakeDb = () => {
  fakeDb = seed();
  try {
    if (typeof window !== "undefined") window.localStorage.removeItem(KEY);
  } catch {
    // ignore
  }
};
export const nextId = (p: string) => `${p}-${++fakeDb.seq}`;

export function withCounts(m: MatterOut): MatterOut {
  return { ...m, conversation_count: fakeDb.conversations.filter((c) => c.matter_id === m.id).length };
}

export function fakeConversationDetail(id: string): ConversationDetail | null {
  const c = fakeDb.conversations.find((x) => x.id === id);
  return c ? { ...c, messages: fakeDb.messages[id] ?? [], provenance: FAKE_PROVENANCE } : null;
}

// Fake mode: remember a question and its sample answer so History and Share can find it.
// Returns the id of the stored answer (the done event carries it, as the real API does).
export function fakeRecordTurn(conversationId: string, question: string): string | null {
  const id = recordTurn(conversationId, question);
  persistFakeDb();
  return id;
}
function recordTurn(conversationId: string, question: string): string | null {
  const c = fakeDb.conversations.find((x) => x.id === conversationId);
  if (!c) return null;
  c.title ??= question.slice(0, 80);
  c.message_count += 2;
  const a = fakeAnswerFor(question);
  const list = (fakeDb.messages[conversationId] ??= []);
  const assistantId = nextId("fake-msg");
  list.push(
    { id: nextId("fake-msg"), role: "user", content: question, from_cache: false, citations: [], created_at: NOW },
    { id: assistantId, role: "assistant", content: a.text, from_cache: false, citations: a.citations, created_at: NOW },
  );
  return assistantId;
}

// The stored answer behind a message id, with the question that led to it.
export function fakeStoredAnswer(messageId: string) {
  for (const list of Object.values(fakeDb.messages)) {
    const i = list.findIndex((m) => m.id === messageId && m.role === "assistant");
    if (i >= 0) return { question: [...list.slice(0, i)].reverse().find((m) => m.role === "user")?.content ?? "", answer: list[i] };
  }
  return null;
}
