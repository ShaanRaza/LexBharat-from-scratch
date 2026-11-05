"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { listMatters } from "@/lib/api/client";
import { signOut } from "@/lib/auth/signout";
import { FEATURE_PRICING, PRODUCT_NAME } from "@/lib/config";
import { NAV } from "@/lib/copy";
import { wordsFor } from "@/lib/matters/label";
import { useLoaded } from "@/lib/matters/useLoaded";
import { useDefaultKind } from "@/lib/matters/useRole";

const SHOWN_MATTERS = 8; // the rest are one click away on the Matters page

// The signed-in app's navigation: one list, used as a fixed column on a desktop and inside
// the Menu sheet on a phone (AppShell decides where it sits). Order, top to bottom:
// wordmark, New question, Matters with its list, History, a divider, the reference pages,
// then Help, Account and Sign out pinned to the bottom (in the phone sheet the wordmark
// is dropped, the bar above already shows it, and the middle list scrolls while the bottom group stays put). It never shows "Get early access":
// that belongs to the public shell. Styled only from tokens.
export function AppSidebar({ onNavigate, inSheet = false }: { onNavigate?: () => void; inSheet?: boolean }) {
  const path = usePathname();
  const router = useRouter();
  const kind = useDefaultKind();
  const words = wordsFor(kind);
  const matters = useLoaded(() => listMatters("active"), `sidebar-matters:${path}`);
  const [signOutFailed, setSignOutFailed] = useState(false);

  const item = (href: string, label: string) => {
    const here = path === href || (href !== "/" && path.startsWith(`${href}/`));
    return (
      <Link
        key={href}
        href={href}
        onClick={onNavigate}
        aria-current={here ? "page" : undefined}
        className={`block rounded-chip px-2 py-1.5 text-small font-semibold hover:bg-panel ${here ? "bg-tint text-ink" : "text-ink-soft hover:text-ink"}`}
      >
        {label}
      </Link>
    );
  };

  async function leave() {
    setSignOutFailed(false);
    try {
      await signOut();
      onNavigate?.();
      router.push("/signin");
    } catch {
      setSignOutFailed(true);
    }
  }

  const list = matters.value ?? [];
  return (
    <nav aria-label={NAV.appNav} className="flex min-h-0 flex-1 flex-col gap-4">
      {!inSheet && (
        <Link href="/" onClick={onNavigate} className="font-serif text-lead font-bold text-ink">
          {PRODUCT_NAME}
        </Link>
      )}
      <Link
        href="/"
        onClick={onNavigate}
        className="rounded-pill bg-accent px-4 py-2 text-center text-small font-semibold text-on-accent hover:bg-accent-hover"
      >
        {NAV.newQuestion}
      </Link>

      <div className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto">
        {item("/matters", words.many)}
        <ul aria-label={words.many} className="ml-2 flex flex-col gap-0.5 border-l border-line pl-2">
          {matters.status === "loading" && <li className="px-2 py-1 text-label text-ink-soft">…</li>}
          {matters.status === "error" && <li className="px-2 py-1 text-label text-ink-soft">{NAV.mattersFailed}</li>}
          {matters.status === "ready" && list.length === 0 && (
            <li className="px-2 py-1 text-label text-ink-soft">{NAV.mattersNone}</li>
          )}
          {list.slice(0, SHOWN_MATTERS).map((m) => {
            const href = `/matters/${m.id}`;
            const here = path === href;
            return (
              <li key={m.id}>
                <Link
                  href={href}
                  onClick={onNavigate}
                  aria-current={here ? "page" : undefined}
                  className={`block truncate rounded-chip px-2 py-1 text-small hover:bg-panel ${here ? "bg-tint font-semibold text-ink" : "text-ink-soft hover:text-ink"}`}
                >
                  {m.title}
                </Link>
              </li>
            );
          })}
          {list.length > SHOWN_MATTERS && (
            <li>
              <Link href="/matters" onClick={onNavigate} className="block px-2 py-1 text-label font-semibold text-accent">
                {NAV.allMatters} ({list.length})
              </Link>
            </li>
          )}
        </ul>
        {item("/history", NAV.history)}

        <hr className="my-2 border-line" />
        <h2 className="px-2 font-sans text-label font-bold uppercase tracking-wide text-ink-soft">{NAV.reference}</h2>
        {item("/acts", NAV.acts)}
        {item("/stats", NAV.statistics)}
        {item("/coverage", NAV.coverage)}
        {FEATURE_PRICING && item("/pricing", NAV.plans)}
      </div>

      <div className="flex flex-col gap-1 border-t border-line pt-3">
        {item("/help", NAV.help)}
        {item("/account", NAV.account)}
        <button
          type="button"
          onClick={leave}
          className="rounded-chip px-2 py-1.5 text-left text-small font-semibold text-ink-soft hover:bg-panel hover:text-ink"
        >
          {NAV.signOut}
        </button>
        {signOutFailed && (
          <p role="status" className="px-2 text-label text-ink-soft">
            Sign-out is not set up yet.
          </p>
        )}
      </div>
    </nav>
  );
}
