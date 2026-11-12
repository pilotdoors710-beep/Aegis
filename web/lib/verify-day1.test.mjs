import { test } from "node:test";
import assert from "node:assert/strict";
import { checkSampleStream } from "./verify-day1.mjs";

// Synthetic transport fixtures test the verifier; these are not real run evidence.
function sampleFrames() {
  const events = ["snapshot", "decision", "verdict", "executed", "ask", "error", "done", "done"];
  return `: heartbeat\r\n\r\nevent: run\r\ndata: ${JSON.stringify({ run_id: "sample", is_sample: true })}\r\n\r\n` + events.map((kind, index) =>
    `event: ${kind}\r\nid: ${index + 1}\r\ndata: ${JSON.stringify({ run_id: "sample", kind, mode: index === 6 ? "unshielded" : "shielded", payload: { text: "₹1,299" } })}\r\n\r\n`,
  ).join("");
}

function response(text) {
  const bytes = new TextEncoder().encode(text);
  return new Response(new ReadableStream({
    start(controller) {
      // Force framing and multibyte characters to cross arbitrary chunk boundaries.
      for (let i = 0; i < bytes.length; i += 7) controller.enqueue(bytes.slice(i, i + 7));
      controller.close();
    },
  }), { headers: { "Content-Type": "text/event-stream" } });
}

test("deployment verifier accepts chunked CRLF SSE with both completed sides", async () => {
  const result = await checkSampleStream(response(sampleFrames()), AbortSignal.timeout(1000));
  assert.equal(result.events, 8);
});

test("deployment verifier rejects an unlabelled sample", async () => {
  await assert.rejects(checkSampleStream(response(sampleFrames().replace('"is_sample":true', '"is_sample":false')), AbortSignal.timeout(1000)), /Sample must be labelled/);
});

test("deployment verifier rejects a stream that ends before both sides finish", async () => {
  await assert.rejects(checkSampleStream(response(sampleFrames().replace('"mode":"unshielded"', '"mode":"shielded"')), AbortSignal.timeout(1000)), /before both sides finished/);
});
