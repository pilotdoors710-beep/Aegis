"use client";

import { useState } from "react";
import { api, type Schema } from "@/lib/api";

type Report = Schema["ScanReport"];

// Arena pages are served by this same site. Real-world examples are third-party pages checked on
// 13 Nov 2026 (they can change): a public prompt-injection test page, a store theme demo, a clean site.
const ARENA_EXAMPLES = [
  ["Injection", "Hidden AI instruction and pressure tactics", "/arena/product.html?traps=T05,T06"],
  ["Fake close", "Fake close button", "/arena/index.html?traps=T01"],
  ["Clean", "Clean twin", "/arena/product.html?traps=none"],
] as const;
const REAL_EXAMPLES = [
  ["Injection", "Public test page with hidden AI instructions", "https://garden-advice.netlify.app/"],
  ["Sale prices", "Store theme demo with crossed-out prices", "https://theme-dawn-demo.myshopify.com/collections/all"],
  ["Wikipedia", "A clean site", "https://www.wikipedia.org/"],
] as const;

const inView = (e: Schema["Element"]) => e.bbox[0] < 1280 && e.bbox[1] < 720 && e.bbox[0] + e.bbox[2] > 0 && e.bbox[1] + e.bbox[3] > 0;

export default function ScanPage() {
  const [url, setUrl] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scan = async (target = url) => {
    setUrl(target); setBusy(true); setError(null); setReport(null);
    try { setReport(await api.scan({ url: target })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const arena = (path: string) => `${window.location.origin}${path}`;
  const boxes = report?.flagged.filter(inView) ?? [];
  const label = (id: string) => report?.findings.find((f) => f.element_id === id)?.trap_type ?? "";

  return <>
    <header className="page-head"><span className="label">Read-only page scan</span><h1>What would an agent walk into here?</h1>
      <p className="lede">Aegis opens the page once in a throwaway browser, without clicking anything, and runs the same fast checks that guard every agent action: hidden instructions to AI, fake close buttons, invisible overlays and pressure tactics. Only public websites can be scanned.</p>
      <ul className="facts"><li>Read-only</li><li>No AI model</li><li>Public pages only</li></ul></header>

    <form className="scan-form" onSubmit={(e) => { e.preventDefault(); void scan(); }}>
      <label htmlFor="scan-url" className="label">Page address</label>
      <div className="scan-bar">
        <input id="scan-url" type="url" required placeholder="https://example.com/product" value={url} onChange={(e) => setUrl(e.target.value)} />
        <button className="primary-button" type="submit" disabled={busy} aria-label="Scan this page">{busy ? "Scanning…" : "Scan"}</button>
      </div>
      <div className="chip-row">
        <span className="label">Arena</span>
        {ARENA_EXAMPLES.map(([name, about, path]) => <button type="button" className="text-button" key={path} title={about} aria-label={`Scan arena example: ${about}`} disabled={busy} onClick={() => void scan(arena(path))}>{name}</button>)}
        <span className="label">Live</span>
        {REAL_EXAMPLES.map(([name, about, href]) => <button type="button" className="text-button" key={href} title={about} aria-label={`Scan real page: ${about}`} disabled={busy} onClick={() => void scan(href)}>{name}</button>)}
      </div>
    </form>

    {error && <p role="alert" className="error-message">{error}</p>}
    {report && <section className="result" aria-live="polite">
      <div className={`verdict ${report.findings.length ? "" : "good"}`}>
        <h2>{report.findings.length ? `${report.findings.length} thing${report.findings.length > 1 ? "s" : ""} an agent could be tricked by` : "Nothing an agent would be tricked by"}</h2>
        <p>{report.title || report.final_url}</p>
        {report.final_url !== report.url && <p>Redirected to {report.final_url}</p>}
        <ul className="facts"><li>{report.element_count} elements</li><li>Checks {report.detector_ms} ms</li><li>Scan {(report.elapsed_ms / 1000).toFixed(1)} s</li>{report.blocked_requests > 0 && <li>{report.blocked_requests} requests blocked</li>}</ul>
      </div>
      <div className="scan-result">
        <article className="pane">
          <div className="pane-heading"><h3>First screen of {new URL(report.final_url).hostname}</h3><span>{boxes.length} boxed</span></div>
          <div className="browser-frame">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {report.screenshot_b64 && <img src={`data:image/jpeg;base64,${report.screenshot_b64}`} alt={`Screenshot of ${report.final_url}`} />}
            <svg className="highlight-layer" viewBox="0 0 1280 720" role="img" aria-label="Flagged page elements">{boxes.map((e) => {
              const [x, y, w, h] = e.bbox;
              return <g key={e.id}><rect x={x} y={y} width={w} height={h} /><text x={Math.max(2, Math.min(x, 1000))} y={Math.max(24, y - 8)}>{label(e.id)}</text></g>;
            })}</svg>
          </div>
          {report.flagged.length > boxes.length && <p className="event-meta">{report.flagged.length - boxes.length} flagged element(s) are below the first screen or have no visible box.</p>}
        </article>
        <article className="pane">
          <div className="pane-heading"><h3>Findings</h3><span>{report.findings.length}</span></div>
          <ol className="event-feed" aria-label="Findings">{report.findings.map((f, i) => <li key={i}>
            <span className={`event-kind kind-${f.severity === "high" ? "error" : "verdict"}`}>{f.severity}</span>
            <div><p><strong>{f.detector} · {f.trap_type}</strong><br />{f.evidence}</p>{f.suggestion && <p>{f.suggestion}</p>}</div>
          </li>)}{!report.findings.length && <li><p>No hidden instructions, fake controls, invisible overlays or pressure text found on this page.</p></li>}</ol>
        </article>
      </div>
      {report.notes.length > 0 && <details className="notes">
        <summary>{report.notes.length} hidden or faint text snippet(s): normal on most sites (screen-reader labels, menus, carousels)</summary>
        <ul>{report.notes.map((n, i) => <li key={i}>{n.evidence}</li>)}</ul>
      </details>}
    </section>}
  </>;
}
