"use client";
import { Button, Card, EmptyState, Label } from "@/components/ui";
import { listShares, revokeShare } from "@/lib/api/client";
import { EMPTY, SHARED_EXPIRES, SHARED_REVOKE, SHARED_REVOKED } from "@/lib/copy";
import { useLoaded } from "@/lib/matters/useLoaded";

// The links the user has made. A link can be switched off here; the public page stops
// working on the next request. The link address itself is not shown (it was shown once).
export function SharedLinksScreen() {
  const links = useLoaded(() => listShares(), "shares");
  if (links.status === "loading") return <p className="text-ink-soft">Loading</p>;
  if (links.status === "error") return <p role="alert" className="text-danger">Something went wrong. Please try again.</p>;
  if (links.value!.length === 0) return <EmptyState {...EMPTY.shared} />;
  return (
    <ul className="flex flex-col gap-2">
      {links.value!.map((l) => (
        <li key={l.id}>
          <Card className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-small">{SHARED_EXPIRES(l.expires_at.slice(0, 10))}</span>
            {l.revoked_at ? (
              <Label>{SHARED_REVOKED}</Label>
            ) : (
              <Button
                variant="secondary"
                onClick={async () => {
                  await revokeShare(l.id);
                  links.reload();
                }}
              >
                {SHARED_REVOKE}
              </Button>
            )}
          </Card>
        </li>
      ))}
    </ul>
  );
}
