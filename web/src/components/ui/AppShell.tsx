"use client";
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { PRODUCT_NAME } from "@/lib/config";
import { NAV } from "@/lib/copy";
import { AppSidebar } from "./AppSidebar";
import { Button } from "./Button";
import { Dialog } from "./Dialog";

// The frame for the signed-in app: a fixed left sidebar from the large breakpoint up; below
// it, a slim bar with the name and one Menu button that opens the same sidebar as a sheet.
// The public pages use PublicShell instead (a visitor from a search engine must not land
// in something that looks like a signed-in app).
export function AppShell({ children, width = "reading" }: { children: ReactNode; width?: "reading" | "content" }) {
  const [open, setOpen] = useState(false);
  const max = width === "content" ? "max-w-content" : "max-w-reading";
  return (
    <div className="flex min-h-screen flex-1 flex-col lg:flex-row">
      <aside className="hidden w-(--container-appnav) shrink-0 border-r border-line bg-page p-gutter lg:sticky lg:top-0 lg:block lg:h-screen">
        <AppSidebar />
      </aside>
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-page px-gutter py-3 lg:hidden">
        <Link href="/" className="font-serif text-lead font-bold text-ink">
          {PRODUCT_NAME}
        </Link>
        <Button variant="secondary" onClick={() => setOpen(true)} aria-haspopup="dialog">
          {NAV.menu}
        </Button>
        {open && (
          <Dialog title={NAV.menu} placement="sheet" onClose={() => setOpen(false)}>
            <div className="flex max-h-(--size-sheet-scroll) flex-col">
              <AppSidebar inSheet onNavigate={() => setOpen(false)} />
            </div>
          </Dialog>
        )}
      </header>
      <main className={`mx-auto w-full ${max} min-w-0 flex-1 px-gutter py-section`}>{children}</main>
    </div>
  );
}
