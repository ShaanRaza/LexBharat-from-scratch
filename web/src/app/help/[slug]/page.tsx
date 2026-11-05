import { Suspense } from "react";
import { HelpArticleView } from "@/components/launch/HelpScreens";
import { Loading } from "@/components/ui";

async function Article({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <HelpArticleView slug={decodeURIComponent(slug)} />;
}

export default function Page({ params }: { params: Promise<{ slug: string }> }) {
  return (
    <Suspense fallback={<Loading />}>
      <Article params={params} />
    </Suspense>
  );
}
