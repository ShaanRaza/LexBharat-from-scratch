"use client";
import { useState } from "react";
import { Button, Card, Dialog, EmptyState, Label } from "@/components/ui";
import { deleteAccount, getMe, listConsents, requestExport, withdrawConsent } from "@/lib/api/client";
import {
  ACCOUNT_SECTIONS,
  CONSENTS_NONE,
  CONSENT_GIVEN,
  CONSENT_VERSION_LABEL,
  CONSENT_WITHDRAW,
  CONSENT_WITHDRAWN,
  DELETE_BUTTON,
  DELETE_CONFIRM_BUTTON,
  DELETE_CONFIRM_TITLE,
  DELETE_CONSEQUENCES,
  DELETE_DONE,
  DELETE_FAILED,
  EXPORT_BUTTON,
  EXPORT_FAILED,
  EXPORT_READY,
  MATTER_CANCEL,
  ANSWERS_LEFT,
} from "@/lib/copy";
import { useLoaded } from "@/lib/matters/useLoaded";

type Note = { status: "idle" } | { status: "working" } | { status: "done" } | { status: "failed" };

// Account settings: plan and usage, consents (with the notice version they were given
// under), export my data, delete my account. Export and delete call routes that exist but
// answer 501 today (GET /me/export, DELETE /me): the screen then says it is not available.
export function AccountScreen() {
  const me = useLoaded(() => getMe(), "me");
  const consents = useLoaded(() => listConsents(), "consents");
  const [exp, setExp] = useState<Note>({ status: "idle" });
  const [del, setDel] = useState<Note>({ status: "idle" });
  const [confirm, setConfirm] = useState(false);

  async function doExport() {
    setExp({ status: "working" });
    try {
      await requestExport();
      setExp({ status: "done" });
    } catch {
      setExp({ status: "failed" });
    }
  }
  async function doDelete() {
    setDel({ status: "working" });
    try {
      await deleteAccount();
      setDel({ status: "done" });
      setConfirm(false);
    } catch {
      setDel({ status: "failed" });
      setConfirm(false);
    }
  }

  return (
    <div className="flex flex-col gap-section">
      <section id="plan" aria-label={ACCOUNT_SECTIONS.plan} className="flex flex-col gap-2">
        <h2 className="text-lead font-bold">{ACCOUNT_SECTIONS.plan}</h2>
        {me.status === "ready" && me.value && (
          <Card className="flex flex-wrap items-center gap-2">
            <Label>{me.value.plan}</Label>
            {me.value.answers_left_this_month !== null && <span>{ANSWERS_LEFT(me.value.answers_left_this_month)}</span>}
          </Card>
        )}
      </section>

      <section id="consents" aria-label={ACCOUNT_SECTIONS.consents} className="flex flex-col gap-2">
        <h2 className="text-lead font-bold">{ACCOUNT_SECTIONS.consents}</h2>
        {consents.status === "ready" && consents.value!.length === 0 && <EmptyState {...CONSENTS_NONE} />}
        <ul className="flex flex-col gap-2">
          {consents.value?.map((c) => (
            <li key={c.id}>
              <Card className="flex flex-wrap items-center justify-between gap-2">
                <span className="flex min-w-0 flex-col text-small">
                  <span className="font-semibold">{CONSENT_VERSION_LABEL(c.notice_version)}</span>
                  <span className="text-ink-soft">
                    {c.purpose} · {CONSENT_GIVEN(c.given_at.slice(0, 10))}
                  </span>
                </span>
                {c.withdrawn_at ? (
                  <Label plain>{CONSENT_WITHDRAWN(c.withdrawn_at.slice(0, 10))}</Label>
                ) : (
                  <Button
                    variant="secondary"
                    onClick={async () => {
                      await withdrawConsent(c.id);
                      consents.reload();
                    }}
                  >
                    {CONSENT_WITHDRAW}
                  </Button>
                )}
              </Card>
            </li>
          ))}
        </ul>
      </section>

      <section id="data" aria-label={ACCOUNT_SECTIONS.data} className="flex flex-col gap-2">
        <h2 className="text-lead font-bold">{ACCOUNT_SECTIONS.data}</h2>
        <div>
          <Button variant="secondary" disabled={exp.status === "working"} onClick={doExport}>
            {EXPORT_BUTTON}
          </Button>
        </div>
        {exp.status === "done" && <p role="status">{EXPORT_READY}</p>}
        {exp.status === "failed" && <p role="alert" className="text-small text-warn">{EXPORT_FAILED}</p>}
      </section>

      <section id="delete" aria-label={ACCOUNT_SECTIONS.delete} className="flex flex-col gap-2">
        <h2 className="text-lead font-bold">{ACCOUNT_SECTIONS.delete}</h2>
        <div>
          <Button variant="secondary" disabled={del.status === "working" || del.status === "done"} onClick={() => setConfirm(true)}>
            {DELETE_BUTTON}
          </Button>
        </div>
        {del.status === "done" && <p role="status">{DELETE_DONE}</p>}
        {del.status === "failed" && <p role="alert" className="text-small text-warn">{DELETE_FAILED}</p>}
      </section>

      {confirm && (
        <Dialog title={DELETE_CONFIRM_TITLE} onClose={() => setConfirm(false)}>
          <p data-needs-owner className="text-small text-warn">{DELETE_CONSEQUENCES}</p>
          <div className="flex flex-wrap gap-2">
            <Button disabled={del.status === "working"} onClick={doDelete}>
              {DELETE_CONFIRM_BUTTON}
            </Button>
            <Button variant="secondary" onClick={() => setConfirm(false)}>
              {MATTER_CANCEL}
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
