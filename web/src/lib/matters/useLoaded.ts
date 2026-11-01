"use client";
import { useCallback, useEffect, useState } from "react";

// Load something once, and again on demand (`reload`). The result is tagged with the
// request that produced it, so a slow older answer can never replace a newer one. No
// styling here. `status` is "loading" until the first answer for the current key.
export function useLoaded<T>(load: () => Promise<T>, key: string) {
  const [tick, setTick] = useState(0);
  const [res, setRes] = useState<{ id: string; value?: T; failed: boolean } | null>(null);
  const id = `${key}#${tick}`;
  useEffect(() => {
    let live = true;
    load().then(
      (value) => live && setRes({ id, value, failed: false }),
      () => live && setRes({ id, failed: true }),
    );
    return () => {
      live = false;
    };
    // `load` changes every render; the key and tick say when to fetch again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  const current = res && res.id.startsWith(`${key}#`) ? res : null;
  return {
    value: current?.value,
    status: !current ? ("loading" as const) : current.failed ? ("error" as const) : ("ready" as const),
    reload,
  };
}
