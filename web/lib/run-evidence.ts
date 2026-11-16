import type { RunEvent, Schema } from "./api";

export type AskEvent = Extract<RunEvent, { kind: "ask" }>;
export type VerdictEvent = Extract<RunEvent, { kind: "verdict" }>;

export const approvalLabels: Record<Schema["AskPayload"]["status"], string> = {
  pending: "Awaiting your decision",
  approved: "Approved by a person",
  denied: "Denied",
  timed_out: "Timed out · not approved",
  auto_approved_demo: "Simulated demo approval · not human consent",
};

export function latestAsks(events: RunEvent[]): AskEvent[] {
  const asks = new Map<string, AskEvent>();
  for (const event of events) {
    if (event.kind === "ask" && event.mode === "shielded") asks.set(event.payload.ask_id, event);
  }
  return [...asks.values()];
}

export function pendingAsk(events: RunEvent[]): AskEvent | undefined {
  if (events.some((event) => event.kind === "done" && event.mode === "shielded")) return undefined;
  return latestAsks(events).find((event) => event.payload.status === "pending");
}

type DecisionEvent = Extract<RunEvent, { kind: "decision" }>;
type Correction = { correction?: DecisionEvent; correctionExecuted: boolean };

/** The server names the audit step each correction answers (`correcting`). */
function linkedCorrection(side: RunEvent[], step: number): Correction {
  const decisions = side.filter((next): next is DecisionEvent => next.kind === "decision" && next.payload.correcting === step);
  return {
    correction: decisions.at(-1), // the attempt that was finally allowed, if any
    correctionExecuted: side.some((next) => next.kind === "executed" && next.payload.correcting === step && next.payload.ok),
  };
}

/** Replays recorded before `correcting` existed: the first retry before the recheck. */
function guessedCorrection(later: RunEvent[], recheck: VerdictEvent | undefined): Correction {
  const beforeRecheck = recheck ? later.slice(0, later.indexOf(recheck)) : later;
  const correction = beforeRecheck.find((next): next is DecisionEvent => next.kind === "decision" && (next.payload.attempt ?? 1) > 1);
  const executed = correction && beforeRecheck.slice(beforeRecheck.indexOf(correction) + 1).find((next) => next.kind === "executed" && next.step === correction.step && next.payload.ok && next.payload.action.type === correction.payload.action.type && next.payload.action.target_id === correction.payload.action.target_id && next.payload.action.text === correction.payload.action.text && next.payload.action.url === correction.payload.action.url);
  return { correction, correctionExecuted: Boolean(executed) };
}

export function auditEvidence(events: RunEvent[]) {
  const side = events.filter((event) => event.mode === "shielded");
  const linked = side.some((event) => event.kind === "decision" && "correcting" in event.payload);
  return side.flatMap((event, index) => {
    if (event.kind !== "verdict" || !event.payload.audit) return [];
    // Rechecks appear on their original card. Do not turn them into another violation.
    const report = event.payload.audit;
    return report.checks.filter((check) => report.recheck_of == null || check.status === "permitted").map((check, checkIndex) => {
      const later = side.slice(index + 1);
      const recheck = later.find((next): next is VerdictEvent => next.kind === "verdict" && next.payload.audit?.recheck_of === event.step);
      const { correction, correctionExecuted } = linked ? linkedCorrection(side, event.step) : guessedCorrection(later, recheck);
      return {
        key: `${index}:${checkIndex}`, event, check, correction, correctionExecuted,
        recheck: recheck?.payload.audit?.checks.find((next) => next.constraint === check.constraint),
        recheckStep: recheck?.step,
      };
    });
  });
}

export function commitmentKey(item: Schema["Commitment"]): string {
  return JSON.stringify([item.kind, item.description, item.amount ?? null, item.period ?? null, item.state]);
}
