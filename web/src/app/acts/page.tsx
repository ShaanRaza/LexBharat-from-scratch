import { TopBar, Card, Label } from "@/components/ui";
import { FAKE_SECTIONS } from "@/lib/fake/data";

// Sample list until the API has an Acts index route (docs/API.md lists none).
export default function Acts() {
  return (
    <>
      <TopBar />
      <main className="mx-auto w-full max-w-reading flex-1 px-gutter py-section">
        <h1 className="mb-4 text-title font-extrabold">Look up an Act section</h1>
        <Label>Sample</Label>
        <ul className="mt-4 flex flex-col gap-2">
          {FAKE_SECTIONS.map((s) => (
            <li key={`${s.act_slug}/${s.section}`}>
              <a href={`/acts/${s.act_slug}/${s.section}`}>
                <Card>
                  {s.act_name}, section {s.section}
                </Card>
              </a>
            </li>
          ))}
        </ul>
      </main>
    </>
  );
}
