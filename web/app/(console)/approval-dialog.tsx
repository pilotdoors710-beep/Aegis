"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Schema } from "@/lib/api";
import { type AskEvent } from "@/lib/run-evidence";
import { TwoView } from "./evidence-cards";

export function ApprovalDialog({ ask, sample, connected }: { ask: AskEvent; sample: boolean; connected: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const deny = useRef<HTMLButtonElement>(null);
  const submitting = useRef(false);
  const [busy, setBusy] = useState(false);
  const [acknowledged, setAcknowledged] = useState<Schema["AskPayload"]["status"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    deny.current?.focus({ preventScroll: true });
    if (element) element.scrollTop = 0; // open on the evidence, not on the buttons
    return () => element?.close();
  }, []);

  async function decide(decision: "approve" | "deny") {
    if (sample || !connected || submitting.current || acknowledged) return;
    submitting.current = true;
    setBusy(true); setError(null);
    try {
      const result = await api.resolveAsk(ask.run_id, ask.payload.ask_id, { decision });
      setAcknowledged(result.status);
      dialog.current?.close(); // the server accepted the decision; don't wait on the stream to close
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not send your decision.");
    } finally { submitting.current = false; setBusy(false); }
  }

  const action = ask.payload.action;
  const cloaked = ask.payload.reason === "cloaked_checkout";
  return <dialog ref={dialog} className={`approval-dialog${cloaked ? " approval-wide" : ""}`} aria-labelledby="approval-title" aria-describedby="approval-context" onCancel={(event) => event.preventDefault()}>
    <p className="eyebrow">{sample ? "SAMPLE APPROVAL" : "ACTION PAUSED"}</p>
    <h2 id="approval-title">{cloaked ? "The agent was shown a different checkout" : "Review the agent’s next action"}</h2>
    <p id="approval-context">{sample ? "Recorded sample: these controls cannot grant permission. The sample will continue on its own." : "The agent is waiting. Your response applies to this action; the server checks the page again before execution."}</p>
    <dl className="approval-action"><div><dt>Reason</dt><dd>{ask.payload.reason.replaceAll("_", " ")}</dd></div><div><dt>Action</dt><dd>{action ? `${action.type} ${action.text || action.url || action.target_id || ""}` : "No executable action supplied"}</dd></div></dl>
    {action?.rationale && <p>{action.rationale}</p>}
    <TwoView report={ask.payload.two_view} />
    {/* A cloaked checkout passed every check on the agent's view; the two views are the evidence. */}
    {!cloaked && <div className="approval-evidence">
      {ask.payload.findings?.map((finding, index) => <p key={index}><strong>{finding.detector} · {finding.trap_type}</strong><br />{finding.evidence}</p>)}
      {ask.payload.audit?.checks.map((check, index) => <article key={index} className={`audit-check check-${check.status}`}><strong>{check.status === "permitted" ? "Permitted by your request" : check.status === "uncertain" ? "Needs a human decision" : check.status}</strong><p>{check.constraint}: {check.evidence}</p><p>Your request: {check.ledger_value}</p><p>Observed: {check.observed_value}</p></article>)}
    </div>}
    {!connected && <p role="alert">The live connection is unavailable. Reconnect before responding; no approval has been sent.</p>}
    {error && <p className="error-message" role="alert">{error} You can retry while this request remains pending.</p>}
    <div className="approval-buttons"><button ref={deny} disabled={sample || !connected || busy || acknowledged !== null} onClick={() => decide("deny")}>Deny</button><button className="primary-button" disabled={sample || !connected || busy || acknowledged !== null} onClick={() => decide("approve")}>{busy ? "Sending…" : cloaked ? "Pay anyway" : "Approve"}</button></div>
  </dialog>;
}
