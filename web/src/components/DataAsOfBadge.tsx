import { Label } from "./Label";

/** "Data as of 31 Aug 2026". Shows the API's date, else the snapshot name. */
export function DataAsOfBadge({
  date,
  snapshot,
}: {
  date?: string | null;
  snapshot?: string;
}) {
  return <Label tone="neutral">Data as of {formatDate(date) ?? snapshot ?? "snapshot date unknown"}</Label>;
}

function formatDate(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  // UTC so server and browser print the same day.
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}
