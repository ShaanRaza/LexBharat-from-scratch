"use client";
import { useCallback, useState } from "react";
import { improveQuestion } from "@/lib/api/client";

export type ImproveState =
  | { status: "idle" }
  | { status: "working" }
  | { status: "suggestion"; text: string }
  | { status: "unchanged" }
  | { status: "failed" };

// The "Improve my question" helper. It only returns text for the input box: it never
// sends anything, never runs a search and is not part of the answer pipeline.
export function useImprove() {
  const [state, setState] = useState<ImproveState>({ status: "idle" });
  const improve = useCallback(async (text: string) => {
    setState({ status: "working" });
    try {
      const out = await improveQuestion(text);
      setState(out.changed && out.text.trim() ? { status: "suggestion", text: out.text } : { status: "unchanged" });
    } catch {
      setState({ status: "failed" });
    }
  }, []);
  const edit = useCallback((text: string) => setState({ status: "suggestion", text }), []);
  const dismiss = useCallback(() => setState({ status: "idle" }), []);
  return { state, improve, edit, dismiss };
}
