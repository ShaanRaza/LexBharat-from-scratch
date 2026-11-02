import type { ReactNode } from "react";
import { AppShell } from "./AppShell";
import { PublicShell } from "./PublicShell";

// Every page picks one of two frames, on purpose and in plain sight:
//   shell="app"    the signed-in tool: left sidebar (AppShell)
//   shell="public" logged-out visitors and search engines: light top bar (PublicShell)
// There is no default, so a new page cannot end up in the wrong one by accident.
export function PageShell({
  shell,
  children,
  width = "reading",
}: {
  shell: "app" | "public";
  children: ReactNode;
  width?: "reading" | "content";
}) {
  const Frame = shell === "app" ? AppShell : PublicShell;
  return <Frame width={width}>{children}</Frame>;
}
