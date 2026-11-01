import Link from "next/link";
import { copy } from "@/lib/copy";
import type { CitationState } from "@/lib/citations";
import { DashIcon, TickIcon, WarnIcon } from "./icons";

const STYLE: Record<CitationState, string> = {
  verified: "border-verified bg-verified-tint text-verified",
  partial: "border-notfound bg-notfound-tint text-notfound",
  unverified: "border-notfound bg-page text-notfound",
};

const DEFAULT_LABEL: Record<CitationState, string> = {
  verified: copy.verified,
  partial: copy.partly,
  unverified: copy.notVerified,
};

/**
 * One source chip, e.g. "S1".
 * The tick shows ONLY for state "verified". The other states get a warning
 * mark or a dash, never a tick. The state is worked out in lib/citations.ts.
 */
export function CitationChip({
  sourceId,
  state,
  href,
  label: apiLabel,
}: {
  sourceId: string;
  state: CitationState;
  href?: string | null;
  /** Wording from the API (e.g. "Record found in dataset"); else our copy. */
  label?: string | null;
}) {
  const label = apiLabel || DEFAULT_LABEL[state];
  const Icon = state === "verified" ? TickIcon : state === "partial" ? WarnIcon : DashIcon;
  const inner = (
    <>
      <span>{sourceId}</span>
      <span role="img" aria-label={label} data-state={state} className="inline-flex">
        <Icon width={12} height={12} />
      </span>
    </>
  );
  const cls = `inline-flex items-center gap-1 rounded-pill border px-2 py-0.5 text-label font-label align-baseline ${STYLE[state]}`;
  return href ? (
    <Link href={href} className={cls} title={label}>
      {inner}
    </Link>
  ) : (
    <span className={cls} title={label}>
      {inner}
    </span>
  );
}
