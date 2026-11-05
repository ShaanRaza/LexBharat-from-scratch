import { TriageScreen } from "@/components/launch/AdminScreens";
import { ADMIN_SECTIONS } from "@/lib/copy";

export default function Page() {
  return (
    <>
      <h1 className="mb-4 text-title font-bold">{ADMIN_SECTIONS.triage}</h1>
      <TriageScreen />
    </>
  );
}
