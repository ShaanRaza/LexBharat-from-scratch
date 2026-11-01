"use client";
// Loads one thing from the API and reports loading / error / data.
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api-error";

export type Loaded<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; data: T };

export function useApiData<T>(load: () => Promise<T>, key: string): Loaded<T> {
  const [result, setResult] = useState<{ key: string; value: Loaded<T> } | null>(null);
  useEffect(() => {
    let cancelled = false;
    load()
      .then((data) => !cancelled && setResult({ key, value: { status: "ready", data } }))
      .catch((e: unknown) => {
        if (cancelled) return;
        const error = e instanceof ApiError ? e : new ApiError("internal_error", "", 0);
        setResult({ key, value: { status: "error", error } });
      });
    return () => {
      cancelled = true;
    };
    // `load` is a fresh closure each render; `key` identifies what to load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return result && result.key === key ? result.value : { status: "loading" };
}
