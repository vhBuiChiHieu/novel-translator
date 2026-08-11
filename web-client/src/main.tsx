import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, type Chapter, type ChapterPreview, type ContextItem, type Dashboard, type Job } from "./api";
import "./styles.css";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 2000 } } });

const navItems = [
  ["dashboard", "Tổng quan"], ["project", "Project"], ["import", "Nhập chương"], ["chapters", "Chapters"],
  ["jobs", "Translation Jobs"], ["context", "Context"], ["conflicts", "Conflicts"], ["settings", "Settings"],
  ["export", "Export"], ["developer", "Developer tools"]
] as const;

function useLaunch() {
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState("Đang kết nối local server…");
  useEffect(() => {
    const token = location.hash.match(/^#\/launch\/(.+)$/)?.[1];
    if (!token) { setMessage("Local server is no longer running."); return; }
    api.bootstrap(token).then(() => {
      history.replaceState(null, "", location.pathname + location.search);
      setReady(true);
    }).catch((error: unknown) => setMessage(error instanceof Error ? error.message : "Không thể bootstrap local session."));
  }, []);
  return { ready, message };
}

function App() {
  const launch = useLaunch();
  if (!launch.ready) return <main className="launch"><div className="launch-card"><span className="eyebrow">NOVEL TRANSLATOR / LOCAL</span><h1>{launch.message}</h1><p>Ứng dụng chỉ kết nối tới backend trên máy này.</p></div></main>;
  return <Workspace />;
}

function Workspace() {
  const [page, setPage] = useState("dashboard");
  const query = useQueryClient();
  const [events, setEvents] = useState<string[]>([]);
  useEffect(() => {
    const source = new EventSource("/api/v1/events");
    const handle = (event: MessageEvent) => {
      setEvents((current) => [event.type, ...current].slice(0, 8));
      if (event.type === "operation_completed" || event.type === "operation_failed" || event.type === "resync_required") query.invalidateQueries();
    };
    ["operation_started", "operation_completed", "operation_failed", "operation_cancelled", "chunk_completed", "resync_required"].forEach((name) => source.addEventListener(name, handle));
    source.onerror = () => setEvents((current) => ["reconnecting", ...current].slice(0, 8));
    return () => source.close();
  }, [query]);
  const current = useQuery({ queryKey: ["current"], queryFn: api.current });
  if (current.isLoading) return <main className="launch"><div className="launch-card"><h1>Đang mở project…</h1></div></main>;
  return <div className="shell">
    <aside className="sidebar"><div className="brand"><span className="brand-mark">N</span><div><strong>Novel</strong><small>TRANSLATOR / LOCAL</small></div></div><nav aria-label="Điều hướng chính">{navItems.map(([key, label]) => <button key={key} className={page === key ? "nav-item active" : "nav-item"} onClick={() => setPage(key)}>{label}</button>)}</nav><div className="side-foot"><span className="live-dot" /> Loopback only<br /><small>{current.data?.project?.project_name ?? "Chưa mở project"}</small></div></aside>
    <main className="content"><header className="topbar"><div><span className="eyebrow">WORKSPACE</span><h2>{navItems.find(([key]) => key === page)?.[1]}</h2></div><div className="connection"><span className="live-dot" /> Connected · SSE</div></header>{events.length > 0 && <div className="event-strip" role="status">Realtime: {events[0]}</div>}<Page page={page} current={current.data} /></main>
  </div>;
}

function Page({ page, current }: { page: string; current?: { open: boolean; project?: { project_name: string }; path?: string; validation_errors?: string[] } }) {
  if (!current?.open && page !== "project") return <ProjectPicker />;
  switch (page) {
    case "project": return <ProjectPicker current={current} />;
    case "dashboard": return <DashboardPage />;
    case "import": return <ImportPage />;
    case "chapters": return <ChaptersPage />;
    case "jobs": return <JobsPage />;
    case "context": return <ContextPage />;
    case "conflicts": return <ConflictsPage />;
    case "settings": return <SettingsPage />;
    case "export": return <ExportPage />;
    case "developer": return <DeveloperPage />;
    default: return <DashboardPage />;
  }
}

function ProjectPicker({ current }: { current?: { open: boolean; project?: { project_name: string }; path?: string; validation_errors?: string[] } }) {
  const [mode, setMode] = useState<"open" | "create">("open");
  const [path, setPath] = useState(current?.path ?? "");
  const [parentPath, setParentPath] = useState("");
  const [name, setName] = useState("");
  const query = useQueryClient();
  const openMutation = useMutation({ mutationFn: api.open, onSuccess: () => query.invalidateQueries() });
  const createMutation = useMutation({ mutationFn: () => api.create(parentPath, name), onSuccess: (result) => { setPath(result.path); setName(""); query.invalidateQueries(); } });
  const pickerMutation = useMutation({
    mutationFn: (purpose: "project" | "parent") => api.pickDirectory(purpose),
    onSuccess: (result, purpose) => {
      if (!result.path) return;
      if (purpose === "project") setPath(result.path);
      else setParentPath(result.path);
    },
  });
  const mutationError = mode === "open" ? openMutation.error : createMutation.error;
  const pending = openMutation.isPending || createMutation.isPending || pickerMutation.isPending;
  return <section className="panel hero-panel"><span className="eyebrow">PROJECT PICKER</span><h1>{current?.open ? current.project?.project_name : "Project local"}</h1><p className="muted">Mở project đã có hoặc tạo một project mới. Dữ liệu vẫn nằm hoàn toàn trên máy này.</p>{current?.validation_errors?.map((error) => <p className="error-line" key={error}>{error}</p>)}<div className="form-row compact" role="tablist" aria-label="Project action"><button className={mode === "open" ? "primary" : "secondary"} onClick={() => setMode("open")} role="tab" aria-selected={mode === "open"}>Mở project</button><button className={mode === "create" ? "primary" : "secondary"} onClick={() => setMode("create")} role="tab" aria-selected={mode === "create"}>Tạo project mới</button></div>{mode === "open" ? <><label htmlFor="project-path">Thư mục project</label><div className="form-row path-picker-row"><input id="project-path" value={path} onChange={(event) => setPath(event.target.value)} placeholder="C:\\projects\\tien-hiep-demo" /><button className="secondary" onClick={() => pickerMutation.mutate("project")} disabled={pending}>Chọn thư mục…</button><button className="primary" onClick={() => openMutation.mutate(path)} disabled={!path || pending}>Mở project</button></div><p className="muted picker-hint">Mở hộp thoại hệ thống để chọn thư mục, không cần dán đường dẫn.</p></> : <><label htmlFor="project-parent-path">Thư mục cha</label><div className="form-row path-picker-row"><input id="project-parent-path" value={parentPath} onChange={(event) => setParentPath(event.target.value)} placeholder="C:\\projects" /><button className="secondary" onClick={() => pickerMutation.mutate("parent")} disabled={pending}>Chọn thư mục…</button></div><label htmlFor="project-name">Tên project</label><div className="form-row"><input id="project-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="tien-hiep-demo" /><button className="primary" onClick={() => createMutation.mutate()} disabled={!parentPath || !name || pending}>Tạo và mở</button></div><p className="muted">Project sẽ được tạo thành <code>{parentPath || "C:\\projects"}\{name || "ten-project"}</code> cùng cấu trúc SQLite, source, translated, exports và logs.</p></>}{mutationError && <ErrorBox error={mutationError} />}{pickerMutation.error && <ErrorBox error={pickerMutation.error} />}{current?.open && <p className="success">Project đang mở: {current.project?.project_name}</p>}</section>;
}

function DashboardPage() {
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  if (dashboard.isLoading) return <Loading />;
  if (dashboard.error) return <ErrorBox error={dashboard.error} />;
  const data = dashboard.data as Dashboard;
  return <><div className="page-intro"><div><span className="eyebrow">DASHBOARD / LOCAL FIRST</span><h1>{data.project.title || data.project.project_name}</h1><p className="muted">{data.project.source_language.toUpperCase()} → {data.project.target_language.toUpperCase()} · {data.provider} / {data.model}</p></div><span className={data.health_ok ? "status-pill good" : "status-pill bad"}>{data.health_ok ? "Healthy" : "Needs attention"}</span></div><div className="stats">{Object.entries(data.chapter_counts).map(([key, value]) => <div className="stat-card" key={key}><span>{key}</span><strong>{value}</strong></div>)}<div className="stat-card"><span>open conflicts</span><strong>{data.open_conflicts}</strong></div></div><div className="grid-two"><div className="panel"><div className="panel-heading"><h3>Đang chạy</h3><span className="muted">{data.running_jobs.length} jobs</span></div>{data.running_jobs.length ? data.running_jobs.map((job) => <JobRow key={job.id} job={job} />) : <Empty text="Không có translation job đang chạy." />}</div><div className="panel"><div className="panel-heading"><h3>Health checks</h3></div>{data.health_errors.length ? data.health_errors.map((error) => <p className="error-line" key={error}>{error}</p>) : <p className="success">Project, database và thư mục đều hợp lệ.</p>}</div></div></>;
}

function ImportPage() {
  const [path, setPath] = useState(""); const [preview, setPreview] = useState<ChapterPreview[]>([]); const [error, setError] = useState<unknown>();
  const previewMutation = useMutation({ mutationFn: api.previewImport, onSuccess: setPreview, onError: setError });
  const importMutation = useMutation({ mutationFn: api.importChapters, onError: setError });
  const pickerMutation = useMutation({ mutationFn: () => api.pickDirectory("source"), onSuccess: (result) => { if (result.path) setPath(result.path); }, onError: setError });
  const pending = previewMutation.isPending || importMutation.isPending || pickerMutation.isPending;
  return <><div className="page-intro"><div><span className="eyebrow">SOURCE / IMPORT</span><h1>Nhập chương</h1><p className="muted">Preview trước, sau đó đưa các file chapter_<em>n</em>.txt vào project.</p></div></div><div className="panel"><label htmlFor="source-path">Thư mục chứa chapter</label><div className="form-row path-picker-row"><input id="source-path" value={path} onChange={(event) => setPath(event.target.value)} placeholder="C:\\input\\chapters" /><button className="secondary" onClick={() => pickerMutation.mutate()} disabled={pending}>Chọn thư mục…</button><button className="secondary" onClick={() => previewMutation.mutate(path)} disabled={!path || pending}>Preview</button><button className="primary" onClick={() => importMutation.mutate(path)} disabled={!preview.length || pending}>Import</button></div><p className="muted picker-hint">Chọn thư mục source bằng hộp thoại hệ thống, không cần dán đường dẫn.</p>{error !== undefined && error !== null ? <ErrorBox error={error} /> : null}{preview.length > 0 && <div className="table-wrap"><table><thead><tr><th>Chapter</th><th>File</th><th>UTF-8</th><th>Preview</th></tr></thead><tbody>{preview.map((item) => <tr key={item.chapter_number}><td>#{item.chapter_number}</td><td>{item.path}</td><td>{item.valid_utf8 ? "✓" : "✕"}</td><td className="truncate">{item.error ?? item.source_text ?? "—"}</td></tr>)}</tbody></table></div>}</div></>;
}

function ChaptersPage() {
  const chapters = useQuery({ queryKey: ["chapters"], queryFn: () => api.chapters() });
  const query = useQueryClient(); const [range, setRange] = useState({ first: "", last: "" }); const [message, setMessage] = useState("");
  const translate = useMutation({ mutationFn: (number: number) => api.translate(number), onSuccess: (operation) => setMessage(`Đã xếp hàng operation ${operation.operation_id}`), onError: setMessage });
  const translateRange = useMutation({ mutationFn: () => api.translateRange(Number(range.first), Number(range.last)), onSuccess: () => { setMessage("Đã xếp hàng range translation"); query.invalidateQueries({ queryKey: ["jobs"] }); }, onError: setMessage });
  if (chapters.isLoading) return <Loading />; if (chapters.error) return <ErrorBox error={chapters.error} />;
  return <><div className="page-intro"><div><span className="eyebrow">CHAPTERS</span><h1>Danh sách chương</h1></div><div className="form-row compact"><input aria-label="Từ chương" value={range.first} onChange={(e) => setRange({ ...range, first: e.target.value })} placeholder="Từ" /><input aria-label="Đến chương" value={range.last} onChange={(e) => setRange({ ...range, last: e.target.value })} placeholder="Đến" /><button className="primary" onClick={() => translateRange.mutate()} disabled={!range.first || !range.last || translateRange.isPending}>Dịch range</button></div></div>{message && <p className="success" role="status">{typeof message === "string" ? message : "Đã xảy ra lỗi."}</p>}<div className="panel table-wrap"><table><thead><tr><th>Chapter</th><th>Status</th><th>Source</th><th>Action</th></tr></thead><tbody>{(chapters.data as Chapter[]).map((chapter) => <tr key={chapter.id}><td>#{chapter.chapter_number}</td><td><span className="status-pill">{chapter.status}</span></td><td>{chapter.source_path}</td><td><button className="text-button" onClick={() => translate.mutate(chapter.chapter_number)} disabled={translate.isPending}>Translate</button></td></tr>)}</tbody></table>{!(chapters.data as Chapter[]).length && <Empty text="Chưa có chapter. Hãy preview và import source." />}</div></>;
}

function JobsPage() { const jobs = useQuery({ queryKey: ["jobs"], queryFn: api.jobs }); if (jobs.isLoading) return <Loading />; if (jobs.error) return <ErrorBox error={jobs.error} />; return <><div className="page-intro"><div><span className="eyebrow">TRANSLATION / REALTIME</span><h1>Translation jobs</h1><p className="muted">SSE cập nhật chunk progress; REST/SQLite là nguồn dữ liệu authoritative.</p></div></div><div className="panel">{(jobs.data as Job[]).map((job) => <JobRow key={job.id} job={job} detail />)}{!(jobs.data as Job[]).length && <Empty text="Chưa có job dịch." />}</div></>; }
function JobRow({ job, detail = false }: { job: Job; detail?: boolean }) { return <div className="job-row"><div><strong>Chapter {job.chapter_number ?? "—"}</strong><span className="muted"> · {job.model_provider}/{job.model_name}</span></div><span className={`status-pill ${job.status === "completed" ? "good" : ""}`}>{job.status}</span>{detail && <small className="muted">{job.total_prompt_tokens} prompt tokens · {job.total_duration_ms} ms</small>}</div>; }

function ContextPage() { const context = useQuery({ queryKey: ["context"], queryFn: api.context }); const [source, setSource] = useState(""); const [translation, setTranslation] = useState(""); const mutation = useMutation({ mutationFn: () => api.upsertContext({ context_type: "term", source, translation }), onSuccess: () => { setSource(""); setTranslation(" "); }, }); if (context.isLoading) return <Loading />; return <><div className="page-intro"><div><span className="eyebrow">GLOSSARY / CONTEXT</span><h1>Context</h1><p className="muted">Mapping xác nhận và đề xuất được lưu qua application facade.</p></div></div><div className="panel"><div className="form-row"><input aria-label="Source" value={source} onChange={(e) => setSource(e.target.value)} placeholder="Source term" /><input aria-label="Translation" value={translation} onChange={(e) => setTranslation(e.target.value)} placeholder="Bản dịch" /><button className="primary" onClick={() => mutation.mutate()} disabled={!source || mutation.isPending}>Lưu mapping</button></div><div className="table-wrap"><table><thead><tr><th>Type</th><th>Source</th><th>Translation</th><th>Status</th></tr></thead><tbody>{(context.data as ContextItem[]).map((item) => <tr key={`${item.context_type}-${item.id}`}><td>{item.context_type}</td><td>{item.source}</td><td>{item.translation}</td><td>{item.status}</td></tr>)}</tbody></table></div></div></>; }
function ConflictsPage() { const conflicts = useQuery({ queryKey: ["conflicts"], queryFn: api.conflicts }); if (conflicts.isLoading) return <Loading />; return <><div className="page-intro"><div><span className="eyebrow">CONTEXT / REVIEW</span><h1>Conflicts</h1></div></div><div className="panel">{(conflicts.data ?? []).map((conflict) => <div className="conflict" key={conflict.id}><div><strong>{conflict.source_key}</strong><p className="muted">Existing: {conflict.existing_value ?? "—"} · Candidate: {conflict.candidate_value ?? "—"}</p></div><span className="status-pill">{conflict.status}</span></div>)}{!(conflicts.data ?? []).length && <Empty text="Không có conflict mở." />}</div></>; }

function SettingsPage() { const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings }); const keyStatus = useQuery({ queryKey: ["key-status"], queryFn: api.apiKeyStatus }); const [key, setKey] = useState(""); const keyMutation = useMutation({ mutationFn: () => api.saveApiKey(key), onSuccess: () => { setKey(""); keyStatus.refetch(); } }); if (settings.isLoading) return <Loading />; return <><div className="page-intro"><div><span className="eyebrow">CONFIGURATION</span><h1>Settings</h1><p className="muted">API key là write-only và chỉ hiển thị trạng thái đã cấu hình.</p></div></div><div className="grid-two"><div className="panel"><h3>Model</h3><dl className="details"><dt>Provider</dt><dd>{String((settings.data?.model as Record<string, unknown>)?.provider)}</dd><dt>Model</dt><dd>{String((settings.data?.model as Record<string, unknown>)?.name)}</dd><dt>Prompt</dt><dd>{String(settings.data?.prompt_version)}</dd></dl></div><div className="panel"><h3>DeepSeek API key</h3><p className="muted">Configured: {keyStatus.data?.configured ? "yes" : "no"}</p><label htmlFor="api-key">API key</label><div className="form-row"><input id="api-key" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} /><button className="primary" onClick={() => keyMutation.mutate()} disabled={!key || keyMutation.isPending}>Lưu key</button></div></div></div></>; }
function ExportPage() { const mutation = useMutation({ mutationFn: api.exportProject }); return <><div className="page-intro"><div><span className="eyebrow">OUTPUT / LOCAL</span><h1>Export</h1><p className="muted">Tạo bản ghép trong thư mục exports của project.</p></div></div><div className="panel actions"><button className="primary" onClick={() => mutation.mutate("novel")} disabled={mutation.isPending}>Export novel</button><button className="secondary" onClick={() => mutation.mutate("context")} disabled={mutation.isPending}>Export context YAML</button>{mutation.data && <p className="success">Đã xếp hàng operation {mutation.data.operation_id}</p>}{mutation.error && <ErrorBox error={mutation.error} />}</div></>; }
function DeveloperPage() { const tables = useQuery({ queryKey: ["tables"], queryFn: api.tables }); const [selected, setSelected] = useState(""); const table = useQuery({ queryKey: ["table", selected], queryFn: () => api.table(selected), enabled: Boolean(selected) }); return <><div className="page-intro"><div><span className="eyebrow">DEVELOPER ONLY</span><h1>Database inspector</h1><p className="muted">Read-only viewer; audit có thể chứa source, prompt và translation.</p></div></div><div className="panel"><div className="form-row"><label htmlFor="table">Table</label><select id="table" value={selected} onChange={(e) => setSelected(e.target.value)}><option value="">Chọn table…</option>{tables.data?.tables.map((name) => <option key={name}>{name}</option>)}</select></div>{table.data && <div className="table-wrap"><table><thead><tr>{table.data.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{table.data.rows.map((row, index) => <tr key={index}>{table.data.columns.map((column) => <td key={column} className="truncate">{row[column]}</td>)}</tr>)}</tbody></table></div>}</div></>; }

function Loading() { return <div className="panel loading" role="status">Đang tải dữ liệu…</div>; }
function Empty({ text }: { text: string }) { return <p className="empty">{text}</p>; }
function ErrorBox({ error }: { error: unknown }) { const message = error instanceof ApiError ? `${error.code}: ${error.message}` : error instanceof Error ? error.message : "Đã xảy ra lỗi."; return <div className="error-box" role="alert">{message}</div>; }

createRoot(document.getElementById("root")!).render(<React.StrictMode><QueryClientProvider client={queryClient}><App /></QueryClientProvider></React.StrictMode>);
