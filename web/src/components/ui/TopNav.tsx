"use client";
import Link from "next/link";
import { useState } from "react";
import { MattersNavLink } from "@/components/matters/MattersNavLink";
import { Button } from "./Button";
import { Dialog } from "./Dialog";

type NavLink = { href: string; label: string };

// The top-bar links. On a desktop they sit in a row. On a phone (375px is the design width)
// they sit behind one Menu button, in a sheet with large tap targets, instead of wrapping into
// four rows above the page. The same list feeds both, so nothing is reachable on one only.
export function TopNav({ links }: { links: NavLink[] }) {
  const [open, setOpen] = useState(false);
  const cta = "rounded-pill bg-accent px-4 py-2 text-center text-on-accent hover:bg-accent-hover";
  return (
    <>
      <nav aria-label="Main" className="hidden flex-wrap items-center gap-x-4 gap-y-1 text-small font-semibold md:flex">
        <MattersNavLink />
        {links.map((l) => (
          <Link key={l.href} href={l.href} className="text-ink-soft hover:text-ink">
            {l.label}
          </Link>
        ))}
        <Link href="/signup" className={cta}>
          Get early access
        </Link>
      </nav>
      <div className="md:hidden">
        <Button variant="secondary" onClick={() => setOpen(true)} aria-haspopup="dialog">
          Menu
        </Button>
        {open && (
          <Dialog title="Menu" placement="sheet" onClose={() => setOpen(false)}>
            <nav aria-label="Menu" className="flex flex-col gap-1 text-body font-semibold" onClick={() => setOpen(false)}>
              <span className="block rounded-chip px-2 py-2 hover:bg-panel">
                <MattersNavLink />
              </span>
              {links.map((l) => (
                <Link key={l.href} href={l.href} className="block rounded-chip px-2 py-2 text-ink hover:bg-panel">
                  {l.label}
                </Link>
              ))}
              <Link href="/signup" className={`${cta} mt-2`}>
                Get early access
              </Link>
            </nav>
          </Dialog>
        )}
      </div>
    </>
  );
}
