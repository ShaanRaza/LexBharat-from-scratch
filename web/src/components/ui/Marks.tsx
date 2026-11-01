// The small outline marks that sit beside a citation's words. Drawn, not typed: one
// stroke weight, in the text colour of whatever they sit in (never a green check; see
// docs/DESIGN-DIRECTION.md section 4). They are decoration: the words carry the meaning.
type Props = { className?: string };

const base = {
  width: 16,
  height: 16,
  viewBox: "0 0 16 16",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false,
};

// Record found in the dataset.
export function TickMark({ className }: Props) {
  return (
    <svg {...base} className={className}>
      <circle cx="8" cy="8" r="6.25" />
      <path d="M5.2 8.2l2 2 3.6-4" />
    </svg>
  );
}

// Supports only partly: the circle is half open.
export function PartlyMark({ className }: Props) {
  return (
    <svg {...base} className={className}>
      <path d="M8 1.75a6.25 6.25 0 1 0 0 12.5" />
      <path d="M8 1.75v12.5" strokeDasharray="2 2" />
    </svg>
  );
}

// Support not checked: a dashed circle.
export function UncheckedMark({ className }: Props) {
  return (
    <svg {...base} className={className}>
      <circle cx="8" cy="8" r="6.25" strokeDasharray="2.2 2.2" />
    </svg>
  );
}

// A citation was removed / a check failed: an outline triangle, drawn in --warn.
export function RemovedMark({ className }: Props) {
  return (
    <svg {...base} className={className}>
      <path d="M8 2.2L14.2 13H1.8L8 2.2z" />
      <path d="M8 6.4v3" />
      <path d="M8 11.4v.1" />
    </svg>
  );
}

// Progress panel only (not a verification mark): a finished step.
export function StepDoneMark({ className }: Props) {
  return (
    <svg {...base} className={className}>
      <path d="M3.5 8.4l3 3 6-6.4" />
    </svg>
  );
}

// Progress panel only: the step that is running.
export function StepActiveMark({ className }: Props) {
  return (
    <svg {...base} className={className}>
      <path d="M8 1.75a6.25 6.25 0 1 0 6.25 6.25" />
    </svg>
  );
}
