import { copy } from "@/lib/copy";
import type { FailureKind } from "@/lib/failure";
import { Button } from "./Button";
import { Card, type CardTone } from "./Card";

interface View {
  tone: CardTone;
  title: string;
  body: string;
  tips?: readonly string[];
  canRetry: boolean;
}

const VIEWS: Record<FailureKind, View> = {
  not_found: { tone: "notfound", ...copy.notFound, canRetry: false },
  out_of_scope: { tone: "notfound", ...copy.outOfScope, canRetry: false },
  usage_limit: { tone: "notfound", ...copy.usageLimit, tips: undefined, canRetry: false },
  provider_failed: { tone: "notfound", ...copy.providerFailed, tips: undefined, canRetry: true },
  service_error: { tone: "danger", ...copy.serviceError, tips: undefined, canRetry: true },
};

/** The failure screens: not found, outside coverage, limit reached, errors. */
export function FailureNotice({
  kind,
  requestId,
  onRetry,
}: {
  kind: FailureKind;
  requestId?: string | null;
  onRetry?: () => void;
}) {
  const v = VIEWS[kind];
  return (
    <Card tone={v.tone} as="section">
      <div role="alert" data-failure={kind}>
        <h2 className="text-lead font-heading">{v.title}</h2>
        <p className="mt-1 text-body">{v.body}</p>
        {v.tips && (
          <ul className="mt-2 list-disc pl-5 text-small text-muted">
            {v.tips.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        )}
        {requestId && (
          <p className="mt-2 text-label text-muted">Reference: {requestId}</p>
        )}
        {v.canRetry && onRetry && (
          <div className="mt-3">
            <Button variant="secondary" onClick={onRetry}>
              {copy.retry}
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
