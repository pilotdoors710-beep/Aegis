import type { Metadata } from "next";
import { LandingExperience } from "./landing-experience";

export const metadata: Metadata = {
  title: "Aegis",
  description: "A runtime shield between autonomous agents and the live web, stopping deception before it becomes a commitment.",
};

export default function LandingPage() {
  return <LandingExperience />;
}
