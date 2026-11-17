"use client";

import { FormEvent, useRef, useState } from "react";
import { api, type Schema } from "@/lib/api";
import styles from "./sybil.module.css";

type Evidence = Schema["SybilRealDomainEvidence"];

// One that passes, a big shop that doesn't, a small shop, one outside the sample, a platform seller.
const EXAMPLES = ["techcrunch.com", "ebay.com", "anotherbikeshop.com", "ikea.com", "gadgets.myshopify.com"];

const STATUS: Record<Evidence["status"], string> = {
  scored: "In the sample",
  anchor: "Trusted starting site",
  not_in_sample: "Not in the sample",
  shared_platform: "Shared platform seller",
  unavailable: "Could not score",
};

const pct = (v: number) => `${Math.round(v * 100)}%`;

export function RealSiteCheck() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<Evidence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const latest = useRef(0);

  async function check(value: string) {
    const q = value.trim();
    if (!q) return;
    const ticket = ++latest.current;
    setQuery(q);
    setBusy(true);
    setError(null);
    try {
      const evidence = await api.sybilRealEvaluate({ query: q, max_paths: 3 });
      if (ticket === latest.current) setResult(evidence);
    } catch (e) {
      if (ticket === latest.current) {
        setResult(null);
        setError(e instanceof Error ? e.message : "The check failed.");
      }
    } finally {
      if (ticket === latest.current) setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void check(query);
  }

  const score = result?.scores;
  return (
    <section className={styles.stage4Section} aria-labelledby="real-site-title">
      <div className={styles.stage4Header}>
        <div>
          <h2 id="real-site-title">Check a real website</h2>
        </div>
        {busy && <span className={styles.stage4Meta}>Checking…</span>}
      </div>

      <div className={styles.stage4Grid}>
        <div className={styles.stage4Card}>
          <form className={styles.controls} onSubmit={submit}>
            <label>
              Website
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="example.com"
                maxLength={2048}
                spellCheck={false}
                autoCapitalize="off"
              />
            </label>
            <div className={styles.actions}>
              <button className="primary-button" disabled={busy || !query.trim()}>
                Check
              </button>
            </div>
          </form>
          <div>
            <span className={styles.stage4Meta}>Examples</span>
            <div className={styles.actions}>
              {EXAMPLES.map((example) => (
                <button key={example} className="secondary-button" disabled={busy} onClick={() => void check(example)}>
                  {example}
                </button>
              ))}
            </div>
          </div>
          {error && (
            <p className={styles.alert} role="alert">
              {error}
            </p>
          )}
        </div>

        <div className={styles.stage4Card} aria-live="polite">
          {result ? (
            <>
              <div>
                <h3>
                  {result.domain ?? result.host}
                  <span className={result.policy_passed ? styles.passBadge : styles.cutEdgeBadge}>
                    {result.policy_passed ? "Agent goes ahead" : "Agent asks first"}
                  </span>
                </h3>
                <p className={styles.stage4Meta}>
                  {STATUS[result.status]}
                  {result.domain && result.domain !== result.host && ` · ${result.host} matched to ${result.domain}`}
                </p>
              </div>
              <p>{result.reason}</p>
              {score && (
                <dl className={styles.facts}>
                  <div>
                    <dt>Score</dt>
                    <dd>
                      <strong>{score.total_robustness.toFixed(1)}</strong> / 100
                    </dd>
                  </div>
                  <div>
                    <dt>Trust</dt>
                    <dd>{pct(score.structural_support)}</dd>
                  </div>
                  <div>
                    <dt>Spread</dt>
                    <dd>{pct(score.anchor_breadth)}</dd>
                  </div>
                  <div>
                    <dt>Without top trusted site</dt>
                    <dd>{pct(score.anchor_withdrawal_resilience)}</dd>
                  </div>
                  <div>
                    <dt>After cutting top links</dt>
                    <dd>{pct(score.tested_connection_resilience)}</dd>
                  </div>
                  <div>
                    <dt>Sites linking to it</dt>
                    <dd>{result.links_in.toLocaleString()}</dd>
                  </div>
                </dl>
              )}
              {result.anchor_paths.length > 0 && (
                <div>
                  <span className={styles.stage4Meta}>Links from trusted sites</span>
                  <ol className={styles.trajectoryList}>
                    {result.anchor_paths.map((path) => (
                      <li key={path.anchor}>{path.hops.join(" → ")}</li>
                    ))}
                  </ol>
                </div>
              )}
              {result.top_linkers.length > 0 && (
                <p className={styles.stage4Meta}>Most trust from: {result.top_linkers.join(", ")}</p>
              )}
              <p className={styles.disclosure}>{result.disclosure}</p>
            </>
          ) : (
            <p className={styles.stage4Meta}>Pick an example or type a site.</p>
          )}
        </div>
      </div>
    </section>
  );
}
