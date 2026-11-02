import type { ReactNode } from "react";
import { AppShell } from "./AppShell";
import { PublicShell } from "./PublicShell";
import { ViewerShell } from "./ViewerShell";

// Every page picks one of two frames, on purpose and in plain sight:
//   shell="app"    the signed-in tool: left sidebar (AppShell)
//   shell="public" always the light top bar (PublicShell): /signin and /signup only
//   shell="auto"   public data pages: the frame follows the viewer (ViewerShell)
// There is no default, so a new page cannot end up in the wrong one by accident.
export function PageShell({
  shell,
  children,
  width = "reading",
}: {
  shell: "app" | "public" | "auto";
  children: ReactNode;
  width?: "reading" | "content";
}) {
  const Frame = shell === "app" ? AppShell : shell === "auto" ? ViewerShell : PublicShell;
  return <Frame width={width}>{children}</Frame>;
}
