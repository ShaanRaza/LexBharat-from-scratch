"use client";
import { useState } from "react";
import { Button, Card, TextField } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import type { ShareCreated } from "@/lib/api/types";
import {
  COPIED,
  SHARE_COPY_LINK,
  SHARE_EXPIRES,
  SHARE_FAILED,
  SHARE_LABEL,
  SHARE_LINK_LABEL,
  SHARE_MANAGE_HINT,
  SHARE_NOTE,
  SHARE_WORKING,
} from "@/lib/copy";

type State =
  | { status: "idle" }
  | { status: "working" }
  | { status: "made"; link: ShareCreated; copied: boolean }
  | { status: "refused"; message: string }
  | { status: "failed" };

// "Share" under a saved answer. The server decides: it refuses (and says why) when an
// upload or a saved matter fact shaped the answer, and then NO link exists. The token is
// shown once; only a hash is stored. Presentational: `create` and `copy` come in.
export function ShareControl({
  create,
  copy,
  origin,
}: {
  create: () => Promise<ShareCreated>;
  copy: (text: string) => Promise<boolean>;
  origin: string;
}) {
  const [state, setState] = useState<State>({ status: "idle" });

  async function go() {
    setState({ status: "working" });
    try {
      setState({ status: "made", link: await create(), copied: false });
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setState({ status: "refused", message: e.body.message });
      else setState({ status: "failed" });
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div>
        <Button variant="secondary" disabled={state.status === "working"} onClick={go}>
          {state.status === "working" ? SHARE_WORKING : SHARE_LABEL}
        </Button>
      </div>
      {state.status === "refused" && (
        <p role="alert" className="text-small text-notfound">
          {state.message}
        </p>
      )}
      {state.status === "failed" && (
        <p role="alert" className="text-small text-danger">
          {SHARE_FAILED}
        </p>
      )}
      {state.status === "made" && (
        <Card className="flex flex-col gap-2">
          <TextField label={SHARE_LINK_LABEL} readOnly value={`${origin}${state.link.path}`} onFocus={(e) => e.currentTarget.select()} />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              onClick={async () => {
                const ok = await copy(`${origin}${state.link.path}`);
                setState({ ...state, copied: ok });
              }}
            >
              {SHARE_COPY_LINK}
            </Button>
            {state.copied && (
              <span role="status" className="text-small text-ink-soft">
                {COPIED}
              </span>
            )}
          </div>
          <p className="text-small text-ink-soft">{SHARE_NOTE}</p>
          <p className="text-small text-ink-soft">
            {SHARE_EXPIRES(state.link.expires_at.slice(0, 10))}. {SHARE_MANAGE_HINT}
          </p>
        </Card>
      )}
    </div>
  );
}
