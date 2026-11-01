import { PageShell, StandingNotices } from "@/components/ui";
import { SignInForm } from "@/components/auth/SignInForm";

export default function SignIn() {
  return (
    <PageShell>
      <h1 className="mb-4 text-title font-extrabold">Sign in</h1>
      <SignInForm />
      <StandingNotices />
    </PageShell>
  );
}
