"use client";
// Chat logic for the screen. Presentational components get plain data and
// callbacks from here and know nothing about streaming or the API.
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { getApi, type ApiClient } from "@/lib/api";
import {
  answersLeftFrom,
  chatReducer,
  fromHistory,
  initialChatState,
  type ChatMessage,
} from "./chatState";

export interface UseChatOptions {
  /** Inject a client in tests; defaults to the real or fake client. */
  api?: ApiClient;
  /** Open an existing conversation; omit to start a new one lazily. */
  conversationId?: string | null;
  /** Called when a new conversation was created (e.g. to refresh the sidebar). */
  onConversationCreated?: (id: string) => void;
}

export interface UseChat {
  messages: ChatMessage[];
  busy: boolean;
  loading: boolean;
  answersLeft: number | null;
  send: (question: string) => Promise<void>;
  retry: () => Promise<void>;
}

export function useChat(options: UseChatOptions = {}): UseChat {
  const api = options.api ?? getApi();
  const { onConversationCreated } = options;
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const [answersLeft, setAnswersLeft] = useState<number | null>(null);
  const [loading, setLoading] = useState(Boolean(options.conversationId));
  const conversationId = useRef<string | null>(options.conversationId ?? null);
  const abort = useRef<AbortController | null>(null);
  const counter = useRef(0);
  const lastQuestion = useRef<string | null>(null);
  const busyRef = useRef(false);

  // Load history when opening an existing conversation.
  useEffect(() => {
    const id = options.conversationId;
    if (!id) return;
    let cancelled = false;
    api
      .getConversation(id)
      .then((c) => {
        if (!cancelled) dispatch({ type: "load", messages: c.messages.map(fromHistory) });
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [api, options.conversationId]);

  // Stop any running stream when the screen goes away.
  useEffect(() => () => abort.current?.abort(), []);

  const run = useCallback(
    async (question: string) => {
      if (busyRef.current) return;
      busyRef.current = true;
      lastQuestion.current = question;
      const n = ++counter.current;
      const assistantId = `a${n}`;
      dispatch({ type: "ask", userId: `u${n}`, assistantId, question });
      const controller = new AbortController();
      abort.current = controller;
      try {
        if (!conversationId.current) {
          const created = await api.createConversation();
          conversationId.current = created.id;
          onConversationCreated?.(created.id);
        }
        for await (const event of api.streamMessage(conversationId.current, question, controller.signal)) {
          dispatch({ type: "event", id: assistantId, event });
          const left = answersLeftFrom(event);
          if (left !== null) setAnswersLeft(left);
        }
        dispatch({ type: "interrupted", id: assistantId }); // no-op if `done` came
      } catch (err) {
        if (!controller.signal.aborted) {
          const code = err && typeof err === "object" && "code" in err ? String((err as { code: unknown }).code) : "internal_error";
          dispatch({ type: "event", id: assistantId, event: { type: "error", code, message: "", requestId: null } });
        }
      } finally {
        busyRef.current = false;
      }
    },
    [api, onConversationCreated],
  );

  const send = useCallback(
    async (question: string) => {
      const q = question.trim();
      if (q) await run(q);
    },
    [run],
  );

  const retry = useCallback(async () => {
    const q = lastQuestion.current;
    if (!q || busyRef.current) return;
    dispatch({ type: "dropLastTurn" });
    await run(q);
  }, [run]);

  const last = state.messages[state.messages.length - 1];
  return {
    messages: state.messages,
    busy: last?.role === "assistant" && last.status === "streaming",
    loading,
    answersLeft,
    send,
    retry,
  };
}
