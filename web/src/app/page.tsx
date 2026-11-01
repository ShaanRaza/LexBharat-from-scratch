import { TopBar } from "@/components/ui";

export default function Home() {
  return (
    <>
      <TopBar />
      <main className="mx-auto w-full max-w-content flex-1 px-gutter py-section">
        <h1 className="text-display font-extrabold">Ask a legal question</h1>
      </main>
    </>
  );
}
