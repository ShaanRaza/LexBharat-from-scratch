import { Card } from "@/components/ui";
import { StepActiveMark, StepDoneMark } from "@/components/ui/Marks";
import { PROGRESS_COUNTS, PROGRESS_LABELS } from "@/lib/copy";
import type { StepEventData } from "@/lib/api/types";

// Shows where the answer is, step by step. It is given step names and counts and
// nothing else: it has no way to show a citation, so none can appear early.
export function ProgressPanel({ steps, done }: { steps: StepEventData[]; done?: boolean }) {
  if (steps.length === 0) return null;
  const last = steps.length - 1;
  return (
    <Card role="status" aria-live="polite" aria-label="Progress">
      <ol className="flex flex-col gap-1 text-small">
        {steps.map((s, i) => {
          const active = !done && i === last;
          const counts = PROGRESS_COUNTS(s.found, s.kept);
          return (
            <li
              key={`${s.step}-${i}`}
              data-state={active ? "active" : "done"}
              className={`step-enter flex flex-wrap items-center gap-2 ${active ? "font-semibold text-ink" : "text-ink-soft"}`}
            >
              {active ? <StepActiveMark /> : <StepDoneMark />}
              <span>{PROGRESS_LABELS[s.step]}</span>
              {counts && <span className="text-label font-normal text-ink-soft">{counts}</span>}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
