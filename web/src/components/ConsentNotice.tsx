import { consent } from "@/lib/copy";
import { Card } from "./Card";
import { Label } from "./Label";

/** The consent notice shown at sign-up. Text is a labelled placeholder for now. */
export function ConsentNotice() {
  return (
    <Card tone="panel" as="section">
      <div className="flex items-center gap-2">
        <h2 className="text-lead font-heading">{consent.title}</h2>
        <Label tone="notfound">Version {consent.noticeVersion}</Label>
      </div>
      <p className="mt-2 text-small text-muted">{consent.placeholder}</p>
    </Card>
  );
}
