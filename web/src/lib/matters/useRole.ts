"use client";
import { useEffect, useState } from "react";
import { getMe } from "@/lib/api/client";
import { defaultKind } from "./label";
import type { MatterKind } from "@/lib/api/types";

// Which word a NEW matter gets: "project" for a student, "matter" for everyone else.
export function useDefaultKind(): MatterKind {
  const [kind, setKind] = useState<MatterKind>("matter");
  useEffect(() => {
    let live = true;
    getMe().then(
      (m) => live && setKind(defaultKind(m.role)),
      () => {},
    );
    return () => {
      live = false;
    };
  }, []);
  return kind;
}
