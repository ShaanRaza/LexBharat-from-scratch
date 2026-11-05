import type { ReactNode } from "react";
import { AreaLayout, PageShell } from "@/components/ui";
import { HELP_CONTACT, HELP_TITLE } from "@/lib/copy";

const ITEMS = [
  { href: "/help", label: "All articles" },
  { href: "/help/contact", label: HELP_CONTACT },
];

export default function HelpLayout({ children }: { children: ReactNode }) {
  return (
    <PageShell shell="auto" width="content">
      <AreaLayout title={HELP_TITLE} items={ITEMS}>
        {children}
      </AreaLayout>
    </PageShell>
  );
}
