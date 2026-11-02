import { PageShell } from "@/components/ui";
import { HistoryScreen } from "@/components/matters/HistoryScreen";
import { HISTORY_TITLE } from "@/lib/copy";

export default function Page() {
  return (
    <PageShell shell="app">
      <h1 className="mb-4 text-title font-bold">{HISTORY_TITLE}</h1>
      <HistoryScreen />
    </PageShell>
  );
}
