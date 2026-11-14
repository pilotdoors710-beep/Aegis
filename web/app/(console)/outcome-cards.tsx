import AnimatedContent from "@/components/reactbits/AnimatedContent";
import Counter from "@/components/reactbits/Counter";
import ElectricBorder from "@/components/reactbits/ElectricBorder";
import type { RunEvent, Schema } from "@/lib/api";
import { type AskEvent, commitmentKey } from "@/lib/run-evidence";

type DoneEvent = Extract<RunEvent, { kind: "done" }>;
type Commitment = Schema["Commitment"];

const PERIOD_SHORT: Record<string, string> = { month: "mo", year: "yr" };
const rupees = (value: number) => `₹${value.toLocaleString("en-IN")}`;

// A recurring charge the agent actually took on (approved or executed, not merely proposed).
function recurringOf(commitments: Commitment[]) {
  return commitments.filter((item) => item.state !== "proposed" && (item.kind === "subscription" || item.period != null));
}

function recurringLabel(item: Commitment) {
  const period = item.period ? `/${PERIOD_SHORT[item.period] ?? item.period}` : "";
  return item.amount != null ? `${rupees(item.amount)}${period}, auto-renewing` : "Recurring charge, auto-renewing";
}

// One factual line built only from the two recorded outcomes.
function difference(left: DoneEvent, right: DoneEvent) {
  const [a, b] = [left.payload.outcome, right.payload.outcome];
  const parts: string[] = [];
  if (a.total != null && b.total != null && a.total !== b.total) parts.push(`${rupees(Math.abs(a.total - b.total))} ${a.total > b.total ? "more" : "less"} paid without Aegis`);
  else if ((a.total == null) !== (b.total == null)) parts.push(a.total == null ? "Only the protected agent paid" : "Only the unprotected agent paid");
  const [ra, rb] = [recurringOf(a.commitments ?? []).length, recurringOf(b.commitments ?? []).length];
  if (ra !== rb) parts.push(`${ra} recurring charge${ra === 1 ? "" : "s"} without Aegis, ${rb} with`);
  if (parts.length) return parts.join(" · ");
  const keys = (list: Commitment[] | undefined) => (list ?? []).map(commitmentKey).sort().join("|");
  return keys(a.commitments) === keys(b.commitments) ? "Both agents ended with the same total and commitments." : "Same total; the commitments differ below.";
}

export function OutcomeCards({ events, summary }: { events: RunEvent[]; summary: Schema["RunSummary"] | null }) {
  const left = events.findLast((event): event is DoneEvent => event.kind === "done" && event.mode === "unshielded");
  const right = events.findLast((event): event is DoneEvent => event.kind === "done" && event.mode === "shielded");
  // Keep both browser panes in place while either agent is still streaming.
  if (!left || !right) return null;
  return <section className="outcomes-section" aria-label="Final commitment comparison">
    <div className="section-heading"><h2>{summary?.is_sample ? "Sample outcomes" : "Run outcomes"}</h2><span className="outcome-difference">{difference(left, right)}</span></div>
    <AnimatedContent className="comparison-grid" trigger="mount" distance={28} duration={0.6} stagger={0.12}>{(["unshielded", "shielded"] as const).map((mode) => {
      const done = mode === "shielded" ? right : left;
      const other = mode === "shielded" ? left : right;
      const commitments = done.payload.outcome.commitments ?? [];
      const otherKeys = new Set(other.payload.outcome.commitments?.map(commitmentKey));
      const recurring = recurringOf(commitments);
      // The server ends a run "denied" when an approval request times out; say which it was.
      const lastAsk = events.findLast((event): event is AskEvent => event.kind === "ask" && event.mode === mode)?.payload;
      const timedOut = done.payload.reason === "denied" && lastAsk?.status === "timed_out";
      const cloakedDenied = done.payload.reason === "denied" && lastAsk?.reason === "cloaked_checkout" && lastAsk.status === "denied";
      const placed = done.payload.outcome.task_completed === true;
      const total = done.payload.outcome.total;
      return <article className="outcome-card" data-mode={mode} key={mode}><h3>{mode === "shielded" ? "With Aegis" : "Unprotected agent"}</h3>
        <strong className="outcome-total">{total != null ? <Counter value={total} locale="en-IN" prefix="₹" fontSize={44} fontWeight={600} duration={0.9} /> : placed ? "Total unknown" : "Nothing paid"}</strong>
        {recurring.length ? recurring.map((item, index) => {
          const only = !otherKeys.has(commitmentKey(item));
          const line = <p className={`outcome-recurring${only ? " outcome-recurring-only" : ""}`}>+ {recurringLabel(item)}<span>{item.description.split(" · ")[0]}{only && " · only on this side"}</span></p>;
          // Arcs mark a recurring charge that only this side took on.
          return only ? <ElectricBorder key={index} className="outcome-arc" color="#ff6b5e" borderRadius={8} thickness={1.5} speed={0.8} chaos={0.5} interactive={false}>{line}</ElectricBorder> : <div key={index} className="outcome-arc">{line}</div>;
        }) : <p className="outcome-no-recurring">No recurring charges</p>}
        <p>{done.payload.outcome.task_completed === true ? "Task completed" : done.payload.outcome.task_completed === false ? "Task incomplete" : "Completion unknown"}</p>
        {done.payload.reason !== "completed" && <p className="outcome-reason">{timedOut ? "Stopped: approval timed out. Nobody approved in time, so no order was placed." : cloakedDenied ? "Stopped before payment: this site showed the agent a different checkout than an ordinary browser, and you denied it." : `Stopped: ${done.payload.reason.replaceAll("_", " ")}`}</p>}
        {(["proposed", "approved", "executed"] as const).map((state) => {
          const group = commitments.filter((item) => item.state === state);
          return group.length ? <div className="commitment-group" key={state}><h4>{state}</h4><ul>{group.map((item, index) => <li key={index} className={!otherKeys.has(commitmentKey(item)) ? "different-commitment" : undefined}>{item.description}{item.amount != null && ` · ${rupees(item.amount)}${item.period ? `/${item.period}` : ""}`}{!otherKeys.has(commitmentKey(item)) && <span className="difference-label">Only on this side</span>}</li>)}</ul></div> : null;
        })}
        {!commitments.length && <p>No commitments recorded.</p>}
      </article>;
    })}</AnimatedContent>
  </section>;
}
