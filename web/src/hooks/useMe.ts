"use client";
import { useEffect, useState } from "react";
import { getApi } from "@/lib/api";
import type { Me } from "@/lib/types";
import { useAuth } from "./useAuth";

/** Profile + answers left. Only asked for when someone is signed in. */
export function useMe(): Me | null {
  const { session } = useAuth();
  const [me, setMe] = useState<Me | null>(null);
  const signedIn = session !== null;
  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    getApi()
      .getMe()
      .then((m) => !cancelled && setMe(m))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [signedIn]);
  return signedIn ? me : null;
}
