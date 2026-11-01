"use client";
import type { ReactNode } from "react";
import { AuthProvider, useAuth } from "@/hooks/useAuth";
import { useMe } from "@/hooks/useMe";
import { config } from "@/lib/config";
import { Button } from "./Button";
import { TopBar } from "./TopBar";

function Shell({ children }: { children: ReactNode }) {
  const { session, signOut } = useAuth();
  const me = useMe();
  return (
    <>
      <TopBar
        productName={config.productName}
        links={[
          { href: "/", label: "Research" },
          ...(session ? [] : [{ href: "/signup", label: "Sign up" }]),
        ]}
        answersLeft={me?.answers_left ?? null}
        actions={
          session ? (
            <Button variant="ghost" onClick={signOut}>
              Sign out
            </Button>
          ) : null
        }
      />
      <main className="flex flex-1 flex-col">{children}</main>
    </>
  );
}

/** Wraps every page: sign-in state plus the top bar. */
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <Shell>{children}</Shell>
    </AuthProvider>
  );
}
