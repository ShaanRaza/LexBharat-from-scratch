// Small inline icons. They use currentColor, so the colour comes from tokens.
import type { SVGProps } from "react";

const base = {
  width: 16,
  height: 16,
  viewBox: "0 0 16 16",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export const TickIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}><path d="M3 8.5l3.2 3.2L13 4.8" /></svg>
);
export const WarnIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}><path d="M8 3v6M8 12.2v.1" /></svg>
);
export const DashIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}><path d="M4 8h8" /></svg>
);
export const SearchIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}><circle cx="7" cy="7" r="4.2" /><path d="M10.2 10.2L13.5 13.5" /></svg>
);
export const PlusIcon = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base} {...p}><path d="M8 3v10M3 8h10" /></svg>
);
