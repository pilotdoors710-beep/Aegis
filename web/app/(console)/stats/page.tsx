"use client";

import { useEffect, useState } from "react";
import { api, type Schema } from "@/lib/api";

export default function StatsPage() {
  const [stats, setStats] = useState<Schema["EvalStats"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api.stats(controller.signal).then(setStats).catch((error: Error) => {
      if (!controller.signal.aborted) setError(error.message);
    });
    return () => controller.abort();
  }, []);
  const ratio = (value: Schema["Count"]) => `${value.count} / ${value.of}`;
  return <>
    <div className="console-intro"><div><p className="eyebrow">EVALUATION</p><h1>Measured outcomes</h1><p>Counts and denominators stay visible alongside each configuration.</p></div></div>
    {error && <p role="alert" className="error-message">Could not load statistics: {error}</p>}
    {!stats && !error && <p role="status">Loading evaluation data…</p>}
    {stats && <><div className="sample-banner"><strong className="badge">{stats.label === "sample" ? "SAMPLE DATA" : stats.label.toUpperCase()}</strong><span>{stats.label === "sample" ? "Illustrative values only. These are not measured Aegis results." : `Generated ${stats.generated_at}`} · N={stats.n} · {stats.model ?? "Model not specified"}</span></div>
      <div className="table-scroll"><table><caption>U: unprotected · F: detectors and filtering · I: full Aegis</caption><thead><tr><th>Configuration</th><th>Runs</th><th>Task completed</th><th>Safe completion</th><th>Unauthorized commitments</th><th>Clean false blocks</th><th>Detector median</th></tr></thead><tbody>{stats.configs.map((config) => <tr key={config.config}><th>{config.config}</th><td>{config.runs}</td><td>{ratio(config.task_success)}</td><td>{ratio(config.safe_task_completion)}</td><td>{ratio(config.unauthorized_commitments)}</td><td>{ratio(config.clean_false_block)}</td><td>{config.fast_detector_ms_median == null ? "Not reported" : `${config.fast_detector_ms_median} ms`}</td></tr>)}</tbody></table></div>
    </>}
  </>;
}
