import Link from "next/link";
import type { ReactNode } from "react";
import { Label } from "./Label";

export interface TopBarLink {
  href: string;
  label: string;
}

interface Props {
  productName: string;
  links: TopBarLink[];
  /** Plain number, e.g. 18 (never "credits"). null hides it. */
  answersLeft?: number | null;
  /** Extra controls on the right, e.g. a sign-out button. */
  actions?: ReactNode;
}

/** Sticky top bar. Pure display: the container decides what goes in it. */
export function TopBar({ productName, links, answersLeft, actions }: Props) {
  return (
    <header className="sticky top-0 z-10 h-topbar border-b border-line bg-page">
      <div className="mx-auto flex h-full max-w-content items-center gap-4 px-gutter">
        <Link href="/" className="text-lead font-heading text-text">
          {productName}
        </Link>
        <nav className="ml-auto flex items-center gap-4 text-small font-label">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className="text-muted hover:text-accent">
              {l.label}
            </Link>
          ))}
        </nav>
        {answersLeft != null && <Label tone="accent">{answersLeft} answers left this month</Label>}
        {actions}
      </div>
    </header>
  );
}
