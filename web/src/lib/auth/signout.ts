import { USE_FAKE_API } from "@/lib/config";
import { AuthNotConfigured } from "./signin";

// Signing out is Firebase's job in the browser, like signing in, and is not wired yet.
// Fake mode has no session to end, so it succeeds and the caller goes to the sign-in page.
// Real mode says so plainly instead of pretending. When Firebase is added, replace this
// body (and clear the token provider).
export async function signOut(): Promise<void> {
  if (!USE_FAKE_API) throw new AuthNotConfigured("Sign-out is not set up yet");
}
