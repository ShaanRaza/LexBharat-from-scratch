import Link from "next/link";
import { TopNav } from "./TopNav";
import { FEATURE_PRICING, PRODUCT_NAME } from "@/lib/config";
import { NAV } from "@/lib/copy";

// The public top bar: reference pages, help, sign-in and early access. Nothing here is
// personal (no matters, history or account): those live in the app sidebar.
const LINKS = [
  { href: "/acts", label: NAV.acts },
  { href: "/stats", label: NAV.statistics },
  { href: "/coverage", label: NAV.coverage },
  ...(FEATURE_PRICING ? [{ href: "/pricing", label: NAV.plans }] : []),
  { href: "/help", label: NAV.help },
  { href: "/signin", label: NAV.signIn },
];

export function TopBar() {
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-page">
      <div className="mx-auto flex max-w-content items-center justify-between gap-x-4 px-gutter py-3">
        <Link href="/" className="font-serif text-lead font-bold text-ink">
          {PRODUCT_NAME}
        </Link>
        <TopNav links={LINKS} />
      </div>
    </header>
  );
}
