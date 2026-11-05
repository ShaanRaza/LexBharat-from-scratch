// Pure rule: sign-up may submit only with a plausible email AND an explicit, unticked-by-default consent.
export function canSubmit(email: string, consented: boolean): boolean {
  return consented && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim());
}

// Sign-in may submit once both fields are filled.
export function canSignIn(email: string, password: string): boolean {
  return password.length > 0 && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim());
}
