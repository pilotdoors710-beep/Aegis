import assert from "node:assert/strict";
import { parseArgs } from "node:util";
import { pathToFileURL } from "node:url";

export async function checkSampleStream(response, signal) {
  assert.match(response.headers.get("content-type") ?? "", /text\/event-stream/);
  assert.ok(response.body, "Missing stream body");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const finished = new Set();
  const kinds = new Set();
  const ids = new Set();
  let pending = "";
  let summarySeen = false;
  const started = performance.now();
  try {
    while (finished.size < 2) {
      signal.throwIfAborted();
      const { done, value } = await reader.read();
      assert.ok(!done, "Stream ended before both sides finished");
      pending += decoder.decode(value, { stream: true });
      // Normalize complete CRLF pairs without losing a CR split across chunks.
      pending = pending.replaceAll("\r\n", "\n");
      let boundary;
      while ((boundary = pending.indexOf("\n\n")) !== -1) {
        const frame = pending.slice(0, boundary);
        pending = pending.slice(boundary + 2);
        const lines = frame.split("\n");
        const field = (name) => lines.filter((line) => line.startsWith(`${name}:`)).map((line) => line.slice(name.length + 1).trimStart()).join("\n");
        const event = field("event");
        const data = field("data");
        if (!data) continue; // SSE heartbeat/comment.
        const payload = JSON.parse(data);
        if (event === "run") {
          assert.equal(payload.run_id, "sample");
          assert.equal(payload.is_sample, true, "Sample must be labelled");
          if (!summarySeen) assert.ok(performance.now() - started < 5000, "First run frame took over 5 seconds");
          summarySeen = true;
          continue;
        }
        if (!["snapshot", "decision", "verdict", "executed", "ask", "error", "done"].includes(event)) continue;
        assert.ok(summarySeen, "Run summary must precede events");
        assert.equal(payload.run_id, "sample");
        assert.equal(payload.kind, event);
        assert.ok(["shielded", "unshielded"].includes(payload.mode));
        const id = Number(field("id"));
        assert.ok(Number.isInteger(id) && id > 0 && !ids.has(id), "Missing or repeated event id");
        ids.add(id);
        kinds.add(event);
        if (event === "done") finished.add(payload.mode);
      }
    }
    assert.equal(kinds.size, 7, "Sample must exercise all seven event kinds");
    return { events: ids.size, elapsedSeconds: ((performance.now() - started) / 1000).toFixed(1) };
  } finally {
    await reader.cancel();
  }
}

async function main() {
  const { values } = parseArgs({ options: { web: { type: "string" }, server: { type: "string" } } });
  assert.ok(values.web && values.server, "Usage: pnpm verify:day1 --web https://WEB --server https://SERVER");
  const origin = (value) => {
    const url = new URL(value);
    assert.ok(["http:", "https:"].includes(url.protocol) && !url.username && !url.password);
    assert.ok(url.pathname === "/" && !url.search && !url.hash, "Supply origins without paths, queries or credentials");
    return url.origin;
  };
  const web = origin(values.web);
  const server = origin(values.server);
  const get = async (base, path, cors = false) => {
    const response = await fetch(`${base}${path}`, { signal: AbortSignal.timeout(20_000), headers: cors ? { Origin: web } : {} });
    assert.ok(response.ok, `${path}: HTTP ${response.status}`);
    if (cors) assert.equal(response.headers.get("access-control-allow-origin"), web, `${path}: backend CORS must allow the exact web origin`);
    return response;
  };
  for (const path of ["/", "/console", "/health", "/runs", "/stats", "/arena"]) {
    const response = await get(web, path);
    assert.match(response.headers.get("content-type") ?? "", /text\/html/);
    const html = await response.text();
    assert.ok(html.includes(path === "/arena" ? "Aurora" : "Aegis"), `${path}: expected application HTML, not an authentication or error page`);
    console.log(`PASS web ${path}`);
  }
  const health = await (await get(server, "/healthz", true)).json();
  assert.equal(health.status, "ok");
  const browser = await (await get(server, "/healthz/browser", true)).json();
  assert.equal(browser.title, "Aegis OK");
  assert.ok(browser.version && browser.screenshot_b64, "Remote Chromium must return a screenshot");
  console.log("PASS remote Chromium + exact-origin CORS");
  const arena = await (await get(server, "/healthz/arena", true)).json();
  assert.equal(new URL(arena.url).origin, web, "Backend is loading a different arena host; coordinate ARENA_BASE_URL with Dev A");
  assert.match(arena.title, /Aurora/);
  console.log("PASS backend Chromium reaches this web arena");
  const llm = await (await get(server, "/healthz/llm", true)).json();
  assert.ok(llm.provider && llm.model);
  console.log(`PASS LLM smoke: ${llm.provider}:${llm.model}`);
  const presets = await (await get(server, "/presets", true)).json();
  assert.ok(Array.isArray(presets) && presets.length > 0);
  const summary = await (await get(server, "/runs/sample", true)).json();
  assert.equal(summary.is_sample, true);
  const signal = AbortSignal.timeout(40_000);
  const response = await fetch(`${server}/runs/sample/stream`, { headers: { Origin: web }, signal });
  assert.ok(response.ok);
  assert.equal(response.headers.get("access-control-allow-origin"), web);
  const result = await checkSampleStream(response, signal);
  console.log(`PASS sample SSE: ${result.events} events, both sides finished in ${result.elapsedSeconds}s`);
  console.log("HTTP/SSE checks passed. Browser interaction and phone-hotspot checks still require separate verification.");
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => { console.error(`FAIL: ${error.message}`); process.exitCode = 1; });
}
