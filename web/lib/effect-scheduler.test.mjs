import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const source = ts.transpileModule(readFileSync(new URL("./effect-scheduler.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function harness() {
  const frames = new Map(), listeners = new Map();
  let sequence = 0;
  const exports = {};
  vm.runInNewContext(source, {
    exports,
    requestAnimationFrame(callback) { frames.set(++sequence, callback); return sequence; },
    cancelAnimationFrame(id) { frames.delete(id); },
    window: {
      addEventListener(type, callback) {
        assert.equal(listeners.has(type), false, "only one native listener per event");
        listeners.set(type, callback);
      },
      removeEventListener(type, callback) {
        assert.equal(listeners.get(type), callback); listeners.delete(type);
      },
    },
  });
  return { ...exports, frames, listeners,
    flush() { for (const [id, callback] of [...frames]) { frames.delete(id); callback(100); } } };
}

test("multiple effects measure before any paint, and next-frame work stays deferred", () => {
  const h = harness(), actions = [];
  h.requestEffectFrame(() => { actions.push("read A"); return () => actions.push("paint A"); });
  h.requestEffectFrame(() => {
    actions.push("read B");
    h.requestEffectFrame(() => { actions.push("next frame"); });
    return () => actions.push("paint B");
  });
  assert.equal(h.frames.size, 1);
  h.flush();
  assert.deepEqual(actions, ["read A", "read B", "paint A", "paint B"]);
  h.flush();
  assert.equal(actions.at(-1), "next frame");
});

test("cleanup cancels frames and releases shared pointer listeners after the last card", () => {
  const h = harness(), calls = [];
  const id = h.requestEffectFrame(() => { assert.fail("unmounted effect ran"); });
  h.cancelEffectFrame(id);
  assert.equal(h.frames.size, 0);
  const stopA = h.followEffectEvent("pointermove", () => calls.push("A"));
  const stopB = h.followEffectEvent("pointermove", () => calls.push("B"));
  h.listeners.get("pointermove")({});
  stopA();
  h.listeners.get("pointermove")({});
  assert.deepEqual(calls, ["A", "B", "B"]);
  stopB();
  assert.equal(h.listeners.size, 0);
});
