import type { Metadata } from "next";
import localFont from "next/font/local";
import { LandingExperience } from "./landing-experience";
import styles from "./landing.module.css";

const slab = localFont({ src: "../../public/landing/fonts/roboto-slab.ttf", weight: "800", display: "swap", variable: "--font-landing-slab" });

export const metadata: Metadata = {
  title: "Aegis — Check before committing.",
  description: "Aegis protects browser agents from deceptive interfaces and checks that their actions match what you authorized.",
};

export default function LandingPage() {
  return <div className={slab.variable}><LandingExperience>
    <p className={styles.eyebrow}>AEGIS / RUNTIME SECURITY FOR BROWSER AGENTS</p>
    <h1 className={styles.headline}><span>Check before</span><span>committing.</span></h1>
    <p className={styles.description}>Aegis protects browser agents from deceptive interfaces and checks that their actions match what you authorized.</p>
  </LandingExperience></div>;
}
