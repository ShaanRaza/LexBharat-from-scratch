import Link from "next/link";
import { PRODUCT_NAME } from "@/lib/config";

const LINKS = [
  { href: "/acts", label: "Acts" },
  { href: "/stats", label: "Statistics" },
  { href: "/coverage", label: "Coverage" },
  { href: "/signin", label: "Sign in" },
];

// Links wrap under the name on a phone instead of disappearing.
export function TopBar() {
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-page">
      <div className="mx-auto flex max-w-content flex-wrap items-center justify-between gap-x-4 gap-y-2 px-gutter py-3">
        <Link href="/" className="text-lead font-extrabold text-ink">
          {PRODUCT_NAME}
        </Link>
        <nav aria-label="Main" className="flex flex-wrap items-center gap-x-4 gap-y-1 text-small font-semibold">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="text-ink-soft hover:text-ink">
              {l.label}
            </Link>
          ))}
          <Link href="/signup" className="rounded-pill bg-accent px-4 py-2 text-on-accent hover:bg-accent-hover">
            Get early access
          </Link>
        </nav>
      </div>
    </header>
  );
}
