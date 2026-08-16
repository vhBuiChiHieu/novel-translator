import React, { useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, type Chapter, type ChapterPreview, type ContextItem, type Dashboard, type Job } from "./api";
import "./styles.css";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 2000 } } });

const navItems = [
  { key: "dashboard", label: "Tổng quan", icon: "⌂" },
  { key: "project", label: "Project", icon: "◈" },
  { key: "import", label: "Nhập chương", icon: "↥" },
  { key: "chapters", label: "Chapters", icon: "☷" },
  { key: "jobs", label: "Translation Jobs", icon: "◌" },
  { key: "context", label: "Context", icon: "◎" },
  { key: "conflicts", label: "Conflicts", icon: "⚠" },
  { key: "settings", label: "Settings", icon: "⚙" },
  { key: "export", label: "Export", icon: "↧" },
  { key: "developer", label: "Developer tools", icon: "</>" },
] as const;

type PageKey = (typeof navItems)[number]["key"];
type CurrentProject = { open: boolean; project?: { project_name: string }; path?: string; validation_errors?: string[] };
type Feedback = { kind: "success" | "error"; text: string };
type ConnectionState = "connecting" | "connected" | "reconnecting";

const EVENT_LABELS: Record<string, string> = {
  operation_started: "Operation vừa bắt đầu",
  operation_completed: "Operation đã hoàn tất",
  operation_failed: "Operation thất bại",
  operation_cancelled: "Operation đã dừng",
  chunk_completed: "Một chunk vừa hoàn tất",
  resync_required: "Dữ liệu đã được làm mới",
};

function useLaunch() {
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState("Đang kết nối local server…");
  useEffect(() => {
    let cancelled = false;
    const token = location.hash.match(/^#\/launch\/(.+)$/)?.[1];
    const useExistingSession = () => api.current().then(() => {
      if (!cancelled) setReady(true);
    }).catch((error: unknown) => {
      if (cancelled) return;
      const nextMessage = error instanceof ApiError && error.code === "SESSION_REQUIRED"
        ? "Không tìm thấy local session. Hãy mở lại ứng dụng bằng lệnh novel-web."
        : error instanceof Error ? error.message : "Không thể khôi phục local session.";
      setMessage(nextMessage);
    });

    if (!token) {
      void useExistingSession();
      return () => { cancelled = true; };
    }

    api.bootstrap(token).then(() => {
      if (cancelled) return;
      history.replaceState(null, "", location.pathname + location.search);
      setReady(true);
    }).catch((error: unknown) => {
      if (cancelled) return;
      // The one-time launch token may already have been consumed while the
      // browser still has a valid session cookie (for example after reload).
      if (error instanceof ApiError && error.code === "BOOTSTRAP_INVALID") {
        void useExistingSession();
        return;
      }
      setMessage(error instanceof Error ? error.message : "Không thể bootstrap local session.");
    });
    return () => { cancelled = true; };
  }, []);
  return { ready, message };
}

function useRealtimeEvents() {
  const query = useQueryClient();
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [lastEvent, setLastEvent] = useState<string | null>(null);
  useEffect(() => {
    const source = new EventSource("/api/v1/events");
    const handle = (event: Event) => {
      setLastEvent(EVENT_LABELS[event.type] ?? event.type);
      if (["operation_completed", "operation_failed", "resync_required"].includes(event.type)) query.invalidateQueries();
    };
    source.onopen = () => setConnection("connected");
    source.onerror = () => setConnection("reconnecting");
    ["operation_started", "operation_completed", "operation_failed", "operation_cancelled", "chunk_completed", "resync_required"].forEach((name) => source.addEventListener(name, handle));
    return () => source.close();
  }, [query]);
  return { connection, lastEvent };
}

function App() {
  const launch = useLaunch();
  if (!launch.ready) return <main className="launch"><div className="launch-card"><span className="eyebrow">NOVEL TRANSLATOR / LOCAL</span><div className="launch-mark" aria-hidden="true">N</div><h1>{launch.message}</h1><p>Ứng dụng chỉ kết nối tới backend trên máy này.</p><div className="loading-line" aria-hidden="true"><span /></div></div></main>;
  return <Workspace />;
}

function Workspace() {
  const [page, setPage] = useState<PageKey>("dashboard");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const realtime = useRealtimeEvents();
  const current = useQuery({ queryKey: ["current"], queryFn: api.current });
  const currentProjectName = current.data?.project?.project_name ?? "Chưa mở project";

  if (current.isLoading) return <main className="launch"><div className="launch-card"><div className="skeleton skeleton-kicker" /><div className="skeleton skeleton-title" /><div className="skeleton skeleton-copy" /></div></main>;
  if (current.error) return <main className="launch"><ErrorBox error={current.error} /> </main>;

  return <div className="shell">
    <button className={`nav-scrim ${mobileNavOpen ? "visible" : ""}`} onClick={() => setMobileNavOpen(false)} aria-label="Đóng menu điều hướng" />
    <aside className={`sidebar ${mobileNavOpen ? "open" : ""}`}>
      <div className="brand"><span className="brand-mark">N</span><div><strong>Novel</strong><small>TRANSLATOR / LOCAL</small></div><button className="nav-close" onClick={() => setMobileNavOpen(false)} aria-label="Đóng menu">×</button></div>
      <div className="sidebar-label">Workspace</div>
      <nav aria-label="Điều hướng chính">{navItems.map(({ key, label, icon }) => <button key={key} className={page === key ? "nav-item active" : "nav-item"} onClick={() => { setPage(key); setMobileNavOpen(false); }} aria-current={page === key ? "page" : undefined}><span className="nav-icon" aria-hidden="true">{icon}</span><span>{label}</span>{page === key && <span className="nav-arrow" aria-hidden="true">→</span>}</button>)}</nav>
      <div className="side-foot"><div className="side-status"><span className={`live-dot ${realtime.connection === "reconnecting" ? "warning" : ""}`} /> <span>{realtime.connection === "connected" ? "Loopback only" : realtime.connection === "connecting" ? "Connecting…" : "Reconnecting…"}</span></div><small title={currentProjectName}>{currentProjectName}</small></div>
    </aside>
    <main className="content">
      <header className="topbar"><div className="topbar-main"><button className="menu-toggle" onClick={() => setMobileNavOpen(true)} aria-label="Mở menu điều hướng"><span /><span /><span /></button><div><span className="eyebrow">WORKSPACE</span><div className="title-row"><h2>{navItems.find(({ key }) => key === page)?.label}</h2><span className="project-chip">{currentProjectName}</span></div></div></div><div className={`connection ${realtime.connection}`}><span className={`live-dot ${realtime.connection === "reconnecting" ? "warning" : ""}`} />{realtime.connection === "connected" ? "Connected · SSE" : realtime.connection === "connecting" ? "Connecting…" : "Reconnecting…"}</div></header>
      {realtime.lastEvent && <div className="event-strip" role="status"><span className="event-icon" aria-hidden="true">✦</span><div><strong>Realtime update</strong><span>{realtime.lastEvent}</span></div></div>}
      <Page page={page} current={current.data} />
    </main>
  </div>;
}

function Page({ page, current }: { page: PageKey; current?: CurrentProject }) {
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
  }
}

function ProjectPicker({ current }: { current?: CurrentProject }) {
  const [mode, setMode] = useState<"open" | "create">("open");
  const [path, setPath] = useState(current?.path ?? "");
  const [parentPath, setParentPath] = useState("");
  const [name, setName] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const query = useQueryClient();
  const openMutation = useMutation({ mutationFn: api.open, onSuccess: () => { setFeedback({ kind: "success", text: "Project đã được mở thành công." }); query.invalidateQueries(); }, onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) });
  const createMutation = useMutation({ mutationFn: () => api.create(parentPath, name), onSuccess: (result) => { setPath(result.path); setName(""); setFeedback({ kind: "success", text: "Project mới đã được tạo và mở." }); query.invalidateQueries(); }, onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) });
  const pickerMutation = useMutation({ mutationFn: (purpose: "project" | "parent") => api.pickDirectory(purpose), onSuccess: (result, purpose) => { if (!result.path) return; if (purpose === "project") setPath(result.path); else setParentPath(result.path); }, onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) });
  const pending = openMutation.isPending || createMutation.isPending || pickerMutation.isPending;
  return <section className="panel hero-panel"><div className="hero-orb" aria-hidden="true" /><div className="hero-copy"><span className="eyebrow">PROJECT PICKER</span><h1>{current?.open ? current.project?.project_name : "Project local"}</h1><p className="muted">Mở project đã có hoặc tạo một project mới. Dữ liệu vẫn nằm hoàn toàn trên máy này.</p></div>{current?.validation_errors?.map((error) => <p className="error-line" key={error}>{error}</p>)}<div className="segmented" role="tablist" aria-label="Project action"><button className={mode === "open" ? "segment active" : "segment"} onClick={() => setMode("open")} role="tab" aria-selected={mode === "open"}>Mở project</button><button className={mode === "create" ? "segment active" : "segment"} onClick={() => setMode("create")} role="tab" aria-selected={mode === "create"}>Tạo project mới</button></div>{mode === "open" ? <><label htmlFor="project-path">Thư mục project</label><div className="form-row path-picker-row"><input id="project-path" value={path} onChange={(event) => setPath(event.target.value)} placeholder="C:\\projects\\tien-hiep-demo" /><Button onClick={() => pickerMutation.mutate("project")} disabled={pending} loading={pickerMutation.isPending} loadingLabel="Đang mở…">Chọn thư mục…</Button><Button variant="primary" onClick={() => openMutation.mutate(path)} disabled={!path || pending} loading={openMutation.isPending} loadingLabel="Đang mở…">Mở project</Button></div><p className="muted picker-hint">Chọn thư mục bằng hộp thoại hệ thống, không cần dán đường dẫn.</p></> : <><label htmlFor="project-parent-path">Thư mục cha</label><div className="form-row path-picker-row"><input id="project-parent-path" value={parentPath} onChange={(event) => setParentPath(event.target.value)} placeholder="C:\\projects" /><Button onClick={() => pickerMutation.mutate("parent")} disabled={pending} loading={pickerMutation.isPending} loadingLabel="Đang mở…">Chọn thư mục…</Button></div><label htmlFor="project-name">Tên project</label><div className="form-row"><input id="project-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="tien-hiep-demo" /><Button variant="primary" onClick={() => createMutation.mutate()} disabled={!parentPath || !name || pending} loading={createMutation.isPending} loadingLabel="Đang tạo…">Tạo và mở</Button></div><p className="muted">Project sẽ được tạo thành <code>{parentPath || "C:\\projects"}\{name || "ten-project"}</code> cùng cấu trúc SQLite, source, translated, exports và logs.</p></>}{feedback && <FeedbackBox feedback={feedback} />}{current?.open && !feedback && <p className="success">Project đang mở: {current.project?.project_name}</p>}</section>;
}

function DashboardPage() {
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  if (dashboard.isLoading) return <Loading />;
  if (dashboard.error) return <ErrorBox error={dashboard.error} />;
  const data = dashboard.data as Dashboard;
  const statLabels: Record<string, string> = { imported: "Imported", translated: "Translated", translating: "Translating", failed: "Failed", pending: "Pending" };
  return <><div className="page-intro"><div><span className="eyebrow">DASHBOARD / LOCAL FIRST</span><h1>{data.project.title || data.project.project_name}</h1><p className="muted">{data.project.source_language.toUpperCase()} <span className="route-arrow">→</span> {data.project.target_language.toUpperCase()} <span className="dot-separator">·</span> {data.provider} / {data.model}</p></div><span className={data.health_ok ? "status-pill good" : "status-pill bad"}><span className="status-dot" />{data.health_ok ? "Healthy" : "Needs attention"}</span></div><div className="stats">{Object.entries(data.chapter_counts).map(([key, value]) => <div className="stat-card" key={key}><span>{statLabels[key] ?? key.replaceAll("_", " ")}</span><strong>{value}</strong></div>)}<div className="stat-card accent"><span>Open conflicts</span><strong>{data.open_conflicts}</strong></div></div><div className="grid-two dashboard-lower"><div className="panel"><div className="panel-heading"><div><span className="eyebrow">LIVE</span><h3>Đang chạy</h3></div><span className="muted">{data.running_jobs.length} jobs</span></div>{data.running_jobs.length ? data.running_jobs.map((job) => <JobRow key={job.id} job={job} />) : <Empty text="Không có translation job đang chạy." />}</div><div className="panel"><div className="panel-heading"><div><span className="eyebrow">SYSTEM</span><h3>Health checks</h3></div><span className={data.health_ok ? "check-mark" : "status-dot bad-dot"}>{data.health_ok ? "✓" : "!"}</span></div>{data.health_errors.length ? data.health_errors.map((error) => <p className="error-line" key={error}>{error}</p>) : <p className="success">Project, database và thư mục đều hợp lệ.</p>}</div></div></>;
}

function ImportPage() {
  const [path, setPath] = useState("");
  const [preview, setPreview] = useState<ChapterPreview[]>([]);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const query = useQueryClient();
  const previewMutation = useMutation({ mutationFn: api.previewImport, onSuccess: (items) => { setPreview(items); setFeedback({ kind: "success", text: `${items.length} chapter đã sẵn sàng để kiểm tra.` }); }, onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) });
  const importMutation = useMutation({ mutationFn: api.importChapters, onSuccess: (result) => { setFeedback({ kind: "success", text: `Đã xếp hàng import operation ${result.operation_id}.` }); query.invalidateQueries(); }, onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) });
  const pickerMutation = useMutation({ mutationFn: () => api.pickDirectory("source"), onSuccess: (result) => { if (result.path) { setPath(result.path); setFeedback(null); } }, onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) });
  const pending = previewMutation.isPending || importMutation.isPending || pickerMutation.isPending;
  return <><PageIntro eyebrow="SOURCE / IMPORT" title="Nhập chương" description={<>Preview trước, sau đó đưa các file <code>chapter_n.txt</code> vào project.</>} /><div className="panel"><div className="form-row path-picker-row"><div className="field-grow"><label htmlFor="source-path">Thư mục chứa chapter</label><input id="source-path" value={path} onChange={(event) => setPath(event.target.value)} placeholder="C:\\input\\chapters" /></div><Button onClick={() => pickerMutation.mutate()} disabled={pending} loading={pickerMutation.isPending} loadingLabel="Đang mở…">Chọn thư mục…</Button><Button onClick={() => previewMutation.mutate(path)} disabled={!path || pending} loading={previewMutation.isPending} loadingLabel="Đang đọc…">Preview</Button><Button variant="primary" onClick={() => importMutation.mutate(path)} disabled={!preview.length || pending} loading={importMutation.isPending} loadingLabel="Đang import…">Import</Button></div><p className="muted picker-hint">Chọn thư mục source bằng hộp thoại hệ thống, không cần dán đường dẫn.</p>{feedback && <FeedbackBox feedback={feedback} />}{preview.length > 0 && <div className="table-wrap"><table><thead><tr><th>Chapter</th><th>File</th><th>UTF-8</th><th>Preview</th></tr></thead><tbody>{preview.map((item) => <tr key={item.chapter_number}><td><strong>#{item.chapter_number}</strong></td><td className="path-cell">{item.path}</td><td><span className={`status-pill ${item.valid_utf8 ? "good" : "bad"}`}>{item.valid_utf8 ? "Valid" : "Invalid"}</span></td><td className="truncate">{item.error ?? item.source_text ?? "—"}</td></tr>)}</tbody></table></div>}</div></>;
}

function ChaptersPage() {
  const chapters = useQuery({ queryKey: ["chapters"], queryFn: () => api.chapters() });
  const query = useQueryClient();
  const [range, setRange] = useState({ first: "", last: "" });
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const first = Number(range.first); const last = Number(range.last);
  const rangeInvalid = Boolean(range.first && range.last) && (!Number.isInteger(first) || !Number.isInteger(last) || first < 1 || last < 1 || first > last);
  const translate = useMutation({ mutationFn: (number: number) => api.translate(number), onSuccess: (operation) => { setFeedback({ kind: "success", text: `Đã xếp hàng operation ${operation.operation_id}.` }); query.invalidateQueries(); }, onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) });
  const translateRange = useMutation({ mutationFn: () => api.translateRange(first, last), onSuccess: (operation) => { setFeedback({ kind: "success", text: `Đã xếp hàng range operation ${operation.operation_id}.` }); query.invalidateQueries(); }, onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) });
  if (chapters.isLoading) return <Loading />;
  if (chapters.error) return <ErrorBox error={chapters.error} />;
  const items = chapters.data as Chapter[];
  return <><div className="page-intro"><div><span className="eyebrow">CHAPTERS</span><h1>Danh sách chương</h1><p className="muted">Chọn một chương hoặc xếp hàng cả một khoảng để dịch.</p></div><div className="range-actions"><div className="range-inputs"><input aria-label="Từ chương" value={range.first} onChange={(e) => setRange({ ...range, first: e.target.value })} placeholder="Từ" inputMode="numeric" /><span>→</span><input aria-label="Đến chương" value={range.last} onChange={(e) => setRange({ ...range, last: e.target.value })} placeholder="Đến" inputMode="numeric" /></div><Button variant="primary" onClick={() => translateRange.mutate()} disabled={!range.first || !range.last || rangeInvalid || translateRange.isPending} loading={translateRange.isPending} loadingLabel="Đang xếp hàng…">Dịch range</Button></div></div>{rangeInvalid && <p className="field-error" role="alert">Khoảng chapter không hợp lệ. Hãy nhập số nguyên dương và “Từ” không lớn hơn “Đến”.</p>}{feedback && <FeedbackBox feedback={feedback} />}<div className="panel table-wrap"><table><thead><tr><th>Chapter</th><th>Status</th><th>Source</th><th>Action</th></tr></thead><tbody>{items.map((chapter) => <tr key={chapter.id}><td><strong>#{chapter.chapter_number}</strong></td><td><StatusPill status={chapter.status} /></td><td className="path-cell">{chapter.source_path}</td><td><button className="text-button" onClick={() => translate.mutate(chapter.chapter_number)} disabled={translate.isPending} aria-label={`Dịch chapter ${chapter.chapter_number}`}>Translate <span aria-hidden="true">→</span></button></td></tr>)}</tbody></table>{!items.length && <Empty text="Chưa có chapter. Hãy preview và import source." />}</div></>;
}

function JobsPage() { const jobs = useQuery({ queryKey: ["jobs"], queryFn: api.jobs }); if (jobs.isLoading) return <Loading />; if (jobs.error) return <ErrorBox error={jobs.error} />; const items = jobs.data as Job[]; return <><PageIntro eyebrow="TRANSLATION / REALTIME" title="Translation jobs" description="SSE cập nhật chunk progress; REST/SQLite là nguồn dữ liệu authoritative." /><div className="panel">{items.map((job) => <JobRow key={job.id} job={job} detail />)}{!items.length && <Empty text="Chưa có job dịch." />}</div></>; }

function JobRow({ job, detail = false }: { job: Job; detail?: boolean }) { const tone = job.status === "completed" ? "good" : job.status === "failed" ? "bad" : "info"; return <div className="job-row"><div className="job-main"><strong>Chapter {job.chapter_number ?? "—"}</strong><span className="muted">{job.model_provider}/{job.model_name}</span>{detail && <small className="muted">{job.total_prompt_tokens} prompt tokens <span className="dot-separator">·</span> {job.total_duration_ms} ms</small>}</div><span className={`status-pill ${tone}`}>{job.status}</span></div>; }

function ContextPage() {
  const context = useQuery({ queryKey: ["context"], queryFn: api.context });
  const query = useQueryClient();
  const [source, setSource] = useState(""); const [translation, setTranslation] = useState(""); const [feedback, setFeedback] = useState<Feedback | null>(null);
  const mutation = useMutation({ mutationFn: () => api.upsertContext({ context_type: "term", source, translation }), onSuccess: () => { setSource(""); setTranslation(""); setFeedback({ kind: "success", text: "Mapping đã được lưu." }); query.invalidateQueries({ queryKey: ["context"] }); }, onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) });
  if (context.isLoading) return <Loading />; if (context.error) return <ErrorBox error={context.error} />;
  return <><PageIntro eyebrow="GLOSSARY / CONTEXT" title="Context" description="Mapping xác nhận và đề xuất được lưu qua application facade." /><div className="panel"><div className="form-row context-form"><div className="field-grow"><label htmlFor="context-source">Source term</label><input id="context-source" value={source} onChange={(e) => setSource(e.target.value)} placeholder="Tên nhân vật, địa danh…" /></div><div className="field-grow"><label htmlFor="context-translation">Bản dịch</label><input id="context-translation" value={translation} onChange={(e) => setTranslation(e.target.value)} placeholder="Bản dịch nhất quán" /></div><Button variant="primary" onClick={() => mutation.mutate()} disabled={!source.trim() || !translation.trim() || mutation.isPending} loading={mutation.isPending} loadingLabel="Đang lưu…">Lưu mapping</Button></div>{feedback && <FeedbackBox feedback={feedback} />}<div className="table-wrap"><table><thead><tr><th>Type</th><th>Source</th><th>Translation</th><th>Status</th></tr></thead><tbody>{(context.data as ContextItem[]).map((item) => <tr key={`${item.context_type}-${item.id}`}><td><span className="type-label">{item.context_type}</span></td><td>{item.source}</td><td>{item.translation}</td><td><StatusPill status={item.status} /></td></tr>)}</tbody></table>{!(context.data as ContextItem[]).length && <Empty text="Chưa có mapping nào. Thêm mapping đầu tiên ở phía trên." />}</div></div></>;
}

function ConflictsPage() { const conflicts = useQuery({ queryKey: ["conflicts"], queryFn: api.conflicts }); if (conflicts.isLoading) return <Loading />; if (conflicts.error) return <ErrorBox error={conflicts.error} />; const items = conflicts.data ?? []; return <><PageIntro eyebrow="CONTEXT / REVIEW" title="Conflicts" description="Các mapping cần được xem lại trước khi trở thành quy tắc authoritative." /><div className="panel">{items.map((conflict) => <div className="conflict" key={conflict.id}><div><strong>{conflict.source_key}</strong><p className="muted">Existing: {conflict.existing_value ?? "—"} <span className="dot-separator">·</span> Candidate: {conflict.candidate_value ?? "—"}</p></div><StatusPill status={conflict.status} /></div>)}{!items.length && <Empty text="Không có conflict mở." />}</div></>; }

function SettingsPage() {
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.providers });
  const query = useQueryClient();
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [key, setKey] = useState("");
  const [newProfile, setNewProfile] = useState({ id: "", provider: "gemini", model: "gemini-3.7-flash", base_url: "" });
  const saveKey = useMutation({ mutationFn: (profile: string) => api.saveProviderCredential(profile, key), onSuccess: () => { setKey(""); setFeedback({ kind: "success", text: "Credential đã được lưu an toàn." }); query.invalidateQueries({ queryKey: ["providers"] }); }, onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) });
  const activate = useMutation({ mutationFn: api.activateProvider, onSuccess: () => { setFeedback({ kind: "success", text: "Active profile đã được cập nhật." }); query.invalidateQueries({ queryKey: ["providers"] }); }, onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) });
  const create = useMutation({ mutationFn: () => api.createProvider({ profile_id: newProfile.id, provider: newProfile.provider, model: newProfile.model, base_url: newProfile.base_url || undefined }), onSuccess: () => { resetProfile(); setFeedback({ kind: "success", text: "Provider profile đã được tạo." }); query.invalidateQueries({ queryKey: ["providers"] }); }, onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) });
  if (providers.isLoading) return <Loading />;
  if (providers.error) return <ErrorBox error={providers.error} />;
  const profiles = providers.data?.profiles ?? [];
  const modelOptions = providers.data?.model_options?.[newProfile.provider] ?? [];
  const selectedPreset = modelOptions.some((option) => option.id === newProfile.model) ? newProfile.model : "";
  const selectProvider = (provider: string) => {
    const options = providers.data?.model_options?.[provider] ?? [];
    setNewProfile({ ...newProfile, provider, model: provider === "ollama" ? "qwen3:14b" : options[0]?.id ?? newProfile.model });
  };
  const resetProfile = () => setNewProfile({ id: "", provider: "gemini", model: "gemini-3.7-flash", base_url: "" });
  return <><PageIntro eyebrow="APPLICATION / PROVIDERS" title="Provider settings" description="Profile dùng chung cho mọi project. API key chỉ hiển thị trạng thái đã cấu hình." /><div className="panel"><div className="panel-heading"><div><span className="eyebrow">PROFILES</span><h3>Global provider profiles</h3></div><span className="muted">Active: {providers.data?.active_profile}</span></div>{profiles.map((profile) => <div className="job-row" key={profile.id}><div className="job-main"><strong>{profile.id}</strong><span className="muted">{profile.provider} / {profile.model}</span><small className="muted">{profile.credential_configured ? "Credential configured" : "Credential not configured"}</small></div><div className="action-buttons"><StatusPill status={profile.active ? "active" : "inactive"} /><Button onClick={() => activate.mutate(profile.id)} disabled={profile.active || activate.isPending}>Set active</Button>{profile.provider !== "ollama" && <><input aria-label={`Credential for ${profile.id}`} type="password" value={profile.active ? key : ""} onChange={(event) => setKey(event.target.value)} placeholder="API key" /><Button variant="primary" onClick={() => saveKey.mutate(profile.id)} disabled={!profile.active || !key.trim() || saveKey.isPending}>Save credential</Button></>}</div></div>)}{!profiles.length && <Empty text="Chưa có provider profile." />}</div><div className="panel"><div className="panel-heading"><div><span className="eyebrow">NEW PROFILE</span><h3>Thêm profile</h3></div></div><div className="form-row"><input aria-label="Profile id" value={newProfile.id} onChange={(e) => setNewProfile({ ...newProfile, id: e.target.value })} placeholder="gemini-default" /><select aria-label="Provider" value={newProfile.provider} onChange={(e) => selectProvider(e.target.value)}><option value="ollama">Ollama</option><option value="deepseek">DeepSeek</option><option value="gemini">Gemini</option></select>{newProfile.provider !== "ollama" && <select aria-label="Model preset" value={selectedPreset} onChange={(e) => setNewProfile({ ...newProfile, model: e.target.value || newProfile.model })}><option value="">Custom model ID…</option>{modelOptions.map((option) => <option key={option.id} value={option.id}>{option.label} · {option.status}</option>)}</select>}<input aria-label="Model" value={newProfile.model} onChange={(e) => setNewProfile({ ...newProfile, model: e.target.value })} placeholder={newProfile.provider === "ollama" ? "e.g. qwen3:14b" : "Custom model ID"} /><input aria-label="Base URL" value={newProfile.base_url} onChange={(e) => setNewProfile({ ...newProfile, base_url: e.target.value })} placeholder="Base URL (optional)" /><Button variant="primary" onClick={() => create.mutate()} disabled={!newProfile.id.trim() || !newProfile.model.trim() || create.isPending} loading={create.isPending}>Create</Button></div><p className="muted">Preset chỉ hiển thị cho DeepSeek/Gemini; bạn vẫn có thể nhập model ID tùy chỉnh.</p>{feedback && <FeedbackBox feedback={feedback} />}</div></>;
}

function ExportPage() { const [feedback, setFeedback] = useState<Feedback | null>(null); const mutation = useMutation({ mutationFn: api.exportProject, onSuccess: (result) => setFeedback({ kind: "success", text: `Đã xếp hàng operation ${result.operation_id}.` }), onError: (error: unknown) => setFeedback({ kind: "error", text: formatError(error) }) }); return <><PageIntro eyebrow="OUTPUT / LOCAL" title="Export" description="Tạo bản ghép trong thư mục exports của project." /><div className="panel actions"><div className="action-copy"><span className="action-icon" aria-hidden="true">↧</span><div><strong>Export project data</strong><p className="muted">Chọn định dạng muốn tạo. Tác vụ chạy nền để giao diện luôn phản hồi.</p></div></div><div className="action-buttons"><Button variant="primary" onClick={() => mutation.mutate("novel")} disabled={mutation.isPending} loading={mutation.isPending} loadingLabel="Đang export…">Export novel</Button><Button onClick={() => mutation.mutate("context")} disabled={mutation.isPending}>Export context YAML</Button></div>{feedback && <FeedbackBox feedback={feedback} />}</div></>; }

function DeveloperPage() { const tables = useQuery({ queryKey: ["tables"], queryFn: api.tables }); const [selected, setSelected] = useState(""); const table = useQuery({ queryKey: ["table", selected], queryFn: () => api.table(selected), enabled: Boolean(selected) }); return <><PageIntro eyebrow="DEVELOPER ONLY" title="Database inspector" description="Read-only viewer; audit có thể chứa source, prompt và translation." /><div className="panel"><div className="form-row table-select"><div className="field-grow"><label htmlFor="table">Table</label><select id="table" value={selected} onChange={(e) => setSelected(e.target.value)}><option value="">Chọn table…</option>{tables.data?.tables.map((name) => <option key={name}>{name}</option>)}</select></div>{selected && <span className="muted table-meta">{table.isFetching ? "Đang đọc…" : `${table.data?.rows.length ?? 0} rows`}</span>}</div>{table.error && <ErrorBox error={table.error} />}{table.data && <div className="table-wrap"><table><thead><tr>{table.data.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{table.data.rows.map((row, index) => <tr key={index}>{table.data.columns.map((column) => <td key={column} className="truncate">{row[column]}</td>)}</tr>)}</tbody></table>{!table.data.rows.length && <Empty text="Table này chưa có dữ liệu." />}</div>}</div></>; }

function PageIntro({ eyebrow, title, description }: { eyebrow: string; title: string; description?: ReactNode }) { return <div className="page-intro"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{description && <p className="muted">{description}</p>}</div></div>; }

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary"; loading?: boolean; loadingLabel?: string };
function Button({ variant = "secondary", loading = false, loadingLabel = "Đang xử lý…", children, className = "", disabled, ...props }: ButtonProps) { return <button type="button" {...props} className={`${variant} ${className}`.trim()} disabled={disabled || loading} aria-busy={loading || undefined}><span className="button-content">{loading && <span className="button-spinner" aria-hidden="true" />}{loading ? loadingLabel : children}</span></button>; }
function StatusPill({ status }: { status: string }) { const normalized = status.toLowerCase(); const tone = ["completed", "confirmed", "configured", "valid", "success"].includes(normalized) ? "good" : ["failed", "invalid", "error", "conflict"].includes(normalized) ? "bad" : "info"; return <span className={`status-pill ${tone}`}><span className="status-dot" />{status}</span>; }
function FeedbackBox({ feedback }: { feedback: Feedback }) { return feedback.kind === "error" ? <div className="error-box" role="alert">{feedback.text}</div> : <div className="success" role="status">{feedback.text}</div>; }
function Loading() { return <div className="panel loading" role="status"><span className="loading-spinner" aria-hidden="true" />Đang tải dữ liệu…</div>; }
function Empty({ text }: { text: string }) { return <div className="empty"><span className="empty-icon" aria-hidden="true">✦</span><p>{text}</p></div>; }
function ErrorBox({ error }: { error: unknown }) { return <div className="error-box" role="alert">{formatError(error)}</div>; }
function formatError(error: unknown) { return error instanceof ApiError ? `${error.code}: ${error.message}` : error instanceof Error ? error.message : "Đã xảy ra lỗi."; }

createRoot(document.getElementById("root")!).render(<React.StrictMode><QueryClientProvider client={queryClient}><App /></QueryClientProvider></React.StrictMode>);
