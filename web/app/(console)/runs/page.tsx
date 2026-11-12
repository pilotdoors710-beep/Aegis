"use client";

import { useState } from "react";
import { RunView } from "../run-view";

export default function RunsPage() {
  const [session, setSession] = useState(0);
  return <>
    <div className="console-intro"><div><p className="eyebrow">AUDIT TRAIL</p><h1>Run history</h1><p>Stored run history will appear here when backend persistence is available.</p></div></div>
    <section className="sample-banner"><div><strong className="badge">SAMPLE DATA</strong><span>Inspect the prepared comparison. This is a sample stream, not a fresh agent run.</span></div><button className="primary-button" onClick={() => setSession((value) => value + 1)}>{session ? "Restart sample" : "Open sample"}</button></section>
    {session > 0 && <RunView key={session} runId="sample" />}
  </>;
}
