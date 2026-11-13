"use client";

import { useEffect, useState } from "react";
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
    <main className="mx-auto max-w-3xl p-8 font-sans">
      <h1 className="text-2xl font-semibold text-[#FCF8D8]">Aegis: infrastructure check</h1>
      <p className="mt-2 text-sm text-[#ADACA7]">Server: {API_URL}</p>
      {error && <p className="mt-6 text-[#ff9d94]">Server unreachable: {error}</p>}
      {!data && !error && <p className="mt-6 text-[#ADACA7]">Contacting server…</p>}
      {data && (
        <section className="mt-6 space-y-3">
          <p className="text-[#DD700B]">
            Chromium {data.version} responded in {data.elapsed_ms} ms; page title “{data.title}”
          </p>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            alt="Screenshot taken by the remote browser"
            className="aspect-video w-full rounded border border-[#7C7D75]"
            src={`data:image/jpeg;base64,${data.screenshot_b64}`}
          />
        </section>
      )}
    </main>
  );
}
