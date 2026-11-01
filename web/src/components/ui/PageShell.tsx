import type { ReactNode } from "react";
import { TopBar } from "./TopBar";

// Every page uses this one frame: top bar, centred reading column, standard padding.
export function PageShell({ children }: { children: ReactNode }) {
  return (
    <>
      <TopBar />
      <main className="mx-auto w-full max-w-reading flex-1 px-gutter py-section">{children}</main>
    </>
  );
}
