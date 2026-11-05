"use client";
import { useState } from "react";
import { Button, Card, TextField } from "@/components/ui";
import { AuthNotConfigured, signIn } from "@/lib/auth/signin";
import { canSignIn } from "@/lib/auth/consent";

export function SignInForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "done" | "unavailable" | "error">("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSignIn(email, password)) return;
    setState("saving");
    try {
      await signIn(email.trim(), password);
      setState("done");
    } catch (err) {
      setState(err instanceof AuthNotConfigured ? "unavailable" : "error");
    }
  }

  if (state === "done") return <Card>You are signed in.</Card>;
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <TextField label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <TextField label="Password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
      {state === "unavailable" && (
        <p role="alert" className="text-small text-notfound">Sign-in is not available yet.</p>
      )}
      {state === "error" && <p role="alert" className="text-small text-danger">Something went wrong. Please try again.</p>}
      <Button type="submit" disabled={!canSignIn(email, password) || state === "saving"}>
        Sign in
      </Button>
    </form>
  );
}
