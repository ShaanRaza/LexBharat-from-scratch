import type { Metadata } from "next";
import { Suspense } from "react";
import { Loading, PageShell } from "@/components/ui";
import { SharedAnswerView } from "@/components/chat/SharedAnswerView";
import { getShared } from "@/lib/api/client";
import { SHARED_TITLE } from "@/lib/copy";

// A shared answer is for the people who were given the link, not for search engines or
// caches, and its address must not leak in a Referer header.
export const metadata: Metadata = {
  title: SHARED_TITLE,
  robots: { index: false, follow: false, noarchive: true, nocache: true, nosnippet: true },
  referrer: "no-referrer",
};

async function Shared({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const shared = await getShared(decodeURIComponent(token)).catch(() => null);
  return <SharedAnswerView shared={shared} />;
}

export default function Page({ params }: { params: Promise<{ token: string }> }) {
  return (
    <PageShell>
      <Suspense fallback={<Loading />}>
        <Shared params={params} />
      </Suspense>
    </PageShell>
  );
}
