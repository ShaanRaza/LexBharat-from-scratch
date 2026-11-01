import { PageShell } from "@/components/ui";
import { HistoryScreen } from "@/components/matters/HistoryScreen";
import { HISTORY_TITLE } from "@/lib/copy";

export default function Page() {
  return (
    <PageShell>
      <h1 className="mb-4 text-title font-extrabold">{HISTORY_TITLE}</h1>
      <HistoryScreen />
    </PageShell>
  );
}
