import type { components, operations } from "./api-types";

export type Schema = components["schemas"];
export type RunEvent = operations["get_run_events_runs__run_id__events_get"]["responses"][200]["content"]["application/json"][number];
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = "ApiError"; }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    const detail = await response.json().then((b) => b?.detail, () => null);  // FastAPI's reason, when it is plain text
    throw new ApiError(response.status, response.status === 501 ? "This server feature is not available yet." : typeof detail === "string" ? detail : `Server request failed (HTTP ${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  sybilDatasets: (signal?: AbortSignal) => request<Schema["SybilDatasetStatus"][]>("/sybil/datasets", { signal }),
  createSybilScenario: (body: Schema["SybilScenarioCreate"]) => request<Schema["SybilScenarioRevision"]>("/sybil/scenarios", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }),
  generateSybilScenario: (datasetId: string, body: Schema["SybilGenerate"]) => request<Schema["SybilScenarioRevision"]>(
    `/sybil/datasets/${encodeURIComponent(datasetId)}/generate`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
  ),
  sybilScenario: (id: string, signal?: AbortSignal) => request<Schema["SybilScenarioRevision"]>(
    `/sybil/scenarios/${encodeURIComponent(id)}`, { signal },
  ),
  sybilView: (id: string, limit = 150, signal?: AbortSignal) => request<Schema["SybilGraphView"]>(
    `/sybil/scenarios/${encodeURIComponent(id)}/view?limit=${limit}`, { signal },
  ),
  createSybilAssessment: (id: string) => request<Schema["SybilAssessmentRecord"]>(
    `/sybil/scenarios/${encodeURIComponent(id)}/assessments`, { method: "POST" },
  ),
  sybilAssessment: (id: string, signal?: AbortSignal) => request<Schema["SybilAssessmentRecord"]>(
    `/sybil/assessments/${encodeURIComponent(id)}`, { signal },
  ),
  sybilCounterfactual: (id: string, body: Schema["SybilScenarioCreate"]) => request<Schema["SybilCounterfactualResult"]>(
    `/sybil/scenarios/${encodeURIComponent(id)}/counterfactuals`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
  ),
  presets: (signal?: AbortSignal) => request<Schema["Preset"][]>("/presets", { signal }),
  run: (id: string, signal?: AbortSignal) => request<Schema["RunSummary"]>(`/runs/${encodeURIComponent(id)}`, { signal }),
  runs: (signal?: AbortSignal) => request<Schema["RunSummary"][]>("/runs?limit=20", { signal }),
  events: (id: string, signal?: AbortSignal) => request<RunEvent[]>(`/runs/${encodeURIComponent(id)}/events`, { signal }),
  stats: (signal?: AbortSignal) => request<Schema["EvalStats"]>("/stats", { signal }),
  createRun: (body: Schema["RunCreate"]) => request<Schema["RunCreated"]>("/runs", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }),
  labTrial: (body: Schema["LabRequest"]) => request<Schema["TrialReport"]>("/lab/trial", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }),
  scan: (body: Schema["ScanRequest"]) => request<Schema["ScanReport"]>("/scan", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }),
  resolveAsk: (id: string, askId: string, body: Schema["AskDecision"]) => request<Schema["AskPayload"]>(
    `/runs/${encodeURIComponent(id)}/ask/${encodeURIComponent(askId)}`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
  ),
};
