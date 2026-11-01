import { USE_FAKE_API } from "@/lib/config";

export class AuthNotConfigured extends Error {}

// Sign-in itself is Firebase's job in the browser (docs/API.md) and is not wired yet.
// Fake mode accepts any well-formed input; real mode says so plainly instead of
// pretending. When Firebase is added, replace this body and call setTokenProvider.
export async function signIn(email: string, password: string): Promise<void> {
  if (!USE_FAKE_API) throw new AuthNotConfigured("Sign-in is not set up yet");
  if (!email || !password) throw new Error("missing");
}
