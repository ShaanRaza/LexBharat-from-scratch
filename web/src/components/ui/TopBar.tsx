import Link from "next/link";
import { PRODUCT_NAME } from "@/lib/config";

export function TopBar() {
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-page">
      <div className="mx-auto flex max-w-content items-center justify-between px-gutter py-3">
        <Link href="/" className="text-lead font-extrabold text-ink">
          {PRODUCT_NAME}
        </Link>
        <nav className="flex items-center gap-4 text-small font-semibold">
          <Link href="/acts" className="hidden text-ink-soft hover:text-ink sm:inline">
            Acts
          </Link>
          <Link href="/signup" className="rounded-pill bg-accent px-4 py-2 text-on-accent hover:bg-accent-hover">
            Get early access
          </Link>
        </nav>
      </div>
    </header>
  );
}
