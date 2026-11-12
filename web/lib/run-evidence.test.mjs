import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const source = ts.transpileModule(readFileSync(new URL("./run-evidence.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const helpers = {};
vm.runInNewContext(source, { exports: helpers });
const ask = (id, status, mode = "shielded") => ({ kind: "ask", mode, step: 5, payload: { ask_id: id, status } });
const check = (status) => ({ constraint: "allow_addons", status, ledger_value: "false", observed_value: "Annual plan selected", evidence: "Plan costs 299 per year" });
const action = { type: "click", target_id: "e31", rationale: "Clear annual protection" };
const verdict = (step, status, recheck_of = null) => ({ kind: "verdict", mode: "shielded", step, payload: { verdict: { decision: status === "violation" ? "REROUTE" : "ASK" }, audit: { recheck_of, checks: [check(status)] } } });

test("resolved and timed-out requests cannot reopen an approval; unshielded asks are ignored", () => {
  for (const status of ["approved", "denied", "timed_out", "auto_approved_demo"]) {
    const events = [ask("a", "pending"), ask("a", status), ask("b", "pending", "unshielded")];
    assert.equal(helpers.pendingAsk(events), undefined);
    assert.equal(helpers.latestAsks(events).length, 1);
    assert.equal(helpers.latestAsks(events)[0].payload.status, status);
  }
});

test("each request has its own state and a finished shielded side has no pending consent", () => {
  const events = [ask("old", "pending"), ask("old", "denied"), ask("new", "pending")];
  assert.equal(helpers.pendingAsk(events).payload.ask_id, "new");
  assert.equal(helpers.pendingAsk([...events, { kind: "done", mode: "shielded", payload: {} }]), undefined);
});

test("evidence links retry proposal, execution and only an explicitly linked recheck", () => {
  const events = [verdict(4, "violation"), { kind: "decision", mode: "shielded", step: 4, payload: { attempt: 2, action } }, { kind: "executed", mode: "shielded", step: 4, payload: { action, ok: true } }, verdict(5, "ok", 4)];
  const card = helpers.auditEvidence(events)[0];
  assert.equal(card.correction.payload.action.rationale, action.rationale);
  assert.equal(card.correctionExecuted, true);
  assert.equal(card.recheck.status, "ok");
  assert.equal(card.recheckStep, 5);
  assert.equal(helpers.auditEvidence([verdict(4, "violation"), verdict(5, "ok", 99)])[0].recheck, undefined);
});

test("proposed or failed corrections never become executed; unrelated actions are not corrections", () => {
  const decision = { kind: "decision", mode: "shielded", step: 4, payload: { attempt: 2, action } };
  const failed = { kind: "executed", mode: "shielded", step: 4, payload: { action, ok: false } };
  assert.equal(helpers.auditEvidence([verdict(4, "violation"), decision, failed])[0].correctionExecuted, false);
  assert.equal(helpers.auditEvidence([verdict(4, "violation"), decision, { ...failed, step: 5, payload: { action, ok: true } }])[0].correctionExecuted, false);
  assert.equal(helpers.auditEvidence([verdict(4, "violation"), { ...decision, payload: { attempt: 1, action } }])[0].correction, undefined);
});

test("permitted and uncertain checks retain the server's meaning; commitment states stay distinct", () => {
  assert.equal(helpers.auditEvidence([verdict(1, "permitted")])[0].check.status, "permitted");
  assert.equal(helpers.auditEvidence([verdict(1, "uncertain")])[0].check.status, "uncertain");
  const item = { kind: "addon", description: "Annual protection", amount: 299 };
  assert.notEqual(helpers.commitmentKey({ ...item, state: "proposed" }), helpers.commitmentKey({ ...item, state: "executed" }));
  assert.match(helpers.approvalLabels.auto_approved_demo, /not human consent/);
});
