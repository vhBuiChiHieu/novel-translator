export type ApiErrorShape = { error: { code: string; message: string; details?: Record<string, unknown> } };

export class ApiError extends Error {
  code: string;
  details: Record<string, unknown>;

  constructor(payload: ApiErrorShape) {
    super(payload.error.message);
    this.code = payload.error.code;
    this.details = payload.error.details ?? {};
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api/v1${path}`, { ...init, headers, credentials: "same-origin" });
  if (!response.ok) {
    const payload = (await response.json()) as ApiErrorShape;
    throw new ApiError(payload);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  bootstrap: (token: string) => request<{ authenticated: boolean }>("/session/bootstrap", { method: "POST", headers: { "X-Local-App-Token": token } }),
  health: () => request<{ status: string; version: string }>("/health"),
  current: () => request<{ open: boolean; project?: Novel; path?: string; validation_errors: string[] }>("/projects/current"),
  open: (path: string) => request<{ open: boolean; project: Novel; path: string }>("/projects/open", { method: "POST", body: JSON.stringify({ path }) }),
  pickDirectory: (purpose: "project" | "parent" | "source") => request<{ path: string | null }>("/projects/pick", { method: "POST", body: JSON.stringify({ purpose }) }),
  create: (parent_path: string, name: string) => request<{ open: boolean; project: Novel; path: string }>("/projects/create", { method: "POST", body: JSON.stringify({ parent_path, name }) }),
  dashboard: () => request<Dashboard>("/dashboard"),
  settings: () => request<Record<string, unknown>>("/settings"),
  updateSettings: (updates: Record<string, unknown>) => request<Record<string, unknown>>("/settings", { method: "PATCH", body: JSON.stringify(updates) }),
  apiKeyStatus: () => request<{ configured: boolean }>("/settings/model-api-key/status"),
  saveApiKey: (api_key: string) => request<void>("/settings/model-api-key", { method: "PUT", body: JSON.stringify({ api_key }) }),
  previewImport: (source_directory: string) => request<ChapterPreview[]>("/import/preview", { method: "POST", body: JSON.stringify({ source_directory }) }),
  importChapters: (source_directory: string) => request<Operation>("/imports", { method: "POST", body: JSON.stringify({ source_directory }) }),
  chapters: (status?: string) => request<Chapter[]>(`/chapters${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  jobs: () => request<Job[]>("/translation-jobs"),
  translate: (chapter_number: number, resume = false, force = false) => request<Operation>("/translations", { method: "POST", body: JSON.stringify({ chapter_number, resume, force }) }),
  translateRange: (first: number, last: number, resume = false, force = false) => request<Operation>("/translations/range", { method: "POST", body: JSON.stringify({ first, last, resume, force }) }),
  context: () => request<ContextItem[]>("/context"),
  upsertContext: (payload: Record<string, unknown>) => request<Record<string, unknown>>("/context", { method: "POST", body: JSON.stringify(payload) }),
  conflicts: () => request<Conflict[]>("/context/conflicts"),
  exportProject: (kind: "novel" | "context") => request<Operation>("/exports", { method: "POST", body: JSON.stringify({ kind }) }),
  operations: (id: string) => request<OperationView>(`/operations/${id}`),
  tables: () => request<{ tables: string[] }>("/database/tables"),
  table: (name: string) => request<DatabaseTable>(`/database/tables/${encodeURIComponent(name)}`)
};

export type Novel = { project_name: string; title: string; source_language: string; target_language: string };
export type Dashboard = { project: Novel; provider: string; model: string; chapter_counts: Record<string, number>; running_jobs: Job[]; open_conflicts: number; health_ok: boolean; health_errors: string[] };
export type Chapter = { id: number; chapter_number: number; source_path: string; translated_path?: string; status: string; source_text?: string };
export type ChapterPreview = { chapter_number: number; path: string; valid_utf8: boolean; source_text?: string; error?: string };
export type Job = { id: number; chapter_number?: number; status: string; model_provider: string; model_name: string; total_prompt_tokens: number; total_output_tokens: number; total_duration_ms: number };
export type ContextItem = { id: number; context_type: string; source: string; translation?: string; description?: string; status: string };
export type Conflict = { id: number; context_type: string; source_key: string; existing_value?: string; candidate_value?: string; status: string };
export type Operation = { operation_id: string; status: string; chapter_numbers: number[] };
export type OperationView = Operation & { kind: string; result?: Record<string, unknown>; error?: Record<string, unknown> };
export type DatabaseTable = { name: string; columns: string[]; rows: Record<string, string>[] };
