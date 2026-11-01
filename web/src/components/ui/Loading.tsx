export function Loading({ what = "Loading" }: { what?: string }) {
  return (
    <p role="status" className="text-ink-soft">
      {what}
    </p>
  );
}
