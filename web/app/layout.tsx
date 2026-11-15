import type { Metadata } from "next";
import { Azeret_Mono } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";

// Coolvetica (Typodermic) for all text except the AEGIS wordmark.
const coolvetica = localFont({
  variable: "--font-coolvetica",
  src: [
    // One static weight covers every weight, so bold text never falls to Heavy Compressed or faux bold.
    { path: "../public/landing/fonts/coolvetica/Coolvetica Rg.otf", weight: "100 900", style: "normal" },
    { path: "../public/landing/fonts/coolvetica/Coolvetica Rg It.otf", weight: "100 900", style: "italic" },
  ],
});

// Azeret Mono for data, labels and counters: tabular figures without the usual AI-default monos.
const azeretMono = Azeret_Mono({
  variable: "--font-azeret-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Aegis",
  description: "Runtime security for browser agents: we check the receipt before signing.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${coolvetica.variable} ${azeretMono.variable} dark h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[#151614] text-[#D9DADF]">
        {children}
      </body>
    </html>
  );
}
