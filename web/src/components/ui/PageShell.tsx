import type { ReactNode } from "react";
import { TopBar } from "./TopBar";

// Every page uses this one frame: top bar, centred column, standard padding.
// "content" is the wider column, for screens with a second pane beside the first.
export function PageShell({ children, width = "reading" }: { children: ReactNode; width?: "reading" | "content" }) {
  const max = width === "content" ? "max-w-content" : "max-w-reading";
  return (
    <>
      <TopBar />
      <main className={`mx-auto w-full ${max} flex-1 px-gutter py-section`}>{children}</main>
    </>
  );
}
