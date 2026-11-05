"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Card, Label, TextField } from "@/components/ui";
import { SAMPLE_LABEL } from "@/lib/copy";

type Sample = { act_slug: string; act_name: string; section: string };

// Go to one Act section by its slug and number. There is no Acts index route in
// docs/API.md, so the list of samples only appears in fake mode.
export function ActLookup({ samples }: { samples: Sample[] }) {
  const router = useRouter();
  const [slug, setSlug] = useState("");
  const [section, setSection] = useState("");
  const ok = slug.trim() !== "" && section.trim() !== "";
  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (ok) router.push(`/acts/${encodeURIComponent(slug.trim())}/${encodeURIComponent(section.trim())}`);
        }}
      >
        <TextField label="Act (short name as in the address)" value={slug} onChange={(e) => setSlug(e.target.value)} />
        <TextField label="Section number" value={section} onChange={(e) => setSection(e.target.value)} />
        <Button type="submit" disabled={!ok} className="self-start">
          Look up
        </Button>
      </form>
      {samples.length > 0 && (
        <section aria-label="Sample sections">
          <Label>{SAMPLE_LABEL}</Label>
          <ul className="mt-2 flex flex-col gap-2">
            {samples.map((s) => (
              <li key={`${s.act_slug}/${s.section}`}>
                <a href={`/acts/${s.act_slug}/${s.section}`}>
                  <Card>
                    {s.act_name}, section {s.section}
                  </Card>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
