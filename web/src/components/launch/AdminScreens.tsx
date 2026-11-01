"use client";
import { useEffect, useState } from "react";
import { Button, Card, EmptyState, Label, Loading } from "@/components/ui";
import { getAiSpend, getEvalRun, listInvented, listReports, setReportStatus, startEvalRun } from "@/lib/api/client";
import { ADMIN_NOTICE, REPORT_REASONS } from "@/lib/copy";
import { useLoaded } from "@/lib/matters/useLoaded";
import type { EvalRun, ReportRow } from "@/lib/api/types";

export function AdminNotice() {
  return (
    <p role="note" data-admin-notice className="rounded-chip border border-line bg-panel px-3 py-2 text-small text-ink-soft">
      {ADMIN_NOTICE}
    </p>
  );
}

const STATUS_LABEL: Record<ReportRow["status"], string> = { new: "New", in_review: "In review", resolved: "Resolved" };
const NEXT: Record<ReportRow["status"], ReportRow["status"] | null> = { new: "in_review", in_review: "resolved", resolved: null };
const NEXT_LABEL: Record<ReportRow["status"], string> = { new: "Start review", in_review: "Mark resolved", resolved: "" };

function ReportList({ rows, onChange }: { rows: ReportRow[]; onChange: () => void }) {
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((r) => {
        const next = NEXT[r.status];
        return (
          <li key={r.id}>
            <Card className="flex flex-col gap-2 break-words">
              <span className="flex flex-wrap items-center gap-2 text-small">
                <Label plain>{STATUS_LABEL[r.status]}</Label>
                <span className="font-semibold">{REPORT_REASONS[r.reason]}</span>
                <span className="text-ink-soft">{r.created_at.slice(0, 10)}</span>
              </span>
              {r.comment && <p className="max-w-measure text-small">{r.comment}</p>}
              {next && (
                <div>
                  <Button
                    variant="secondary"
                    onClick={async () => {
                      await setReportStatus(r.id, next);
                      onChange();
                    }}
                  >
                    {NEXT_LABEL[r.status]}
                  </Button>
                </div>
              )}
            </Card>
          </li>
        );
      })}
    </ul>
  );
}

// The triage queue: reports that still need a person (new or in review), newest first.
export function TriageScreen() {
  const reports = useLoaded(() => listReports(), "reports");
  if (reports.status === "loading") return <Loading />;
  const open = (reports.value ?? []).filter((r) => r.status !== "resolved");
  return (
    <div className="flex flex-col gap-4">
      <AdminNotice />
      <p className="text-small text-ink-soft" data-open-count>
        {open.length} open
      </p>
      {open.length === 0 ? (
        <EmptyState title="Nothing to triage" hint="New reports from users appear here." />
      ) : (
        <ReportList rows={open} onChange={reports.reload} />
      )}
    </div>
  );
}

// Every reported answer, resolved ones too.
export function ReportsScreen() {
  const reports = useLoaded(() => listReports(), "reports-all");
  if (reports.status === "loading") return <Loading />;
  const rows = reports.value ?? [];
  return (
    <div className="flex flex-col gap-4">
      <AdminNotice />
      {rows.length === 0 ? <EmptyState title="No reported answers" hint="Reports from users appear here." /> : <ReportList rows={rows} onChange={reports.reload} />}
    </div>
  );
}

// The 200-question test runner: start a run, watch it progress, read the pass rate and the failures.
export function EvalsScreen() {
  const [run, setRun] = useState<EvalRun | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!run || run.status === "done") return;
    const t = setTimeout(async () => {
      try {
        setRun(await getEvalRun(run.id));
      } catch {
        setFailed(true);
      }
    }, 150);
    return () => clearTimeout(t);
  }, [run]);
  const rate = run && run.done > 0 ? Math.round((run.passed / run.done) * 1000) / 10 : null;
  return (
    <div className="flex flex-col gap-4">
      <AdminNotice />
      <div>
        <Button
          disabled={run?.status === "running"}
          onClick={async () => {
            setFailed(false);
            try {
              setRun(await startEvalRun());
            } catch {
              setFailed(true);
            }
          }}
        >
          Start a run
        </Button>
      </div>
      {failed && <p role="alert" className="text-small text-warn">The runner is not available yet.</p>}
      {!run && !failed && <EmptyState title="No run yet" hint="Start a run to test the 200 questions against the current build." />}
      {run && (
        <Card className="flex flex-col gap-2" data-run-status={run.status}>
          <progress className="w-full" value={run.done} max={run.total} aria-label="Progress" />
          <p role="status" className="text-small">
            {run.done} of {run.total} questions {run.status === "done" ? "done" : "run"}
            {rate !== null && ` · pass rate ${rate}%`}
          </p>
          {run.failures.length > 0 && (
            <ul aria-label="Failures" className="flex flex-col gap-1 text-small">
              {run.failures.map((f) => (
                <li key={f.id} className="break-words">
                  <span className="font-semibold">{f.id}</span> ({f.kind}): {f.detail}
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}

// The invented-citation log: what the verifier removed, and why. For admins only.
export function InventedScreen() {
  const rows = useLoaded(() => listInvented(), "invented");
  if (rows.status === "loading") return <Loading />;
  return (
    <div className="flex flex-col gap-4">
      <AdminNotice />
      {(rows.value ?? []).length === 0 ? (
        <EmptyState title="No removed citations" hint="Citations the verifier removes are logged here with the reason." />
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.value!.map((r) => (
            <li key={r.id}>
              <Card className="flex flex-col gap-1 break-words text-small">
                <span className="flex flex-wrap gap-2">
                  <Label plain>{r.reason}</Label>
                  <span className="text-ink-soft">{r.at.slice(0, 10)}</span>
                </span>
                <span>{r.cited_text}</span>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Daily AI spend: answers, helper calls, tokens, and money only if a price is configured.
export function SpendScreen() {
  const rows = useLoaded(() => getAiSpend(), "spend");
  if (rows.status === "loading") return <Loading />;
  const money = (n: number | null) => (n === null ? "—" : n.toFixed(2));
  return (
    <div className="flex flex-col gap-4">
      <AdminNotice />
      {(rows.value ?? []).length === 0 ? (
        <EmptyState title="No spend recorded" hint="Daily figures appear here once answers are made." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-small">
            <thead>
              <tr className="border-b border-line text-ink-soft">
                {["Day", "Answers", "Helper calls", "Tokens in", "Tokens out", "Cost", "Cost per answer"].map((h) => (
                  <th key={h} className="whitespace-nowrap py-2 pr-4 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.value!.map((r) => (
                <tr key={r.day} className="border-b border-line">
                  <td className="py-2 pr-4">{r.day}</td>
                  <td className="py-2 pr-4">{r.answers}</td>
                  <td className="py-2 pr-4">{r.helper_calls}</td>
                  <td className="py-2 pr-4">{r.tokens_in.toLocaleString("en-IN")}</td>
                  <td className="py-2 pr-4">{r.tokens_out.toLocaleString("en-IN")}</td>
                  <td className="py-2 pr-4">{money(r.estimated_cost)}</td>
                  <td className="py-2 pr-4">{money(r.cost_per_answer)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-small text-ink-soft">A dash means no model price is configured, so only tokens are known.</p>
        </div>
      )}
    </div>
  );
}
