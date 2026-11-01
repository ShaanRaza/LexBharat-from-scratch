// Fake mode only: a small in-memory "database" for matters and conversations, so every
// matters screen can be clicked through with no backend. Labelled sample data. It lives
// only in the page's memory; `resetFakeDb()` gives tests a clean copy.
import type { ConversationDetail, ConversationOut, MatterOut, StoredMessage } from "@/lib/api/types";
import { FAKE_ANSWER_TEXT, FAKE_CITATIONS, FAKE_PROVENANCE } from "@/lib/fake/data";

type Db = {
  matters: MatterOut[];
  conversations: ConversationOut[];
  messages: Record<string, StoredMessage[]>;
  seq: number;
  shares: { id: string; message_id: string; token: string; created_at: string; expires_at: string; revoked_at: string | null }[];
};

const NOW = "2026-11-02T10:00:00Z";

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
  return {
    matters: [matter],
    conversations: [conv("fake-conv-1", "What is bail?", matter.id), conv("fake-conv-2", "Limitation for a cheque notice", null)],
    messages: { "fake-conv-1": msgs("What is bail?"), "fake-conv-2": msgs("Limitation for a cheque notice") },
    seq: 100,
    shares: [],
  };
}

export let fakeDb: Db = seed();
export const resetFakeDb = () => {
  fakeDb = seed();
};
export const nextId = (p: string) => `${p}-${++fakeDb.seq}`;

export function withCounts(m: MatterOut): MatterOut {
  return { ...m, conversation_count: fakeDb.conversations.filter((c) => c.matter_id === m.id).length };
}

export function fakeConversationDetail(id: string): ConversationDetail | null {
  const c = fakeDb.conversations.find((x) => x.id === id);
  return c ? { ...c, messages: fakeDb.messages[id] ?? [], provenance: FAKE_PROVENANCE } : null;
}

// Fake mode: remember a question and its sample answer so History can find it.
export function fakeRecordTurn(conversationId: string, question: string) {
  const c = fakeDb.conversations.find((x) => x.id === conversationId);
  if (!c) return;
  c.title ??= question.slice(0, 80);
  c.message_count += 2;
  const list = (fakeDb.messages[conversationId] ??= []);
  list.push(
    { id: nextId("fake-msg"), role: "user", content: question, from_cache: false, citations: [], created_at: NOW },
    { id: nextId("fake-msg"), role: "assistant", content: FAKE_ANSWER_TEXT, from_cache: false, citations: FAKE_CITATIONS, created_at: NOW },
  );
}
