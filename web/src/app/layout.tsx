import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { AppProviders } from "@/components/AppProviders";
import { config } from "@/lib/config";

// The font file is self-hosted (src/fonts) so builds work offline and no
// font name is written in code. The family name lives only in the file itself.
const brandFont = localFont({
  src: "../fonts/brand-sans.woff2",
  variable: "--font-brand",
  weight: "200 800",
  display: "swap",
});

export const metadata: Metadata = {
  title: config.productName,
  description: "Legal research with verified citations",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${brandFont.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
