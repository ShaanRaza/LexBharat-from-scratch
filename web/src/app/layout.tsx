import type { Metadata } from "next";
import { fontVariables } from "@/design/fonts";
import { PRODUCT_NAME } from "@/lib/config";
import "./globals.css";

export const metadata: Metadata = {
  title: PRODUCT_NAME,
  description: "Legal research with verified citations",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${fontVariables} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
