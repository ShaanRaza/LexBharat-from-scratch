import { SupportForm } from "@/components/launch/HelpScreens";
import { HELP_CONTACT } from "@/lib/copy";

export default function Page() {
  return (
    <>
      <h1 className="mb-4 text-title font-bold">{HELP_CONTACT}</h1>
      <SupportForm />
    </>
  );
}
