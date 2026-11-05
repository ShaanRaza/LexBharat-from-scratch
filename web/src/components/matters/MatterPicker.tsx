"use client";
import { Select } from "@/components/ui";
import { MATTER_UNFILED } from "@/lib/copy";
import { wordsFor } from "@/lib/matters/label";
import type { MatterOut } from "@/lib/api/types";

// Choose which matter a conversation is filed under, or "Unfiled". Presentational.
export function MatterPicker({
  label,
  matters,
  value,
  onChange,
  disabled,
}: {
  label: string;
  matters: MatterOut[];
  value: string | null;
  onChange: (matterId: string | null) => void;
  disabled?: boolean;
}) {
  return (
    <Select label={label} value={value ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value || null)}>
      <option value="">{MATTER_UNFILED}</option>
      {matters.map((m) => (
        <option key={m.id} value={m.id}>
          {wordsFor(m.kind).one}: {m.title}
        </option>
      ))}
    </Select>
  );
}
