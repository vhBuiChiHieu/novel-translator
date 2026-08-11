# Đặc tả chuyển UI PySide6 sang Local Web App

**Trạng thái:** Đề xuất triển khai  
**Phạm vi:** Novel Translator chạy hoàn toàn tại máy người dùng  
**Quyết định kiến trúc:** Giữ Python domain/application/persistence hiện có; thay lớp trình bày PySide6 bằng SPA local cùng API loopback. Không chuyển dữ liệu, khóa API, hay quá trình dịch lên cloud.

## 1. Tóm tắt quyết định

Sản phẩm sẽ chuyển từ desktop UI PySide6 sang **local web application** gồm:

- Backend Python chạy một HTTP server chỉ tại `127.0.0.1`.
- Frontend SPA TypeScript/React được backend phục vụ cùng origin.
- SQLite, thư mục project, prompt, log, keyring, Ollama và DeepSeek tiếp tục chạy tại máy local qua tầng application hiện tại.
- REST dùng cho truy vấn/lệnh; Server-Sent Events (SSE) dùng cho tiến độ dịch và trạng thái tác vụ một chiều.
- PySide6 được giữ trong giai đoạn chuyển tiếp; chỉ loại bỏ khi web UI đạt feature parity và các tiêu chí nghiệm thu.

Mục tiêu là tăng tốc lặp UI/UX, cho phép giao diện hiện đại và tạo nền tảng cho các tính năng như tìm kiếm, bộ lọc, diff, audit, dashboard và editor nâng cao, mà không làm thay đổi quy tắc dịch hay mô hình dữ liệu hiện có.

## 2. Bối cảnh hiện tại

Backend hiện đã có ranh giới tốt để di trú:

- Domain không phụ thuộc UI, HTTP hay SQLAlchemy.
- `ApplicationFacade` là API hướng UI và chỉ trả về DTO, không để UI truy cập ORM trực tiếp.
- `TranslationService` xử lý tuần tự từng chunk, ghi SQLite và phát `TranslationProgress` qua callback (`job_started`, `chunk_started`, `chunk_completed`, `chunk_failed`, `job_completed`).
- Mỗi project giữ dữ liệu local: `novel.yaml`, `data/novel.db`, `source/`, `translated/`, `exports/` và `logs/`.
- Khóa DeepSeek được keyring quản lý; không được đưa vào `novel.yaml`, API response hay frontend state.

UI web là một adapter mới phía trên application layer, **không** là một backend song song truy vấn bảng SQLite hoặc gọi provider trực tiếp.

## 3. Mục tiêu và ngoài phạm vi

### 3.1. Mục tiêu

1. Cung cấp toàn bộ workflow UI hiện có: mở/reset project, cấu hình, nhập chương, dịch, theo dõi job/chunk, quản lý context/conflict, xem audit và export.
2. Dịch và xuất phải cho kết quả tương đương native UI khi cùng project, cấu hình, prompt version và provider response.
3. UI khởi động local, không yêu cầu internet ngoài kết nối mà provider đã cần.
4. Không thay đổi schema SQLite, domain rule, prompt contract hay behavior retry trong pha chuyển UI.
5. Mọi tác vụ dài chạy ngoài event loop/UI; browser không bị treo khi import, dịch hoặc export.
6. Có test tự động cho API contract, tiến độ realtime, lỗi và các luồng end-to-end quan trọng.

### 3.2. Ngoài phạm vi của đặc tả này

- SaaS/cloud hosting, đăng nhập người dùng, cộng tác nhiều người hoặc đồng bộ project.
- Mở API cho máy khác trong LAN/internet.
- Thay SQLite bằng database server.
- Viết lại model provider, domain context merger/retriever hoặc translation pipeline.
- Chạy đồng thời nhiều tiến trình ghi vào cùng một project.
- Mobile application hay PWA offline độc lập khỏi backend Python.

## 4. Nguyên tắc thiết kế bắt buộc

### 4.1. Local-first và riêng tư

- Server chỉ bind `127.0.0.1` (IPv4 loopback); không bind `0.0.0.0`, địa chỉ LAN hoặc IPv6 wildcard.
- CORS không được bật cho origin tùy ý. Frontend và API dùng cùng origin.
- Browser không truy cập trực tiếp SQLite, filesystem, model API hay keyring.
- Backend không log API key, header xác thực, token khởi động hay dữ liệu chẩn đoán chưa được sanitize.
- Dữ liệu chỉ rời máy qua endpoint Ollama/DeepSeek mà cấu hình project đã chọn.

### 4.2. Bảo toàn application boundary

- Route handler chỉ gọi `ApplicationFacade` hoặc application service/DTO được bổ sung có chủ đích.
- Route handler không import ORM model, không tạo SQL query và không tự render prompt.
- Không trả raw ORM, exception traceback, API key hoặc path không cần thiết cho client.
- DTO API dùng Pydantic; contract được version dưới tiền tố `/api/v1`.

### 4.3. Một project, một hàng đợi ghi

Native UI hiện thực thi range translation tuần tự. Local web phải giữ invariant này: tại một thời điểm chỉ có một operation có thể ghi/dịch cho một project.

- Một `ProjectRuntime` quản lý project đang mở, lock và event broker của process hiện tại.
- Query read-only có thể chạy song song nếu không gây lock SQLite.
- Import, reset, update settings, context mutation, translate và export được điều phối qua project mutation queue.
- Nút dịch chapter/range bị vô hiệu hóa hoặc trả `409 Conflict` khi project đang có mutation không tương thích.
- Không giữ chung một instance mutable của `ApplicationFacade` giữa request thread. Mỗi operation tạo facade/session từ `project_path`, hoặc runtime bảo đảm ownership tuần tự.

## 5. Kiến trúc mục tiêu

```text
┌──────────────────────────────────────────────────────────┐
│ Browser: React + TypeScript SPA                            │
│ dashboard · import · chapters · translation · context      │
└───────────────┬───────────────────────────────┬───────────┘
                │ REST (/api/v1)                │ SSE (/events)
┌───────────────▼───────────────────────────────▼───────────┐
│ Local API: FastAPI + Pydantic                              │
│ auth bootstrap · project runtime · operation queue         │
│ facade adapter · event broker · static SPA                 │
└─────────────────────────────┬─────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────┐
│ Existing Python application                                │
│ ApplicationFacade · services · domain · providers          │
└─────────┬───────────────────────────┬──────────────────────┘
          │                           │
     SQLite/project files          keyring + Ollama/DeepSeek
```

### 5.1. Công nghệ được chọn

| Thành phần | Quyết định | Lý do |
|---|---|---|
| API server | FastAPI + Uvicorn | Pydantic 2 tương thích codebase, OpenAPI/test client tốt, SSE dễ triển khai. |
| Web client | React + TypeScript + Vite | Iteration nhanh, hệ sinh thái mạnh cho bảng, state và UI component. |
| Giao diện | Tailwind CSS + component primitives có kiểm soát | Tạo design system nhất quán mà không khóa vào một theme desktop. |
| Server state | TanStack Query | Cache/invalidate REST resource và biểu diễn loading/error rõ ràng. |
| Client state ngắn hạn | Zustand hoặc React context nhỏ | Chỉ lưu UI state; không mirror database dài hạn. |
| Realtime | SSE | Tiến độ từ server sang client là một chiều; đơn giản hơn WebSocket trong pha này. |
| E2E | Playwright | Kiểm thử UI thật, route, SSE và workflow local. |

Không dùng Electron ở pha đầu vì backend Python đã tồn tại và Electron làm tăng footprint. Khi cần executable có native menu, folder picker chắc chắn và tự khởi động backend, có thể bọc SPA bằng **Tauri** ở pha sau mà không đổi API.

### 5.2. Cấu trúc thư mục mục tiêu

```text
src/novel_translator/
  application/                 # Giữ nguyên, là business boundary
  domain/                      # Giữ nguyên
  infrastructure/              # Giữ nguyên provider/persistence/prompting
  web/
    __init__.py
    app.py                     # FastAPI factory
    cli.py                     # entry point novel-web
    dependencies.py            # runtime/facade/auth dependencies
    runtime.py                 # ProjectRuntime, queue, event broker
    routes/
      health.py
      projects.py
      settings.py
      imports.py
      chapters.py
      translations.py
      context.py
      exports.py
      diagnostics.py
    schemas/                   # request/response Pydantic schemas
    static/                    # output đã build của frontend, không sửa tay
web-client/
  src/
    app/
    features/{dashboard,projects,import,chapters,translation,context,settings,audit}/
    components/
    api/
    styles/
  tests/
```

`web-client/` là source frontend. Artifact build được copy/version vào `src/novel_translator/web/static/` tại bước package; không commit `node_modules`.

## 6. Khởi động, lifecycle và xác thực local

### 6.1. Entry point

Thêm entry point `novel-web`:

```text
novel-web [--project PATH] [--port PORT] [--no-open]
```

- Không truyền `--port`: bind port rảnh do OS chọn (`0`).
- Có `--port`: fail rõ ràng nếu port bận; không tự chuyển sang interface khác.
- `--project`: cố gắng mở project ngay; nếu thiếu/không hợp lệ, trang project picker hiển thị lỗi validation.
- Mặc định mở browser hệ thống sau khi server sẵn sàng; `--no-open` in local URL để dùng trong browser đã mở.
- Khi browser đóng, server không tự dừng ngay. Cung cấp action **Quit local server** và xử lý `Ctrl+C` sạch sẽ.

### 6.2. Bootstrap token

Port loopback không đủ là authentication boundary. Mỗi lần khởi động:

1. Server sinh token ngẫu nhiên ít nhất 256 bit.
2. Browser được mở tại URL có token trong **fragment**, ví dụ `http://127.0.0.1:43123/#/launch/<token>`; fragment không được gửi lên HTTP server.
3. SPA gửi `POST /api/v1/session/bootstrap` với token trong header `X-Local-App-Token`.
4. Server kiểm tra token, đặt cookie `HttpOnly`, `Secure` khi phù hợp, `SameSite=Strict`, scope `/`; SPA xóa fragment bằng `history.replaceState`.
5. API/SSE sau đó yêu cầu cookie và kiểm tra `Origin`/`Host` loopback hợp lệ.

Token chỉ nằm trong memory, hết hiệu lực khi server dừng và không được ghi log. Nếu user mở lại URL sau khi process kết thúc, phải hiển thị “Local server is no longer running”, không tự kết nối sang host khác.

### 6.3. Shutdown và recovery

- Shutdown đóng SSE connections, chờ operation hiện tại trong thời gian cấu hình được, sau đó báo rõ nếu buộc dừng.
- Không được kill provider request hoặc corrupt SQLite bằng thread daemon không kiểm soát.
- Khi khởi động lại, dashboard đọc trạng thái DB. Job/chunk dở dang hiển thị là interrupted/partial và người dùng có thể dùng Resume theo behavior backend hiện có.
- UI phải reload được mà không mất translation đang chạy; nó re-fetch job state và reconnect SSE.

## 7. Hợp đồng API v1

Mọi response lỗi dùng cấu trúc:

```json
{
  "error": {
    "code": "PROJECT_NOT_OPEN",
    "message": "No project is open.",
    "details": {}
  }
}
```

`message` an toàn để hiển thị. `details` chỉ chứa dữ liệu không nhạy cảm. Mapping tối thiểu: validation `422`, không có project `409`, không tìm thấy `404`, conflict/busy `409`, lỗi provider/operation `502` hoặc `500` theo phân loại đã sanitize.

### 7.1. Session và project

| Method | Route | Hành vi |
|---|---|---|
| `POST` | `/api/v1/session/bootstrap` | Đổi startup token lấy local session cookie. |
| `GET` | `/api/v1/health` | Version app, trạng thái runtime; không có credential/path nhạy cảm. |
| `GET` | `/api/v1/projects/current` | Project session hiện mở hoặc trạng thái chưa mở. |
| `POST` | `/api/v1/projects/open` | Validate và mở project từ absolute local path. |
| `POST` | `/api/v1/projects/reset` | Reset sau confirmation payload bắt buộc. |
| `GET` | `/api/v1/dashboard` | `DashboardDTO` hiện có. |

Request mở project có `{ "path": "C:\\..." }`. Phase 1 dùng field path + Recent Projects; không cho browser upload/copy nguyên thư mục source. Pha Tauri có thể thay bằng native directory picker nhưng vẫn gọi route này với path đã chọn.

### 7.2. Cấu hình và credential

| Method | Route | Hành vi |
|---|---|---|
| `GET` | `/api/v1/settings` | Trả config an toàn cho UI; không bao giờ trả DeepSeek API key. |
| `PATCH` | `/api/v1/settings` | Gọi `ApplicationFacade.update_settings`; validate trước ghi `novel.yaml`. |
| `PUT` | `/api/v1/settings/model-api-key` | Gọi `set_api_key`; body và response là write-only. |
| `GET` | `/api/v1/settings/model-api-key/status` | Chỉ trả `{ "configured": true|false }`. |

API key phải bị redact khỏi browser devtools response, log server, exception, test snapshot và database audit.

### 7.3. Import và chapters

| Method | Route | Hành vi |
|---|---|---|
| `POST` | `/api/v1/import/preview` | Preview source directory bằng `preview_import`. |
| `POST` | `/api/v1/imports` | Queue import qua `import_chapters`; trả `operation_id`. |
| `GET` | `/api/v1/operations/{operation_id}` | Trạng thái `queued/running/completed/failed`. |
| `GET` | `/api/v1/chapters?status=` | Danh sách `ChapterDTO`. |
| `GET` | `/api/v1/chapters/{number}` | Chi tiết một chapter. |

Import là operation ghi và phải phát event `operation_started`, `import_completed` hoặc `operation_failed`. Pha đầu có thể chỉ phát start/completion nếu service chưa có callback granular; không giả lập phần trăm không có dữ liệu thật.

### 7.4. Translation, job và realtime

| Method | Route | Hành vi |
|---|---|---|
| `POST` | `/api/v1/translations` | Queue dịch một chapter; body có `chapter_number`, `resume`, `force`. |
| `POST` | `/api/v1/translations/range` | Queue dịch range tuần tự; body có `first`, `last`, `resume`, `force`. |
| `GET` | `/api/v1/translation-jobs?chapter_number=` | `list_jobs`. |
| `GET` | `/api/v1/translation-chunks/{chunk_id}` | `get_chunk_detail`. |
| `GET` | `/api/v1/events` | SSE event stream của local session/project. |
| `POST` | `/api/v1/operations/{operation_id}/cancel` | Đánh dấu yêu cầu cancel; chỉ có hiệu lực ở chunk boundary trong pha tương thích. |

`POST /translations*` trả ngay `202 Accepted` với:

```json
{
  "operation_id": "uuid",
  "status": "queued",
  "chapter_numbers": [12]
}
```

Mỗi event SSE có `id`, `event`, `data`; event IDs tăng dần trong một server lifetime. Event tiêu chuẩn:

```json
{
  "operation_id": "uuid",
  "event": "chunk_completed",
  "chapter_number": 12,
  "chunk_index": 4,
  "total_chunks": 11,
  "duration_ms": 1820,
  "error": null,
  "at": "2026-08-11T10:00:00Z"
}
```

- Bridge `TranslationProgress` hiện có sang SSE, không suy đoán progress từ polling.
- Event broker giữ buffer tối thiểu 500 event gần nhất để browser reconnect bằng `Last-Event-ID`; nếu ID quá cũ, client re-fetch `/translation-jobs` và `/operations/{id}`.
- UI cập nhật progress từ SSE nhưng dữ liệu authoritative (job/chunk/context) luôn được re-fetch từ REST khi operation hoàn tất hoặc reconnect.
- Trong pha đầu, cancel chỉ ngăn chunk/chapter kế tiếp; không hứa hẹn cancel một HTTP call đang bay tới provider. UI phải hiển thị rõ “Stopping after current chunk”.

### 7.5. Context, conflict, audit, export và inspector

| Method | Route | Hành vi |
|---|---|---|
| `GET` | `/api/v1/context?type=&status=` | `list_context`. |
| `POST` | `/api/v1/context` | `upsert_context`. |
| `DELETE` | `/api/v1/context/{type}/{source}` | `delete_context`; source URL-encoded. |
| `GET` | `/api/v1/context/conflicts` | `list_conflicts`. |
| `POST` | `/api/v1/context/conflicts/{id}/resolve` | `resolve_conflict`. |
| `GET` | `/api/v1/model-calls?chunk_id=` | Audit calls đã sanitize. |
| `POST` | `/api/v1/exports` | Queue/gọi `export_novel`; trả output path an toàn để hiển thị. |
| `GET` | `/api/v1/database/tables` | Inspector developer-only. |
| `GET` | `/api/v1/database/tables/{name}` | `get_database_table`; developer-only. |

Database inspector không phải UI chính. Nó nằm sau một “Developer tools” toggle, có cảnh báo dữ liệu audit có thể chứa source/prompt/translation, và tuyệt đối không có query SQL tự do.

## 8. Thiết kế UX và feature parity

### 8.1. Navigation

Sidebar desktop-first gồm: **Project**, **Dashboard**, **Import**, **Chapters**, **Translation Jobs**, **Context**, **Conflicts**, **Settings**, **Export** và **Developer tools**. Không cần responsive mobile trong pha đầu, nhưng layout phải hoạt động tốt từ 1024 px trở lên và không phụ thuộc kích thước cửa sổ cố định.

### 8.2. Các màn bắt buộc

1. **Project picker:** mở recent project hoặc dán/chọn local path; hiển thị lỗi `novel.yaml`/database/directory thiếu từ project validation.
2. **Dashboard:** tên project, language, provider/model, counters, running jobs, conflict count, health checks và quick actions.
3. **Import:** source path, preview chapter list, import confirmation, trạng thái operation và error recovery.
4. **Chapters:** table có search, status filter, chapter detail drawer; action translate/resume/force có confirm khi cần.
5. **Translation jobs:** progress toàn chapter/range, progress per chunk, duration/token/error, reconnect state và link tới chunk/audit detail.
6. **Context:** tab/type filter, search, add/edit/delete confirmed/proposed mapping; tất cả mutation xác nhận kết quả từ server.
7. **Conflicts:** giải thích source/current/proposed value, chọn resolve action và hiển thị outcome.
8. **Settings:** form model/chunk/context/continuity/validation; API-key control write-only với chỉ báo configured.
9. **Export:** export action, output location, link copy-path/open-folder (Tauri phase) và lịch sử action phiên hiện tại.
10. **Developer tools:** table viewer read-only và model-call inspector đã sanitize.

### 8.3. UX requirements

- Dùng Vietnamese là locale mặc định; chuỗi kỹ thuật/provider có thể giữ nguyên English.
- Có loading, empty, error và success state cho mọi page/action.
- Toast không được là nơi duy nhất chứa lỗi; lỗi tác động thao tác phải còn thấy trong page/panel.
- Các hành động phá huỷ hoặc có chi phí: reset, overwrite import, force translation, delete context, resolve conflict phải có confirmation rõ hậu quả.
- Chỉ disable đúng action không hợp lệ; bảng/list vẫn xem được trong khi backend dịch.
- Keyboard focus, semantic label, contrast và thông báo screen-reader cho progress/error phải đạt mức WCAG 2.1 AA ở các flow chính.

## 9. Runtime và concurrency

### 9.1. Operation model

`Operation` là khái niệm runtime, không thay thế `TranslationJobORM`:

```text
Operation
  id: UUID
  kind: import | translate_chapter | translate_range | export | reset | settings_update | context_mutation
  project_path: Path
  status: queued | running | cancelling | completed | failed | cancelled
  created_at / started_at / completed_at
  result: JSON-safe summary
  error: sanitized error
```

- Operations chỉ lưu in-memory trong pha đầu; translation truth vẫn là DB job/chunk.
- Operation dài chạy trong worker thread/executor; route async không gọi hàm blocking trực tiếp.
- Worker publish event thread-safe qua broker; broker là thành phần duy nhất biết về SSE clients.
- Dùng `asyncio.to_thread`/AnyIO thread pool hoặc executor có giới hạn. Không dùng FastAPI `BackgroundTasks` như hàng đợi bền vững.
- Nếu process restart, in-memory operation mất đi nhưng DB vẫn là source of truth; UI giải quyết bằng refresh job/dashboard.

### 9.2. Trạng thái lỗi

| Tình huống | Backend | UI |
|---|---|---|
| Provider/chunk lỗi | Giữ behavior persist diagnostic đã sanitize, job partial/failed | Hiện chunk lỗi, action Resume và audit detail. |
| Source thay đổi | Không tạo/tiếp tục job không hợp lệ | Báo rõ source đã thay đổi; hướng dẫn import/review. |
| Project bận | `409 PROJECT_BUSY` với operation đang chạy | Hiện banner progress và link operation. |
| SSE mất kết nối | Reconnect exponential backoff, dùng `Last-Event-ID` | Badge “Reconnecting”; polling REST nhẹ chỉ làm fallback. |
| Server dừng | HTTP/SSE fail | Màn connection lost, không retry sang mạng ngoài. |
| SQLite/database invalid | Dùng validation hiện có | Show project health errors và chặn mutation. |

## 10. Bảo mật và dữ liệu nhạy cảm

1. Không có endpoint, event, OpenAPI example hay UI state trả API key.
2. Duy trì sanitization provider diagnostic trước logging/persist/display.
3. Xác thực startup token bắt buộc cho cả REST và SSE (trừ static assets/bootstrap/health tối thiểu); cookie không được chấp nhận từ origin khác.
4. Kiểm tra `Host`, `Origin` và method/content type đối với endpoint mutation để giảm local cross-site request risk.
5. Không sử dụng remote CDN trong bản production; bundle asset cục bộ để không lộ usage/telemetry và vẫn chạy offline.
6. Không hiển thị absolute source/export path trong event chung nếu không cần; REST page có quyền local session mới đọc được.
7. Không tự gửi analytics/telemetry. Nếu thêm về sau phải opt-in riêng.
8. Content Security Policy production phải chặn third-party script và chỉ cho phép `self`, cùng kết nối SSE/API same-origin.

## 11. Kế hoạch di trú

### Pha 0 — Khóa hành vi và chuẩn bị (không đổi UI)

- Bổ sung/hoàn thiện integration test cho `ApplicationFacade`: dashboard, config, import, translate/resume/force, context/conflict, export.
- Tạo DTO/schema còn thiếu để API không phải rò rỉ ORM.
- Ghi nhận manual acceptance baseline của native UI trên một fixture novel nhỏ và một job nhiều chunk.
- Xác định chính xác các feature native đang được dùng; database inspector được đánh dấu developer-only.

**Exit:** Core behavior có test độc lập khỏi PySide6 và không có route/API code nào cần truy cập ORM.

### Pha 1 — Local server foundation

- Thêm extra dependency `.[web]`, FastAPI app factory, `novel-web`, static asset serving và startup-token bootstrap.
- Implement `ProjectRuntime`, serial mutation queue, `Operation`, exception-to-error mapper, health/current-project/dashboard API.
- Scaffold React/Vite, app shell, query client, error boundary, project picker và dashboard read-only.

**Exit:** `novel-web --project <path>` mở browser, hiển thị dashboard thực từ project local; không bind ra LAN và không lộ credential.

### Pha 2 — CRUD/project parity

- Implement settings (kể cả key status/write-only), import preview/import, chapter list/detail, context CRUD, conflicts và export.
- Thêm state/loading/error/confirmation UX và recent project store local (chỉ path được user chọn).
- Implement API contract/integration tests.

**Exit:** Người dùng hoàn thành setup → import → context/conflict → export mà không cần PySide6.

### Pha 3 — Translation realtime parity

- Bridge `TranslationProgress` vào event broker/SSE.
- Thêm translation operation queue, chapter/range command, jobs/chunk/audit route và progress UI.
- Implement SSE reconnect, reload recovery, source-changed, partial failure, resume/force và cancel-at-boundary behavior.
- E2E test bằng mocked provider; test không có duplicate translation khi user double-click hoặc reload page.

**Exit:** Dịch chapter/range nhiều chunk, theo dõi realtime, lỗi/resume và audit hoạt động tương đương native UI.

### Pha 4 — Polish, packaging và cutover

- Hoàn thiện visual system, keyboard/accessibility, responsive desktop và performance profiling.
- Build frontend trong CI/package, test asset manifest, manual smoke test trên Windows bản phân phối.
- Chạy song song với PySide6 trong một release; `novel-web` được khuyến nghị, native được gắn deprecation notice nhưng không xóa ngay.
- Sau một chu kỳ ổn định: đổi entry point chính, bỏ dependency/runtime PySide6 nếu không còn cần; Tauri là lựa chọn packaging kế tiếp chứ không là điều kiện cutover.

**Exit:** Tất cả acceptance criteria đạt, không có blocker data/security, và người dùng có thể hoàn thành mọi workflow production qua web UI.

## 12. Kiểm thử và quality gate

### 12.1. Test bắt buộc

- **Unit:** runtime queue, event broker, auth bootstrap, error mapper, schema validation, serializers.
- **API integration:** routes gọi facade/service thật với temporary project SQLite; test `409` busy, malformed request, missing project và key redaction.
- **Provider integration:** giữ test mocked HTTP hiện có; thêm kiểm tra event translation không lộ raw credential/diagnostic.
- **E2E Playwright:** open project, import preview/import, translate nhiều chunks, SSE progress, page reload giữa job, failed chunk/resume, conflict resolve, export.
- **Regression:** native UI test hiện có (trong thời gian transition) và application/infrastructure test phải tiếp tục xanh.
- **Manual Windows:** startup, browser launch/no-open, shutdown, local firewall/loopback check, paths Unicode, database migrations và một project lớn.

### 12.2. Quality gate

Trước merge/cutover, chạy tối thiểu:

```text
ruff check .
mypy src/novel_translator --exclude migrations
pytest -q
npm --prefix web-client run lint
npm --prefix web-client run test
npm --prefix web-client run build
npm --prefix web-client exec playwright test
```

CI phải cache dependency nhưng không publish/bundle API keys, fixture source có bản quyền hay project thật của user.

## 13. Tiêu chí nghiệm thu

1. `novel-web` chạy ở `127.0.0.1` và không thể truy cập qua LAN.
2. Local session bootstrap token là bắt buộc; API key không xuất hiện trong browser/API/server log/test artifact.
3. Mở một project hợp lệ hiển thị dashboard cùng số liệu với `ApplicationFacade.get_dashboard()`.
4. Settings update và API-key save vẫn lưu đúng `novel.yaml`/keyring, key chỉ hiển thị trạng thái configured.
5. Import preview và import cho kết quả chapter tương đương UI cũ.
6. Translation chapter và range thực thi tuần tự, không block browser; mỗi progress callback có event SSE tương ứng trong tối đa 500 ms ở local normal load.
7. Reload tab/reconnect SSE không tạo job trùng; UI khôi phục trạng thái từ REST/DB.
8. Job lỗi source changed/provider được hiển thị an toàn và Resume/Force tuân theo behavior hiện có.
9. Context CRUD, conflict resolution, model call view và export có feature parity với native UI.
10. Không route nào truy cập ORM trực tiếp; DTO/schema là contract giữa UI và application layer.
11. `ruff`, `mypy`, toàn bộ pytest và Playwright E2E đều pass.
12. Web UI đạt keyboard navigation cơ bản, semantic labels, contrast AA ở các màn/flow chính.
13. Native PySide6 chỉ bị gỡ sau khi release transition đạt các tiêu chí trên.

## 14. Rủi ro và phương án giảm thiểu

| Rủi ro | Ảnh hưởng | Giảm thiểu |
|---|---|---|
| Viết lại backend thay vì chỉ UI | Cao | Bắt buộc dùng facade/service; làm parity test từ pha 0. |
| SQLite contention do web request song song | Cao | Một mutation queue mỗi project; range translation tuần tự; test busy states. |
| Mất progress khi reload | Trung bình | SSE reconnect + event buffer; REST/DB là authoritative recovery. |
| Lộ API key qua API/log | Cao | Write-only endpoint, sanitize test và automated redaction assertion. |
| Browser file API không chọn được folder tốt | Trung bình | Pha 1 nhập path/recent projects; Tauri/native picker là enhancement có chủ đích. |
| Scope creep sang cloud/multi-user | Cao | Giữ non-goals; mọi quyết định network/auth mới cần spec riêng. |
| Bundle frontend lệch version backend | Trung bình | Build static asset trong package/CI; health endpoint báo app version và manifest check. |

## 15. Các quyết định cần chốt trước khi bắt đầu Pha 1

1. Xác nhận React + TypeScript + Vite là frontend stack chính thức.
2. Xác nhận FastAPI + SSE là transport đầu tiên; chỉ dùng WebSocket khi có yêu cầu client-to-server realtime thực sự.
3. Xác nhận phase đầu dùng local-path picker thay vì bắt buộc native folder dialog.
4. Xác nhận PySide6 được giữ cho đến hết Pha 4 và không cho hai UI cùng chạy mutation trên cùng project.
5. Xác nhận Tauri là lựa chọn packaging tương lai nếu cần desktop shell, không đưa vào critical path của web migration.

