// Pure rule: sign-up may submit only with a plausible email AND an explicit, unticked-by-default consent.
export function canSubmit(email: string, consented: boolean): boolean {
  return consented && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim());
}
