// The one place font families are chosen. Their CSS variables are read by --font-serif and
// --font-sans in tokens.css. To change a typeface, change it here.
//
// Noto Serif for headings and the wordmark; Inter for the interface and body text. The two
// Devanagari siblings are loaded for Hindi (after the launch gate): the browser downloads
// them only if a page contains Devanagari text, so they cost nothing until then.
import { Inter, Noto_Sans_Devanagari, Noto_Serif, Noto_Serif_Devanagari } from "next/font/google";

export const serifFont = Noto_Serif({
  variable: "--font-noto-serif",
  subsets: ["latin"],
  weight: ["600", "700"],
});

export const sansFont = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const sansDevanagariFont = Noto_Sans_Devanagari({
  variable: "--font-noto-sans-deva",
  subsets: ["devanagari"],
  weight: ["400", "600"],
});

export const serifDevanagariFont = Noto_Serif_Devanagari({
  variable: "--font-noto-serif-deva",
  subsets: ["devanagari"],
  weight: ["600", "700"],
});

// All four variables, to put on <html>.
export const fontVariables = [
  serifFont.variable,
  sansFont.variable,
  sansDevanagariFont.variable,
  serifDevanagariFont.variable,
].join(" ");
