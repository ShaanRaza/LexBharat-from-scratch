"use client";
import Link from "next/link";
import { useState } from "react";
import { Button, Card, EmptyState, Label, TextField } from "@/components/ui";
import { createMatter, listMatters } from "@/lib/api/client";
import {
  EMPTY,
  MATTERS_NONE,
  MATTER_CREATE,
  MATTER_NEW_LABEL,
  MATTER_SHOW_ARCHIVED,
} from "@/lib/copy";
import { countOf, wordsFor } from "@/lib/matters/label";
import { useLoaded } from "@/lib/matters/useLoaded";
import { useDefaultKind } from "@/lib/matters/useRole";

// The list of matters (or projects): create, open. The word shown comes from `kind`.
export function MattersScreen() {
  const kind = useDefaultKind();
  const [showArchived, setShowArchived] = useState(false);
  const [title, setTitle] = useState("");
  const [error, setError] = useState(false);
  const list = useLoaded(() => listMatters(showArchived ? "all" : "active"), `matters:${showArchived}`);
  const words = wordsFor(kind);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setError(false);
    try {
      await createMatter(title, kind);
      setTitle("");
      list.reload();
    } catch {
      setError(true);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-title font-bold">{words.many}</h1>
      <form onSubmit={create} className="flex flex-wrap items-end gap-2">
        <div className="min-w-0 flex-1 basis-full sm:basis-0">
          <TextField label={MATTER_NEW_LABEL(words.one)} value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <Button type="submit" disabled={!title.trim()}>
          {MATTER_CREATE}
        </Button>
      </form>
      {error && (
        <p role="alert" className="text-small text-danger">
          Something went wrong. Please try again.
        </p>
      )}
      <label className="flex items-center gap-2 text-small">
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
        {MATTER_SHOW_ARCHIVED}
      </label>
      {list.status === "loading" && <p className="text-ink-soft">Loading</p>}
      {list.status === "error" && (
        <p role="alert" className="text-danger">
          Something went wrong. Please try again.
        </p>
      )}
      {list.status === "ready" && list.value!.length === 0 && (
        <EmptyState title={MATTERS_NONE(words.many)} hint={EMPTY.matters.hint} />
      )}
      <ul className="flex flex-col gap-2">
        {list.value?.map((m) => (
          <li key={m.id}>
            <Link href={`/matters/${m.id}`}>
              <Card className="flex flex-wrap items-center justify-between gap-2">
                <span className="min-w-0 break-words font-semibold">{m.title}</span>
                <span className="flex items-center gap-2 text-small text-ink-soft">
                  <Label>{wordsFor(m.kind).one}</Label>
                  {m.status === "archived" && <Label>Archived</Label>}
                  {countOf(m.conversation_count, "conversation")}
                </span>
              </Card>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
