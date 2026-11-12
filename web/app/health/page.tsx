"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    fetch(`${API}/healthz/browser`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main className="mx-auto max-w-3xl p-8 font-sans">
      <h1 className="text-2xl font-semibold">Aegis: infrastructure check</h1>
      <p className="mt-2 text-sm text-zinc-400">Server: {API}</p>
      {error && <p className="mt-6 text-red-400">Server unreachable: {error}</p>}
      {!data && !error && <p className="mt-6 text-zinc-400">Contacting server…</p>}
      {data && (
        <section className="mt-6 space-y-3">
          <p className="text-emerald-400">
            Chromium {data.version} responded in {data.elapsed_ms} ms; page title “{data.title}”
          </p>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            alt="Screenshot taken by the remote browser"
            className="aspect-video w-full rounded border border-zinc-700"
            src={`data:image/jpeg;base64,${data.screenshot_b64}`}
          />
        </section>
      )}
    </main>
  );
}
