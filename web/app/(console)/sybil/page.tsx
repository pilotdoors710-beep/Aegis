import { notFound } from "next/navigation";
import { SybilReadiness } from "./readiness";

export default function SybilPage() {
  if (process.env.SYBIL_ENABLED !== "true") notFound();
  return <SybilReadiness />;
}
