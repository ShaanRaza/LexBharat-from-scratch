"use client";
import { useSyncExternalStore } from "react";

// Who is looking: decides only which FRAME a public page is drawn in (sidebar for a signed-in
// viewer, light top bar for a visitor). It grants nothing: every private route is guarded by
// the API, so a forged flag shows a different frame and no data.
//
// Today the flag is kept in this browser (localStorage) and set by signIn/signOut. When
// Firebase is wired, call markSignedIn/markSignedOut from its auth-state listener instead.
const KEY = "viewer-signed-in";
const listeners = new Set<() => void>();

function read(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false; // private window or blocked storage: treat as a visitor
  }
}

function write(on: boolean) {
  try {
    if (on) window.localStorage.setItem(KEY, "1");
    else window.localStorage.removeItem(KEY);
  } catch {
    // storage blocked: the frame just stays the public one
  }
  listeners.forEach((l) => l());
}

export const markSignedIn = () => write(true);
export const markSignedOut = () => write(false);

function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb); // another tab signed in or out
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

// The server render, and the first client render, are always the visitor's: search engines
// see exactly what they saw before, and there is no hydration mismatch.
export function useViewerSignedIn(): boolean {
  return useSyncExternalStore(subscribe, read, () => false);
}
