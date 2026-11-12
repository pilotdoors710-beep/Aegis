import type { components, operations } from "./api-types";

export type Schema = components["schemas"];
export type RunEvent = operations["get_run_events_runs__run_id__events_get"]["responses"][200]["content"]["application/json"][number];
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = "ApiError"; }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) throw new ApiError(response.status, response.status === 501 ? "This server feature is not available yet." : `Server request failed (HTTP ${response.status}).`);
  return response.json() as Promise<T>;
}

export const api = {
  presets: (signal?: AbortSignal) => request<Schema["Preset"][]>("/presets", { signal }),
  run: (id: string, signal?: AbortSignal) => request<Schema["RunSummary"]>(`/runs/${encodeURIComponent(id)}`, { signal }),
  runs: (signal?: AbortSignal) => request<Schema["RunSummary"][]>("/runs?limit=20", { signal }),
  events: (id: string, signal?: AbortSignal) => request<RunEvent[]>(`/runs/${encodeURIComponent(id)}/events`, { signal }),
  stats: (signal?: AbortSignal) => request<Schema["EvalStats"]>("/stats", { signal }),
  createRun: (body: Schema["RunCreate"]) => request<Schema["RunCreated"]>("/runs", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }),
  resolveAsk: (id: string, askId: string, body: Schema["AskDecision"]) => request<Schema["AskPayload"]>(
    `/runs/${encodeURIComponent(id)}/ask/${encodeURIComponent(askId)}`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
  ),
};
