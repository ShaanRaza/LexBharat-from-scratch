import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-on-accent hover:bg-accent-hover border-transparent",
  secondary: "bg-page text-text border-line hover:bg-panel",
  ghost: "bg-transparent text-accent border-transparent hover:bg-panel",
};

const BASE =
  "inline-flex items-center justify-center gap-2 rounded-control border px-4 py-2 text-small font-label transition-colors disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-2 focus-visible:outline-accent";

interface Props extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> {
  variant?: Variant;
  /** Render as a link instead of a button. */
  href?: string;
  /** Open `href` as an outside link (new tab). */
  external?: boolean;
  children: ReactNode;
}

/** The one button style for the whole site. */
export function Button({ variant = "primary", href, external, children, ...rest }: Props) {
  const cls = `${BASE} ${VARIANTS[variant]}`;
  if (href && external) {
    return (
      <a className={cls} href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  }
  if (href) {
    return (
      <Link className={cls} href={href}>
        {children}
      </Link>
    );
  }
  return (
    <button className={cls} {...rest}>
      {children}
    </button>
  );
}
