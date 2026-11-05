"use client";
import { useSyncExternalStore } from "react";
import { Button, Card } from "@/components/ui";
import { EMPTY, ONBOARDING_DISMISS, ONBOARDING_STEPS, ONBOARDING_TITLE } from "@/lib/copy";

const KEY = "onboarding-dismissed-v1";
const listeners = new Set<() => void>();
const subscribe = (cb: () => void) => {
  listeners.add(cb);
  return () => void listeners.delete(cb);
};
const read = () => {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
};
let dismissedHere = false; // when storage is blocked, "Got it" still hides it for this visit

// The first-run screen: what to do, in three steps, until the first question is asked.
// "Got it" is remembered in this browser (and works without storage: it just reappears).
// Instructions only: nothing here says what a mark means in law.
export function Onboarding() {
  // The server render never knows what this browser stored, so it shows the steps; a
  // returning visitor then switches to the short line without a hydration mismatch.
  const gone = useSyncExternalStore(subscribe, () => dismissedHere || read(), () => false);
  if (gone) {
    return (
      <p data-empty className="max-w-measure text-ink-soft">
        {EMPTY.chat.hint}
      </p>
    );
  }
  return (
    <Card data-onboarding className="flex max-w-measure flex-col gap-3">
      <h2 className="text-lead font-bold">{ONBOARDING_TITLE}</h2>
      <ol className="flex list-decimal flex-col gap-1 pl-5">
        {ONBOARDING_STEPS.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ol>
      <div>
        <Button
          variant="secondary"
          onClick={() => {
            try {
              window.localStorage.setItem(KEY, "1");
            } catch {
              // storage blocked: the card simply comes back next time
            }
            dismissedHere = true;
            listeners.forEach((l) => l());
          }}
        >
          {ONBOARDING_DISMISS}
        </Button>
      </div>
    </Card>
  );
}
