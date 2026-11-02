import { PageShell } from "@/components/ui";
import { MattersScreen } from "@/components/matters/MattersScreen";

export default function Page() {
  return (
    <PageShell shell="app">
      <MattersScreen />
    </PageShell>
  );
}
