import { HelpIndex } from "@/components/launch/HelpScreens";
import { HELP_TITLE } from "@/lib/copy";

export default function Page() {
  return (
    <>
      <h1 className="mb-4 text-title font-bold">{HELP_TITLE}</h1>
      <HelpIndex />
    </>
  );
}
