import Link from "next/link";
import { Card, PageShell, StandingNotices } from "@/components/ui";

export default function NotFound() {
  return (
    <PageShell shell="public">
      <Card>
        <h1 className="text-lead font-bold">This page or record was not found</h1>
        <p className="mt-2 text-ink-soft">Check the address, or go back and ask a question or look up an Act section.</p>
        <Link href="/" className="mt-3 inline-block text-small font-semibold text-accent underline">
          Back to home
        </Link>
      </Card>
      <StandingNotices />
    </PageShell>
  );
}
