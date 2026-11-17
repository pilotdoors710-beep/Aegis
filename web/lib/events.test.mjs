import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

// Exercise the hook's transport lifecycle without a browser or a second schema.
const source = ts.transpileModule(readFileSync(new URL("./events.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function harness() {
  let state;
  let cleanup;
  let updates = 0;
  let sequence = 0;
  const frames = new Map();
  const listeners = new Map();
  const document = { hidden: false,
    addEventListener(type, callback) { listeners.set(type, callback); },
    removeEventListener(type) { listeners.delete(type); },
    dispatchEvent(event) { listeners.get(event.type)?.(event); },
  };
  const connections = [];
  class MessageEvent {
    constructor(data, lastEventId = "") { this.data = JSON.stringify(data); this.lastEventId = lastEventId; }
  }
  class EventSource {
    listeners = new Map();
    closed = false;
    readyState = 1;
    constructor(url) { this.url = url; connections.push(this); }
    addEventListener(name, callback) { this.listeners.set(name, callback); }
    close() { this.closed = true; }
    emit(name, data, id = "") {
      const event = new MessageEvent(data, id);
      this.listeners.get(name)?.(event);
      if (name === "error") this.onerror?.(event);
    }
  }
  const exports = {};
  vm.runInNewContext(source, {
    exports, EventSource, MessageEvent, document,
    requestAnimationFrame(callback) { frames.set(++sequence, callback); return sequence; },
    cancelAnimationFrame(id) { frames.delete(id); },
    require(name) {
      if (name === "./api") return { API_URL: "https://api.example" };
      if (name === "react") return {
        useState(initial) { state = initial; return [state, (update) => { updates++; state = update(state); }]; },
        useEffect(effect) { cleanup = effect(); },
      };
      throw new Error(`Unexpected import ${name}`);
    },
  });
  exports.useRunStream("run-1");
  assert.equal(connections.length, 1);
  return { get state() { return state; }, get updates() { return updates; }, document,
    get connection() { return connections[0]; }, cleanup: () => cleanup(),
    flush() { for (const [id, callback] of [...frames]) { frames.delete(id); callback(); } } };
}

test("bursts render once per frame, preserving order and reconnect deduplication", () => {
  const h = harness();
  for (let i = 0; i < 100; i++) {
    const event = { run_id: "run-1", kind: "snapshot", mode: "shielded", step: i, payload: {} };
    h.connection.emit("snapshot", event, String(i));
    h.connection.emit("snapshot", event, String(i));
  }
  assert.equal(h.state.events.length, 0);
  h.flush();
  assert.equal(h.updates, 1);
  assert.deepEqual(Array.from(h.state.events, e => e.step), Array.from({length: 100}, (_, i) => i));
});

test("approval and transport failure flush older pending events immediately", () => {
  const h = harness();
  h.connection.emit("snapshot", { run_id: "run-1", kind: "snapshot", mode: "shielded", payload: {} }, "1");
  h.connection.emit("ask", { run_id: "run-1", kind: "ask", mode: "shielded", payload: {} }, "2");
  assert.deepEqual(Array.from(h.state.events, e => e.kind), ["snapshot", "ask"]);
  h.connection.emit("decision", { run_id: "run-1", kind: "decision", mode: "shielded", payload: {} }, "3");
  h.connection.readyState = 2;
  h.connection.onerror({type: "error"});
  assert.equal(h.state.events.length, 3);
  assert.equal(h.state.status, "error");
  h.flush();
  assert.equal(h.state.status, "error");
});

test("hidden tabs flush events immediately and unmount cancels pending batches", () => {
  const h = harness();
  h.connection.emit("snapshot", { run_id: "run-1", kind: "snapshot", mode: "shielded", payload: {} });
  h.document.hidden = true;
  h.document.dispatchEvent({type: "visibilitychange"});
  assert.equal(h.state.events.length, 1);
  h.connection.emit("snapshot", { run_id: "run-1", kind: "snapshot", mode: "shielded", payload: {} });
  assert.equal(h.state.events.length, 2);
  h.document.hidden = false;
  h.connection.emit("snapshot", { run_id: "run-1", kind: "snapshot", mode: "shielded", payload: {} });
  h.cleanup(); h.flush();
  assert.equal(h.state.events.length, 2);
});

test("one stream handles summary, ignores unknown names, and closes after both distinct sides finish", () => {
  const h = harness();
  assert.equal(h.connection.url, "https://api.example/runs/run-1/stream");
  h.connection.emit("run", { run_id: "run-1", status: "running", future_field: true });
  assert.equal(h.state.summary.status, "running");
  h.connection.emit("future_event", {});
  h.connection.emit("done", { run_id: "run-1", kind: "done", mode: "unshielded", payload: {} }, "1");
  h.connection.emit("done", { run_id: "run-1", kind: "done", mode: "unshielded", payload: {} }, "1");
  assert.equal(h.state.events.length, 1);
  assert.equal(h.connection.closed, false);
  h.connection.emit("done", { run_id: "run-1", kind: "done", mode: "shielded", payload: {} }, "2");
  assert.equal(h.state.status, "complete");
  assert.equal(h.connection.closed, true);
});

test("application error events remain distinct from transport failures", () => {
  const h = harness();
  h.connection.emit("error", { run_id: "run-1", kind: "error", mode: "shielded", payload: { message: "Example error" } });
  assert.equal(h.state.events.length, 1);
  assert.equal(h.connection.closed, false);
  h.connection.readyState = 2; // the browser gave up (e.g. an HTTP error response)
  h.connection.onerror({ type: "error" });
  assert.equal(h.state.status, "error");
  assert.equal(h.connection.closed, true);
});

test("a dropped connection is retried, resumes on the next frame, and fails after repeated drops", () => {
  const h = harness();
  h.connection.readyState = 0; // the browser is reconnecting with Last-Event-ID
  h.connection.onerror({ type: "error" });
  assert.equal(h.state.status, "reconnecting");
  assert.equal(h.connection.closed, false);
  h.connection.emit("done", { run_id: "run-1", kind: "done", mode: "unshielded", payload: {} }, "7");
  assert.equal(h.state.status, "streaming");
  for (let i = 0; i < 5; i += 1) h.connection.onerror({ type: "error" });
  assert.equal(h.state.status, "reconnecting");
  h.connection.onerror({ type: "error" });
  assert.equal(h.state.status, "error");
  assert.equal(h.connection.closed, true);
});

test("a mismatched run fails with a visible error", () => {
  const h = harness();
  h.connection.emit("run", { run_id: "other", status: "running" });
  assert.equal(h.state.status, "error");
  assert.match(h.state.error, /invalid run summary/);
  assert.equal(h.connection.closed, true);
});

test("unmount closes the stream and ignores late events", () => {
  const h = harness();
  h.cleanup();
  h.connection.emit("done", { run_id: "run-1", kind: "done", mode: "shielded", payload: {} });
  assert.equal(h.connection.closed, true);
  assert.equal(h.state.events.length, 0);
});
