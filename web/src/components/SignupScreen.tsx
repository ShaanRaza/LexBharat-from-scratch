"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { getApi } from "@/lib/api";
import { config } from "@/lib/config";
import { consent } from "@/lib/copy";
import { SignupForm } from "./SignupForm";

/** Sign-up logic: records consent (with its notice version), then signs in. */
export function SignupScreen() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!agreed) return; // consent is required before anything is created
    setBusy(true);
    setError(null);
    try {
      await getApi().recordConsent(consent.noticeVersion, consent.purpose);
      signIn({ name: name.trim(), email: email.trim() });
      router.push("/");
    } catch {
      setError("We could not save your consent, so the account was not created. Please try again.");
      setBusy(false);
    }
  };

  return (
    <SignupForm
      name={name}
      email={email}
      agreed={agreed}
      busy={busy}
      error={error}
      isFake={config.useFakeApi}
      onName={setName}
      onEmail={setEmail}
      onAgreed={setAgreed}
      onSubmit={() => void submit()}
    />
  );
}
