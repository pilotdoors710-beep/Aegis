import type { Metadata } from "next";
import { LandingExperience } from "./landing-experience";

export const metadata: Metadata = {
  title: "Aegis",
  description: "Aegis sits between a browser agent and the live web and checks each action before it runs, so a deceptive page cannot commit the agent to something the user never asked for.",
};

export default function LandingPage() {
  return <LandingExperience />;
}
