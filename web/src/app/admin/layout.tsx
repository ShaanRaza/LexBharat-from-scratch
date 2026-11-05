import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AreaLayout, PageShell } from "@/components/ui";
import { ADMIN_SECTIONS, ADMIN_TITLE } from "@/lib/copy";

// Admin is never for search engines, and it is not linked from the public top bar.
export const metadata: Metadata = { title: ADMIN_TITLE, robots: { index: false, follow: false } };

const ITEMS = [
  { href: "/admin", label: ADMIN_SECTIONS.triage },
  { href: "/admin/reports", label: ADMIN_SECTIONS.reports },
  { href: "/admin/evals", label: ADMIN_SECTIONS.evals },
  { href: "/admin/citations", label: ADMIN_SECTIONS.citations },
  { href: "/admin/spend", label: ADMIN_SECTIONS.spend },
];

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <PageShell shell="app" width="content">
      <AreaLayout title={ADMIN_TITLE} items={ITEMS}>
        {children}
      </AreaLayout>
    </PageShell>
  );
}
