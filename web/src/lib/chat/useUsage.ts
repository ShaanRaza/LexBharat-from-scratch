"use client";
import { useEffect, useState } from "react";
import { getMe } from "@/lib/api/client";

// How many research answers are left this month. null = unknown (not signed in, the
// limit is not configured, or the call failed): the page then shows nothing.
export function useUsage(): number | null {
  const [left, setLeft] = useState<number | null>(null);
  useEffect(() => {
    let live = true;
    getMe()
      .then((m) => live && setLeft(m.answers_left_this_month))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);
  return left;
}
