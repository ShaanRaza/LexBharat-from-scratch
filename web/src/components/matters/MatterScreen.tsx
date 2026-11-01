"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, Label, TextField } from "@/components/ui";
import { deleteMatter, getMatter, updateMatter } from "@/lib/api/client";
import {
  MATTER_ARCHIVE,
  MATTER_CANCEL,
  MATTER_CONVERSATIONS,
  MATTER_CONVERSATIONS_NONE,
  MATTER_DELETE,
  MATTER_RENAME,
  MATTER_RESTORE,
  MATTER_SAVE,
} from "@/lib/copy";
import { wordsFor } from "@/lib/matters/label";
import { useLoaded } from "@/lib/matters/useLoaded";
import type { MatterDeleteMode } from "@/lib/api/types";
import { DeleteMatterDialog } from "./DeleteMatterDialog";

// One matter: its name (rename), archive/restore, delete (asks which delete), and the
// conversations filed under it.
export function MatterScreen({ id }: { id: string }) {
  const router = useRouter();
  const m = useLoaded(() => getMatter(id), `matter:${id}`);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [failed, setFailed] = useState(false);

  if (m.status === "loading") return <p className="text-ink-soft">Loading</p>;
  if (m.status === "error" || !m.value) {
    return (
      <Card role="alert">
        <p className="font-bold text-notfound">This was not found</p>
        <Link href="/matters" className="mt-2 inline-block text-small font-semibold text-accent underline">
          Back to the list
        </Link>
      </Card>
    );
  }
  const matter = m.value;
  const words = wordsFor(matter.kind);

  async function change(change: { title?: string; status?: "active" | "archived" }) {
    setFailed(false);
    try {
      await updateMatter(id, change);
      setRenaming(null);
      m.reload();
    } catch {
      setFailed(true);
    }
  }

  async function confirmDelete(mode: MatterDeleteMode) {
    await deleteMatter(id, mode); // a failure is shown inside the dialog
    router.push("/matters");
  }

  return (
    <article className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Label>{words.one}</Label>
        {matter.status === "archived" && <Label>Archived</Label>}
      </div>
      {renaming === null ? (
        <h1 className="text-title font-bold">{matter.title}</h1>
      ) : (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (renaming.trim()) change({ title: renaming });
          }}
        >
          <div className="min-w-0 flex-1 basis-full sm:basis-0">
            <TextField label={MATTER_RENAME} value={renaming} onChange={(e) => setRenaming(e.target.value)} />
          </div>
          <Button type="submit" disabled={!renaming.trim()}>
            {MATTER_SAVE}
          </Button>
          <Button type="button" variant="secondary" onClick={() => setRenaming(null)}>
            {MATTER_CANCEL}
          </Button>
        </form>
      )}
      <div className="flex flex-wrap gap-2">
        {renaming === null && (
          <Button variant="secondary" onClick={() => setRenaming(matter.title)}>
            {MATTER_RENAME}
          </Button>
        )}
        <Button variant="secondary" onClick={() => change({ status: matter.status === "active" ? "archived" : "active" })}>
          {matter.status === "active" ? MATTER_ARCHIVE : MATTER_RESTORE}
        </Button>
        <Button variant="secondary" onClick={() => setDeleting(true)}>
          {MATTER_DELETE}
        </Button>
      </div>
      {failed && (
        <p role="alert" className="text-small text-danger">
          Something went wrong. Please try again.
        </p>
      )}
      <section aria-label={MATTER_CONVERSATIONS} className="flex flex-col gap-2">
        <h2 className="font-sans text-label font-bold uppercase tracking-wide text-ink-soft">{MATTER_CONVERSATIONS}</h2>
        {matter.conversations.length === 0 && <p className="text-ink-soft">{MATTER_CONVERSATIONS_NONE}</p>}
        <ul className="flex flex-col gap-2">
          {matter.conversations.map((c) => (
            <li key={c.id}>
              <Link href={`/conversations/${c.id}`}>
                <Card>{c.title ?? "Untitled conversation"}</Card>
              </Link>
            </li>
          ))}
        </ul>
      </section>
      {deleting && <DeleteMatterDialog kind={matter.kind} onConfirm={confirmDelete} onCancel={() => setDeleting(false)} />}
    </article>
  );
}
