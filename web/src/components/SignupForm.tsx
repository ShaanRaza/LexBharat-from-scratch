import { consent } from "@/lib/copy";
import { Button } from "./Button";
import { ConsentNotice } from "./ConsentNotice";
import { Label } from "./Label";

interface Props {
  name: string;
  email: string;
  agreed: boolean;
  busy: boolean;
  error: string | null;
  isFake: boolean;
  onName: (v: string) => void;
  onEmail: (v: string) => void;
  onAgreed: (v: boolean) => void;
  onSubmit: () => void;
}

const INPUT =
  "w-full rounded-control border border-line bg-page px-3 py-2 text-body focus:border-accent focus:outline-none";

/** Sign-up layout. The button stays off until the consent box is ticked. */
export function SignupForm(p: Props) {
  return (
    <form
      className="mx-auto flex w-full max-w-reading flex-col gap-4 px-gutter py-8"
      onSubmit={(e) => {
        e.preventDefault();
        p.onSubmit();
      }}
    >
      <h1 className="text-title font-heading">Create your account</h1>
      {p.isFake ? (
        <div>
          <Label tone="accent">Sample sign-up - no real account is created</Label>
        </div>
      ) : (
        <p className="text-small text-muted">Sign-in is not connected yet.</p>
      )}
      <label className="flex flex-col gap-1 text-small font-label">
        Name
        <input className={INPUT} value={p.name} onChange={(e) => p.onName(e.target.value)} autoComplete="name" required />
      </label>
      <label className="flex flex-col gap-1 text-small font-label">
        Email
        <input className={INPUT} type="email" value={p.email} onChange={(e) => p.onEmail(e.target.value)} autoComplete="email" required />
      </label>
      <ConsentNotice />
      <label className="flex items-start gap-2 text-small">
        <input type="checkbox" className="mt-1" checked={p.agreed} onChange={(e) => p.onAgreed(e.target.checked)} />
        <span>{consent.checkbox}</span>
      </label>
      {p.error && (
        <p role="alert" className="text-small text-danger">
          {p.error}
        </p>
      )}
      <div>
        <Button type="submit" disabled={!p.agreed || p.busy || !p.isFake}>
          Sign up
        </Button>
      </div>
    </form>
  );
}
