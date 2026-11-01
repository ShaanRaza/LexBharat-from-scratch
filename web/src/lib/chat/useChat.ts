"use client";
import { useCallback, useRef, useState } from "react";
import { askQuestion, createConversation } from "@/lib/api/client";
import { applyEvent, endOfStream, newAnswer, type AnswerState } from "./state";

// Hook: holds the list of answers and runs a question. No styling here.
export function useChat() {
  const [answers, setAnswers] = useState<AnswerState[]>([]);
  const conv = useRef<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const ask = useCallback(async (question: string) => {
    let state = newAnswer(question);
    const idx = { current: -1 };
    const write = (s: AnswerState) =>
      setAnswers((a) => {
        if (idx.current === -1) {
          idx.current = a.length;
          return [...a, s];
        }
        const copy = [...a];
        copy[idx.current] = s;
        return copy;
      });
    write(state);
    try {
      if (conv.current === null) {
        conv.current = await createConversation();
        setConversationId(conv.current);
      }
      for await (const ev of askQuestion(conv.current, question)) {
        state = applyEvent(state, ev);
        write(state);
      }
      write((state = endOfStream(state)));
    } catch {
      write((state = { ...state, status: "failed", failure: "serviceError", text: "" }));
    }
  }, []);

  return { answers, ask, conversationId, busy: answers.some((a) => a.status === "streaming") };
}
