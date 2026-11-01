import Link from "next/link";
import { TopNav } from "./TopNav";
import { FEATURE_PRICING, PRODUCT_NAME } from "@/lib/config";

const LINKS = [
  { href: "/history", label: "History" },
  { href: "/acts", label: "Acts" },
  { href: "/stats", label: "Statistics" },
  { href: "/coverage", label: "Coverage" },
  ...(FEATURE_PRICING ? [{ href: "/pricing", label: "Plans" }] : []),
  { href: "/help", label: "Help" },
  { href: "/account", label: "Account" },
  { href: "/signin", label: "Sign in" },
];

// Links wrap under the name on a phone instead of disappearing.
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
