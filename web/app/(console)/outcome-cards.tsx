import type { RunEvent, Schema } from "@/lib/api";
import { commitmentKey } from "@/lib/run-evidence";

type DoneEvent = Extract<RunEvent, { kind: "done" }>;

export function OutcomeCards({ events, summary }: { events: RunEvent[]; summary: Schema["RunSummary"] | null }) {
  const left = events.findLast((event): event is DoneEvent => event.kind === "done" && event.mode === "unshielded");
  const right = events.findLast((event): event is DoneEvent => event.kind === "done" && event.mode === "shielded");
  if (!left && !right) return null;
  return <section className="outcomes-section" aria-label="Final commitment comparison"><h2>{summary?.is_sample ? "Sample outcomes" : "Run outcomes"}</h2><div className="comparison-grid">{(["unshielded", "shielded"] as const).map((mode) => {
    const done = mode === "shielded" ? right : left;
    const other = mode === "shielded" ? left : right;
    const commitments = done?.payload.outcome.commitments ?? [];
    const otherKeys = new Set(other?.payload.outcome.commitments?.map(commitmentKey));
    return <article className="outcome-card" key={mode}><h3>{mode === "shielded" ? "With Aegis" : "Unprotected agent"}</h3>{done ? <>
      <strong className="outcome-total">{done.payload.outcome.total == null ? "Total unknown" : `₹${done.payload.outcome.total.toLocaleString("en-IN")}`}</strong>
      <p>{done.payload.outcome.task_completed === true ? "Task completed" : done.payload.outcome.task_completed === false ? "Task incomplete" : "Completion unknown"}</p>
      {done.payload.reason !== "completed" && <p className="outcome-reason">Stopped: {done.payload.reason.replaceAll("_", " ")}</p>}
      {(["proposed", "approved", "executed"] as const).map((state) => {
        const group = commitments.filter((item) => item.state === state);
        return group.length ? <div className="commitment-group" key={state}><h4>{state}</h4><ul>{group.map((item, index) => <li key={index} className={other && !otherKeys.has(commitmentKey(item)) ? "different-commitment" : undefined}>{item.description}{item.amount != null && ` · ₹${item.amount.toLocaleString("en-IN")}${item.period ? `/${item.period}` : ""}`}{other && !otherKeys.has(commitmentKey(item)) && <span className="difference-label">Only on this side</span>}</li>)}</ul></div> : null;
      })}
      {!commitments.length && <p>No commitments recorded.</p>}
    </> : <p>Waiting for this side to finish.</p>}</article>;
  })}</div></section>;
}
