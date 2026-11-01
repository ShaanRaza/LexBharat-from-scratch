import { Button } from "@/components/Button";
import { Card } from "@/components/Card";

export default function NotFound() {
  return (
    <div className="mx-auto w-full max-w-reading px-gutter py-8">
      <Card tone="notfound" as="section">
        <h1 className="text-lead font-heading">We could not find that page</h1>
        <p className="mt-1 text-body">Nothing is guessed: if a record is not in our dataset we say so.</p>
        <div className="mt-3">
          <Button href="/" variant="secondary">
            Back to research
          </Button>
        </div>
      </Card>
    </div>
  );
}
