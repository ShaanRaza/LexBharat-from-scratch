"use client";
import type { ReactNode } from "react";
import { useViewerSignedIn } from "@/lib/auth/viewer";
import { AppShell } from "./AppShell";
import { PublicShell } from "./PublicShell";

// For pages that are public data (Acts, Statistics, Coverage, Help, Plans, a shared answer, a
// judgment): the same content, in the frame that matches who is looking. A visitor (and every
// search engine, and the server render) gets the public top bar; a signed-in user gets
// their own sidebar, so clicking Acts does not look like being signed out.
export function ViewerShell({ children, width = "reading" }: { children: ReactNode; width?: "reading" | "content" }) {
  const signedIn = useViewerSignedIn();
  const Frame = signedIn ? AppShell : PublicShell;
  return <Frame width={width}>{children}</Frame>;
}
