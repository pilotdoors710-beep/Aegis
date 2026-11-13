"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { API_URL } from "@/lib/api";

type BrowserHealth = {
  title: string;
  version: string;
  screenshot_b64: string;
  elapsed_ms: number;
};

// INF check remains accessible alongside the Shield Console.
export default function Home() {
  const [data, setData] = useState<BrowserHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/healthz/browser`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <AppShell><div className="console-intro"><div><p className="eyebrow">Service status</p>
      <h1>Infrastructure check</h1>
      <p>Server: {API_URL}</p></div></div>
      {error && <p role="alert" className="error-message">Server unreachable: {error}</p>}
      {!data && !error && <p role="status" className="console-card">Contacting server…</p>}
      {data && (
        <section className="console-card health-card">
          <p className="health-success">
            Chromium {data.version} responded in {data.elapsed_ms} ms; page title “{data.title}”
          </p>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            alt="Screenshot taken by the remote browser"
            className="health-screenshot"
            src={`data:image/jpeg;base64,${data.screenshot_b64}`}
          />
        </section>
      )}
    </AppShell>
  );
}
