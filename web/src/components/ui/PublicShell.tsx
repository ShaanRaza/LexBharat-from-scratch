import type { ReactNode } from "react";
import { TopBar } from "./TopBar";

// The frame for the public pages (Acts, Statistics, Coverage, shared answers, Help, Plans,
// sign-in): a light top bar and a centred column. No sidebar, no matters list.
export function PublicShell({ children, width = "reading" }: { children: ReactNode; width?: "reading" | "content" }) {
  const max = width === "content" ? "max-w-content" : "max-w-reading";
  return (
    <>
      <TopBar />
      <main className={`mx-auto w-full ${max} flex-1 px-gutter py-section`}>{children}</main>
    </>
  );
}
