"use client";

import { useEffect, useState } from "react";
import { API_URL, type RunEvent, type Schema } from "./api";

const kinds = ["snapshot", "decision", "verdict", "executed", "ask", "error", "done"] as const;
type StreamState = {
  summary: Schema["RunSummary"] | null;
  events: RunEvent[];
  status: "connecting" | "streaming" | "complete" | "error";
  error: string | null;
};

// Key the consuming component by run id to give each run fresh state.
export function useRunStream(runId: string): StreamState {
  const [state, setState] = useState<StreamState>({ summary: null, events: [], status: "connecting", error: null });
  useEffect(() => {
    const source = new EventSource(`${API_URL}/runs/${encodeURIComponent(runId)}/stream`);
    const seen = new Set<string>();
    const finished = new Set<RunEvent["mode"]>();
    let closed = false;
    function fail(message: string) {
      closed = true;
      source.close();
      setState((previous) => ({ ...previous, status: "error", error: message }));
    }
    source.addEventListener("run", (message: MessageEvent<string>) => {
      if (closed) return;
      try {
        const summary = JSON.parse(message.data) as Schema["RunSummary"];
        if (summary.run_id !== runId || typeof summary.is_sample !== "boolean") throw new Error();
        setState((previous) => ({ ...previous, summary, status: "streaming" }));
      } catch { fail("The server sent an invalid run summary."); }
    });
    for (const kind of kinds) {
      source.addEventListener(kind, (message: MessageEvent<string>) => {
        if (closed || typeof message.data !== "string") return;
        if (message.lastEventId && seen.has(message.lastEventId)) return;
        try {
          const event = JSON.parse(message.data) as RunEvent;
          if (event.run_id !== runId || event.kind !== kind || !["shielded", "unshielded"].includes(event.mode) || !event.payload) throw new Error();
          if (message.lastEventId) seen.add(message.lastEventId);
          if (event.kind === "done") finished.add(event.mode);
          const complete = finished.size === 2;
          if (complete) { closed = true; source.close(); }
          setState((previous) => ({ ...previous, events: [...previous.events, event], status: complete ? "complete" : "streaming" }));
        } catch { fail("The server sent an invalid run event."); }
      });
    }
    source.onerror = (event) => {
      if (!closed && !(event instanceof MessageEvent)) fail("The event stream was interrupted. Restart the sample to try again.");
    };
    return () => { closed = true; source.close(); };
  }, [runId]);
  return state;
}
