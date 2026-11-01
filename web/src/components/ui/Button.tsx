import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary";

const styles: Record<Variant, string> = {
  primary: "bg-accent text-on-accent hover:bg-accent-hover",
  secondary: "bg-page text-ink border border-line hover:bg-panel",
};

export function Button({
  variant = "primary",
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...rest}
      className={`rounded-pill px-5 py-2.5 text-small font-semibold transition-colors disabled:opacity-50 ${styles[variant]} ${className}`}
    />
  );
}
