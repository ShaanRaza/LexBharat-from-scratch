import { ANSWERS_LEFT } from "@/lib/copy";

export function UsageMeter({ left }: { left: number | null }) {
  if (left === null) return null;
  return (
    <p className="text-small text-ink-soft" data-testid="usage-meter">
      {ANSWERS_LEFT(left)}
    </p>
  );
}
