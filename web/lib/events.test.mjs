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
    exports, EventSource, MessageEvent,
    require(name) {
      if (name === "./api") return { API_URL: "https://api.example" };
      if (name === "react") return {
        useState(initial) { state = initial; return [state, (update) => { state = update(state); }]; },
        useEffect(effect) { cleanup = effect(); },
      };
      throw new Error(`Unexpected import ${name}`);
    },
  });
  exports.useRunStream("sample");
  assert.equal(connections.length, 1);
  return { get state() { return state; }, get connection() { return connections[0]; }, cleanup: () => cleanup() };
}

test("one stream handles summary, ignores unknown names, and closes after both distinct sides finish", () => {
  const h = harness();
  assert.equal(h.connection.url, "https://api.example/runs/sample/stream");
  h.connection.emit("run", { run_id: "sample", is_sample: true, future_field: true });
  assert.equal(h.state.summary.is_sample, true);
  h.connection.emit("future_event", {});
  h.connection.emit("done", { run_id: "sample", kind: "done", mode: "unshielded", payload: {} }, "1");
  h.connection.emit("done", { run_id: "sample", kind: "done", mode: "unshielded", payload: {} }, "1");
  assert.equal(h.state.events.length, 1);
  assert.equal(h.connection.closed, false);
  h.connection.emit("done", { run_id: "sample", kind: "done", mode: "shielded", payload: {} }, "2");
  assert.equal(h.state.status, "complete");
  assert.equal(h.connection.closed, true);
});

test("application error events remain distinct from transport failures", () => {
  const h = harness();
  h.connection.emit("error", { run_id: "sample", kind: "error", mode: "shielded", payload: { message: "Example error" } });
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
  h.connection.emit("done", { run_id: "sample", kind: "done", mode: "unshielded", payload: {} }, "7");
  assert.equal(h.state.status, "streaming");
  for (let i = 0; i < 5; i += 1) h.connection.onerror({ type: "error" });
  assert.equal(h.state.status, "reconnecting");
  h.connection.onerror({ type: "error" });
  assert.equal(h.state.status, "error");
  assert.equal(h.connection.closed, true);
});

test("a mismatched run fails with a visible error", () => {
  const h = harness();
  h.connection.emit("run", { run_id: "other", is_sample: false });
  assert.equal(h.state.status, "error");
  assert.match(h.state.error, /invalid run summary/);
  assert.equal(h.connection.closed, true);
});

test("unmount closes the stream and ignores late events", () => {
  const h = harness();
  h.cleanup();
  h.connection.emit("done", { run_id: "sample", kind: "done", mode: "shielded", payload: {} });
  assert.equal(h.connection.closed, true);
  assert.equal(h.state.events.length, 0);
});
