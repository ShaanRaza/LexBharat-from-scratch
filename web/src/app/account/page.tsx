import { AreaLayout, PageShell } from "@/components/ui";
import { AccountScreen } from "@/components/launch/AccountScreen";
import { ACCOUNT_SECTIONS, ACCOUNT_TITLE } from "@/lib/copy";

const ITEMS = [
  { href: "/account#plan", label: ACCOUNT_SECTIONS.plan },
  { href: "/account#consents", label: ACCOUNT_SECTIONS.consents },
  { href: "/account#data", label: ACCOUNT_SECTIONS.data },
  { href: "/account#delete", label: ACCOUNT_SECTIONS.delete },
];

export default function Page() {
  return (
    <PageShell shell="app" width="content">
      <AreaLayout title={ACCOUNT_TITLE} items={ITEMS}>
        <h1 className="mb-4 text-title font-bold">{ACCOUNT_TITLE}</h1>
        <AccountScreen />
      </AreaLayout>
    </PageShell>
  );
}
