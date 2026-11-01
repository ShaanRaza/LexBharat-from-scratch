// Where the website gets the login token to send to the API.
// Real mode: Firebase sign-in is NOT wired yet (needs the firebase package and
// project keys - owner's call). Until then real mode sends no token and the
// API will answer 401 for logged-in routes. Fake mode uses a dummy token.
import { config } from "./config";

const FAKE_SESSION_KEY = "web_fake_session";

export interface FakeSession {
  email: string;
  name: string;
}

// A tiny store so React can follow the saved sign-in (useSyncExternalStore).
const listeners = new Set<() => void>();
let cachedRaw: string | null | undefined;
let cachedSession: FakeSession | null = null;

export function readFakeSession(): FakeSession | null {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(FAKE_SESSION_KEY);
  } catch {
    return null; // storage blocked: treat as signed out
  }
  if (raw === cachedRaw) return cachedSession; // same object each call
  cachedRaw = raw;
  try {
    cachedSession = raw ? (JSON.parse(raw) as FakeSession) : null;
  } catch {
    cachedSession = null; // corrupt value
  }
  return cachedSession;
}

export function writeFakeSession(session: FakeSession | null): void {
  try {
    if (session) window.localStorage.setItem(FAKE_SESSION_KEY, JSON.stringify(session));
    else window.localStorage.removeItem(FAKE_SESSION_KEY);
  } catch {
    /* storage blocked: nothing to save */
  }
  listeners.forEach((l) => l());
}

export function subscribeFakeSession(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener); // other tabs
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export async function getAuthToken(): Promise<string | null> {
  if (config.useFakeApi) return "fake-token";
  return null; // TODO: Firebase getIdToken() once sign-in is wired.
}
