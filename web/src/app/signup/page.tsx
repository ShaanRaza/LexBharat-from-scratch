import { TopBar, StandingNotices } from "@/components/ui";
import { SignupForm } from "@/components/auth/SignupForm";

export default function Signup() {
  return (
    <>
      <TopBar />
      <main className="mx-auto w-full max-w-reading flex-1 px-gutter py-section">
        <h1 className="mb-4 text-title font-extrabold">Get early access</h1>
        <SignupForm />
        <StandingNotices />
      </main>
    </>
  );
}
