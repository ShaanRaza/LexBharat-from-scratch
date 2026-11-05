import { USE_FAKE_API } from "@/lib/config";

// Visible whenever fake mode is on, so canned answers can never be mistaken for real ones.
export function DemoBanner() {
  if (!USE_FAKE_API) return null;
  return (
    <p role="status" className="rounded-chip bg-partly-bg px-3 py-2 text-small font-bold text-partly">
      DEMO DATA. These answers and sources are samples, not real.
    </p>
  );
}
