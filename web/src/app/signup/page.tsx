import { PageShell, StandingNotices } from "@/components/ui";
import { SignupForm } from "@/components/auth/SignupForm";

export default function Signup() {
  return (
    <PageShell>
      <h1 className="mb-4 text-title font-bold">Get early access</h1>
      <SignupForm />
      <StandingNotices />
    </PageShell>
  );
}
