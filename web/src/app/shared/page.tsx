import { PageShell } from "@/components/ui";
import { SharedLinksScreen } from "@/components/matters/SharedLinksScreen";
import { SHARED_LINKS_TITLE } from "@/lib/copy";

export default function Page() {
  return (
    <PageShell>
      <h1 className="mb-4 text-title font-extrabold">{SHARED_LINKS_TITLE}</h1>
      <SharedLinksScreen />
    </PageShell>
  );
}
