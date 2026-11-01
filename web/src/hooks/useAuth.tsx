"use client";
// Fake sign-in for now (a name + email kept in this browser only). Real
// Firebase sign-in replaces the inside of this file later; screens only use
// useAuth(), so they will not change.
import { createContext, useCallback, useContext, useMemo, useSyncExternalStore, type ReactNode } from "react";
import { readFakeSession, subscribeFakeSession, writeFakeSession, type FakeSession } from "@/lib/auth-token";

interface AuthValue {
  session: FakeSession | null;
  signIn: (session: FakeSession) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  // Server render and first paint: signed out. Then the saved sign-in is read.
  const session = useSyncExternalStore(subscribeFakeSession, readFakeSession, () => null);
  const signIn = useCallback((s: FakeSession) => writeFakeSession(s), []);
  const signOut = useCallback(() => writeFakeSession(null), []);
  const value = useMemo(() => ({ session, signIn, signOut }), [session, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
