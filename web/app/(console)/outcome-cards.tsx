import type { RunEvent, Schema } from "@/lib/api";
import { type AskEvent, commitmentKey } from "@/lib/run-evidence";

type DoneEvent = Extract<RunEvent, { kind: "done" }>;
type Commitment = Schema["Commitment"];

const PERIOD_SHORT: Record<string, string> = { month: "mo", year: "yr" };

// A recurring charge the agent actually took on (approved or executed, not merely proposed).
function recurringOf(commitments: Commitment[]) {
  return commitments.filter((item) => item.state !== "proposed" && (item.kind === "subscription" || item.period != null));
}

function recurringLabel(item: Commitment) {
  const period = item.period ? `/${PERIOD_SHORT[item.period] ?? item.period}` : "";
  return item.amount != null ? `₹${item.amount.toLocaleString("en-IN")}${period}, auto-renewing` : "Recurring charge, auto-renewing";
}

export function OutcomeCards({ events, summary }: { events: RunEvent[]; summary: Schema["RunSummary"] | null }) {
  const left = events.findLast((event): event is DoneEvent => event.kind === "done" && event.mode === "unshielded");
  const right = events.findLast((event): event is DoneEvent => event.kind === "done" && event.mode === "shielded");
  // Keep both browser panes in place while either agent is still streaming.
  if (!left || !right) return null;
  return <section className="outcomes-section" aria-label="Final commitment comparison"><h2>{summary?.is_sample ? "Sample outcomes" : "Run outcomes"}</h2><div className="comparison-grid">{(["unshielded", "shielded"] as const).map((mode) => {
    const done = mode === "shielded" ? right : left;
    const other = mode === "shielded" ? left : right;
    const commitments = done?.payload.outcome.commitments ?? [];
    const otherKeys = new Set(other?.payload.outcome.commitments?.map(commitmentKey));
    const recurring = recurringOf(commitments);
    // The server ends a run "denied" when an approval request times out; say which it was.
    const timedOut = done.payload.reason === "denied" && events.findLast((event): event is AskEvent => event.kind === "ask" && event.mode === mode)?.payload.status === "timed_out";
    return <article className="outcome-card" key={mode}><h3>{mode === "shielded" ? "With Aegis" : "Unprotected agent"}</h3>{done ? <>
      <strong className="outcome-total">{done.payload.outcome.total == null ? (timedOut ? "No order" : "Total unknown") : `₹${done.payload.outcome.total.toLocaleString("en-IN")}`}</strong>
      {recurring.length ? recurring.map((item, index) => <p key={index} className={`outcome-recurring${otherKeys.has(commitmentKey(item)) ? "" : " outcome-recurring-only"}`}>+ {recurringLabel(item)}<span>{item.description.split(" · ")[0]}</span></p>) : <p className="outcome-no-recurring">No recurring charges</p>}
      <p>{done.payload.outcome.task_completed === true ? "Task completed" : done.payload.outcome.task_completed === false ? "Task incomplete" : "Completion unknown"}</p>
      {done.payload.reason !== "completed" && <p className="outcome-reason">{timedOut ? "Stopped: approval timed out. Nobody approved in time, so no order was placed." : `Stopped: ${done.payload.reason.replaceAll("_", " ")}`}</p>}
      {(["proposed", "approved", "executed"] as const).map((state) => {
        const group = commitments.filter((item) => item.state === state);
        return group.length ? <div className="commitment-group" key={state}><h4>{state}</h4><ul>{group.map((item, index) => <li key={index} className={other && !otherKeys.has(commitmentKey(item)) ? "different-commitment" : undefined}>{item.description}{item.amount != null && ` · ₹${item.amount.toLocaleString("en-IN")}${item.period ? `/${item.period}` : ""}`}{other && !otherKeys.has(commitmentKey(item)) && <span className="difference-label">Only on this side</span>}</li>)}</ul></div> : null;
      })}
      {!commitments.length && <p>No commitments recorded.</p>}
    </> : <p>Waiting for this side to finish.</p>}</article>;
  })}</div></section>;
}
