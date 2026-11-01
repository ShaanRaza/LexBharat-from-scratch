// The one place a font family is chosen. Its CSS variable is read by --font-sans
// in tokens.css. To change the typeface, change it here.
import { Plus_Jakarta_Sans } from "next/font/google";

export const bodyFont = Plus_Jakarta_Sans({
  variable: "--font-jakarta",
  subsets: ["latin"],
  weight: ["400", "600", "700", "800"],
});
