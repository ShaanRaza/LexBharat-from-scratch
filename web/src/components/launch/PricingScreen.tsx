"use client";
import { Card, EmptyState, Label, Loading } from "@/components/ui";
import { getPlans } from "@/lib/api/client";
import { FEATURE_PRICING } from "@/lib/config";
import { PRICING_CURRENT, PRICING_OFF } from "@/lib/copy";
import { useLoaded } from "@/lib/matters/useLoaded";

// Plans and limits as the server lists them. The page holds no price and no limit number:
// both come from the plan tables (the owner's, O10), and limits are plain numbers. The page
// is behind NEXT_PUBLIC_FEATURE_PRICING and says so plainly when it is off.
export function PricingScreen({ enabled = FEATURE_PRICING }: { enabled?: boolean }) {
  const plans = useLoaded(() => (enabled ? getPlans() : Promise.resolve([])), `plans:${enabled}`);
  if (!enabled) return <EmptyState title={PRICING_OFF} />;
  if (plans.status === "loading") return <Loading />;
  if (plans.status === "error") return <p role="alert" className="text-danger">Something went wrong. Please try again.</p>;
  return (
    <ul className="flex flex-col gap-4 sm:grid sm:grid-cols-2">
      {plans.value!.map((p) => (
        <li key={p.id} className="min-w-0">
          <Card className="flex h-full flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lead font-bold">{p.name}</h2>
              {p.current && <Label>{PRICING_CURRENT}</Label>}
            </div>
            <p className="break-words text-ink-soft">{p.price_text}</p>
            <ul className="flex flex-col gap-1 text-small">
              {p.limits.map((l) => (
                <li key={l.label}>
                  {l.value === null ? "" : `${l.value} `}
                  {l.label}
                </li>
              ))}
            </ul>
          </Card>
        </li>
      ))}
    </ul>
  );
}
