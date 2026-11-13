import type { Metadata } from "next";
import localFont from "next/font/local";
import { LandingExperience } from "./landing-experience";

const slab = localFont({ src: "../../public/landing/fonts/roboto-slab.ttf", weight: "800", display: "swap", variable: "--font-landing-slab" });

export const metadata: Metadata = {
  title: "Aegis — Commit before code.",
  description: "A runtime shield between autonomous agents and the live web—stopping deception before it becomes a commitment.",
};

export default function LandingPage() {
  return <div className={slab.variable}><LandingExperience /></div>;
}
