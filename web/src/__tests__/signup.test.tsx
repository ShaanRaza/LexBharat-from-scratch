import { render, screen, fireEvent } from "@testing-library/react";
import { canSubmit } from "@/lib/auth/consent";
import { SignupForm } from "@/components/auth/SignupForm";

describe("signup consent", () => {
  it("needs both a valid email and consent", () => {
    expect(canSubmit("a@b.in", false)).toBe(false);
    expect(canSubmit("nope", true)).toBe(false);
    expect(canSubmit("a@b.in", true)).toBe(true);
  });
  it("consent box starts unticked and the button is disabled", () => {
    render(<SignupForm />);
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.in" } });
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("button", { name: "Create account" })).toBeEnabled();
  });
});
