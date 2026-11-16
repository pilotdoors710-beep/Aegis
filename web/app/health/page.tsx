"use client";

import { SkeletonGroup, SkeletonLines, Skeleton } from "@/components/skeleton";
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
    <AppShell><header className="page-head"><span className="label">Health</span>
      <h1>Infrastructure check</h1>
      <p className="lede">Server: {API_URL}</p></header>
      {error && <p role="alert" className="error-message">Server unreachable: {error}</p>}
      {!data && !error && <SkeletonGroup label="Contacting server…"><SkeletonLines n={2} /><Skeleton className="skeleton-frame" /></SkeletonGroup>}
      {data && (
        <section className="health-card">
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
