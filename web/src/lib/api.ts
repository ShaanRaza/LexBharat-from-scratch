// The ONLY place the website talks to the backend (rule 3). Everything else
// calls getApi() and gets typed data back. With NEXT_PUBLIC_USE_FAKE_API=1 the
// same interface is served from sample data, so the whole site works with no
// backend.
import { ApiError } from "./api-error";
import { getAuthToken } from "./auth-token";
import { config } from "./config";
import { createFakeApi } from "./fake/fakeApi";
import { readSse, toStreamEvent } from "./sse";
import {
  caseFromWire,
  conversationFromWire,
  historyFromWire,
  meFromWire,
  sectionFromWire,
} from "./mappers";
import type {
  ActSection,
  ApiErrorBody,
  CaseRecord,
  ConversationSummary,
  HistoryMessage,
  Me,
  Page,
  StreamEvent,
} from "./types";

export { ApiError };

export interface ApiClient {
  getMe(): Promise<Me>;
  listConversations(cursor?: string): Promise<Page<ConversationSummary>>;
  createConversation(): Promise<{ id: string }>;
  getConversation(id: string): Promise<{
    id: string;
    title: string;
    messages: HistoryMessage[];
    data_as_of: string | null;
  }>;
  /** Streams one answer: text..., one citations, then done. Never throws. */
  streamMessage(
    conversationId: string,
    content: string,
    signal?: AbortSignal,
  ): AsyncIterable<StreamEvent>;
  getCase(id: string): Promise<CaseRecord>;
  /** Public - no login needed. */
  getSection(actSlug: string, section: string): Promise<ActSection>;
  recordConsent(noticeVersion: string, purpose: string): Promise<void>;
}

const BASE = `${config.apiUrl}/api/v1`;

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getAuthToken();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError("network_error", "Could not reach the server.", 0);
  }
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as Partial<ApiErrorBody>;
    return new ApiError(
      body.error?.code ?? "internal_error",
      body.error?.message ?? "",
      res.status,
      body.error?.request_id ?? res.headers.get("x-request-id"),
    );
  } catch {
    return new ApiError("internal_error", "", res.status, res.headers.get("x-request-id"));
  }
}

function createRealApi(): ApiClient {
  return {
    getMe: async () => meFromWire(await request<unknown>("/me")),
    listConversations: async (cursor) => {
      const r = await request<{ items?: unknown[]; next_cursor?: string | null }>(
        `/conversations${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
      );
      return {
        items: (r.items ?? []).map(conversationFromWire).filter((c): c is ConversationSummary => c !== null),
        next_cursor: r.next_cursor ?? null,
      };
    },
    createConversation: async () => {
      const r = await request<{ id: string }>("/conversations", {
        method: "POST",
        body: JSON.stringify({ module: "research" }),
      });
      return { id: r.id };
    },
    getConversation: async (id) =>
      historyFromWire(await request<unknown>(`/conversations/${encodeURIComponent(id)}`)),
    getCase: async (id) => caseFromWire(await request<unknown>(`/cases/${encodeURIComponent(id)}`)),
    getSection: async (act, n) =>
      sectionFromWire(
        await request<unknown>(`/acts/${encodeURIComponent(act)}/sections/${encodeURIComponent(n)}`),
        act,
      ),
    recordConsent: async (notice_version, purpose) => {
      await request("/me/consents", {
        method: "POST",
        body: JSON.stringify({ notice_version, purpose, action: "give" }),
      });
    },
    async *streamMessage(conversationId, content, signal) {
      const token = await getAuthToken();
      const headers: Record<string, string> = {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
      };
      if (token) headers.Authorization = `Bearer ${token}`;
      let res: Response;
      try {
        res = await fetch(`${BASE}/conversations/${encodeURIComponent(conversationId)}/messages`, {
          method: "POST",
          headers,
          body: JSON.stringify({ content }),
          signal,
        });
      } catch {
        if (signal?.aborted) return;
        yield { type: "error", code: "network_error", message: "", requestId: null };
        return;
      }
      if (!res.ok || !res.body) {
        const err = await toApiError(res);
        yield { type: "error", code: err.code, message: err.message, requestId: err.requestId };
        return;
      }
      try {
        for await (const msg of readSse(res.body)) {
          const ev = toStreamEvent(msg);
          if (ev) yield ev;
        }
      } catch {
        if (signal?.aborted) return;
        yield { type: "error", code: "stream_interrupted", message: "", requestId: null };
      }
    },
  };
}

let cached: ApiClient | null = null;

/** The client the whole site uses: sample data or the real backend. */
export function getApi(): ApiClient {
  if (!cached) cached = config.useFakeApi ? createFakeApi() : createRealApi();
  return cached;
}
