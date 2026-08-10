# Spec Update v2 — Native Windows UI

## 1. Mục tiêu

V2 chuyển Novel Translator từ workflow CLI-first sang desktop app native cho Windows.

Workflow chính:

```text
novel init <project-name>
        ↓
Mở Novel Translator
        ↓
Chọn thư mục project
        ↓
Cấu hình, nhập source, dịch, kiểm tra model, xử lý context và export trên UI
```

`novel init` tiếp tục là bước bootstrap duy nhất cần dùng từ CLI. App desktop là workflow chính cho các thao tác còn lại.

## 2. Phạm vi v2

- Native desktop UI tối giản, gọn gàng, chuyên nghiệp.
- Mở project bằng folder picker.
- Dashboard trạng thái project.
- Chỉnh toàn bộ cấu hình bằng form UI.
- Import và xem trước nội dung source.
- Chọn chapter/range để dịch.
- Theo dõi tiến trình theo chapter/chunk.
- Resume job bị gián đoạn.
- Xem source, prompt, context, output model, metrics và lỗi.
- Quản lý glossary/context và conflict.
- Export bản dịch và context.
- Đóng gói thành ứng dụng Windows.

Pause/cancel nâng cao, diff editor và thống kê nâng cao có thể để v2.1 sau khi MVP ổn định.

## 3. Kiến trúc UI

### Công nghệ đề xuất

Dùng PySide6/Qt Widgets:

- `QMainWindow` cho cửa sổ chính.
- Sidebar navigation.
- Qt Model/View cho danh sách chapter, job và context.
- `QThreadPool` hoặc worker thread cho import, dịch và export.
- Signal để cập nhật progress mà không khóa UI.

Entry point đề xuất:

```text
novel init <name>     # tạo project
novel app             # mở desktop app
```

Khi đóng gói có thể tạo `NovelTranslator.exe`.

### Application facade

UI không truy cập SQLAlchemy ORM trực tiếp. Tạo facade điều phối application layer:

```text
ApplicationFacade
├── open_project()
├── get_dashboard()
├── update_settings()
├── import_chapters()
├── list_chapters()
├── translate()
├── list_jobs()
├── get_chunk_detail()
├── list_context()
├── resolve_conflict()
└── export_novel()
```

Các API nên trả về DTO/Pydantic model thay vì ORM object.

### Project session

Tạo abstraction chứa project đang mở:

```python
class ProjectSession:
    project_path: Path
    settings: ProjectSettings
    novel: NovelDTO
```

Các service không còn tự phụ thuộc vào `Path.cwd()`, mà nhận `ProjectSession` hoặc `project_path` rõ ràng.

Các service cần refactor:

- `ProjectService`
- `ImportService`
- `TranslationService`
- `ExportService`
- `ContextService`

## 4. Các màn hình chính

### 4.1. Start / Open Project

- Chọn thư mục project.
- Hiển thị project gần đây.
- Kiểm tra `novel.yaml`, database và các thư mục cần thiết.
- Tự động chạy migration khi mở project cũ.
- Hiển thị lỗi project không hợp lệ một cách dễ hiểu.

### 4.2. Dashboard

Hiển thị:

- Tên project, title, ngôn ngữ nguồn/đích.
- Provider và model hiện tại.
- Tổng chapter theo trạng thái: imported, translated, failed.
- Job đang chạy.
- Conflict chưa xử lý.
- Các thao tác nhanh: Import, Translate, Export, Settings.

### 4.3. Source / Chapters

- Chọn thư mục input bằng folder picker.
- Preview file trước khi import.
- Danh sách chapter, số chapter, trạng thái và source hash.
- Xem nội dung source trực tiếp.
- Cảnh báo file sai tên, sai encoding hoặc trùng số chapter.
- Import lại khi source thay đổi.

### 4.4. Translation Jobs

- Chọn một hoặc nhiều chapter.
- Dịch tuần tự một range để giữ context.
- Các nút `Start`, `Resume`, `Force`.
- Progress theo chapter/chunk.
- Hiển thị token, thời gian và trạng thái lỗi.
- Lưu lịch sử các lần dịch.
- Chỉ cho phép một job ghi dữ liệu vào project tại một thời điểm trong MVP.

### 4.5. Results / Model Inspector

Mỗi chunk cần xem được:

- Source text.
- Prompt system.
- Prompt user đã render.
- Context snapshot.
- Previous translation tail.
- Output translation.
- Context updates từ model.
- Raw structured response.
- Provider, model và prompt version.
- Prompt tokens, output tokens và duration.
- Diagnostic/error response nếu thất bại.

### 4.6. Context / Glossary

- Danh sách character, location, organization và term.
- Filter theo type/status.
- Thêm, sửa, xóa mapping thủ công.
- Confirm hoặc reject candidate.
- Xem và xử lý conflict.
- Resolve bằng existing, candidate hoặc custom value.
- Import/export YAML.

### 4.7. Settings

Form cấu hình gồm:

- Project title, ngôn ngữ và genre.
- Provider: Ollama/DeepSeek.
- Base URL và model name.
- Temperature, top-p, context size và think mode.
- Timeout và retry.
- Chunk size.
- Continuity.
- Context auto-confirm.
- Validation.
- Prompt version.
- Log level.

`novel.yaml` tiếp tục là nguồn cấu hình chính. API key không được ghi vào YAML; UI nên lưu key trong Windows Credential Manager thông qua `keyring`, đồng thời vẫn hỗ trợ biến môi trường cũ.

### 4.8. Logs / Diagnostics

- Xem log theo ngày.
- Lọc lỗi theo job/chapter.
- Copy diagnostic.
- Mở thư mục `logs`.
- Không hiển thị hoặc ghi lộ API key.

## 5. Database và audit model call

Hiện tại `TranslationChunkORM` mới lưu `prompt_hash`, `context_snapshot_json`, output đã parse, metrics và lỗi. Để UI xem chính xác input/output của model, cần bổ sung migration.

### Đề xuất

Tạo bảng `model_call` riêng cho từng lần gọi model/retry, gồm tối thiểu:

- `id`.
- `translation_job_id`.
- `translation_chunk_id`.
- `attempt_number`.
- `provider`.
- `model_name`.
- `prompt_version`.
- `system_prompt`.
- `user_prompt`.
- `source_text` hoặc reference tới source chunk.
- `context_snapshot_json`.
- `previous_translation_tail`.
- `response_json`.
- `translated_text`.
- `diagnostic_json`.
- `prompt_hash`.
- `prompt_tokens`.
- `output_tokens`.
- `duration_ms`.
- `status`.
- `created_at`.

Không lưu API key hoặc request header nhạy cảm. Diagnostic từ provider phải tiếp tục redaction secret.

## 6. Application/query services

Bổ sung các API đọc dữ liệu cho UI:

- `ChapterQueryService`.
- `TranslationJobQueryService`.
- `ModelCallQueryService`.
- `ProjectHealthService`.
- `ConfigService`.

Các API cần hỗ trợ:

- Dashboard summary.
- Danh sách chapter và trạng thái.
- Danh sách job/lịch sử dịch.
- Chi tiết chunk.
- Chi tiết model call.
- Danh sách conflict.
- Kiểm tra provider/config.

## 7. Roadmap triển khai

### Phase 0 — UX và technology spike

- Vẽ wireframe cho Start, Dashboard, Source, Jobs, Results, Context và Settings.
- Tạo prototype PySide6.
- Kiểm tra build chạy được trên Windows.
- Chốt tên executable và cách cài đặt.

### Phase 1 — Project runtime

- Tạo `ProjectSession`.
- Refactor service bỏ phụ thuộc `Path.cwd()`.
- Kết nối CLI hiện tại qua facade mới.
- Thêm project validation và project health check.
- Viết test mở project từ bất kỳ thư mục nào.

### Phase 2 — Database và model audit

- Thêm migration schema v2.
- Tạo bảng `model_call`.
- Lưu prompt đã render, context, output, metrics và diagnostic.
- Bổ sung query API cho chapter/job/chunk/model call.
- Test nâng cấp project v1 lên v2.

### Phase 3 — UI shell, project, config và source

- Tạo app entrypoint.
- Xây Start/Open Project.
- Xây Dashboard cơ bản.
- Xây Settings editor có validation.
- Tích hợp Credential Manager.
- Xây source browser và import workflow.
- Chạy IO trong worker thread.

### Phase 4 — Translation, Results và Context

- Translation job monitor.
- Start/resume/force.
- Progress theo chunk.
- Results/model inspector.
- Glossary/context CRUD.
- Conflict resolution.
- Export novel/context.

### Phase 5 — Packaging và QA

- Build `NovelTranslator.exe`.
- Tạo installer hoặc bản portable.
- Test trên Windows sạch.
- Test project lớn và job bị gián đoạn.
- Test lỗi Ollama, DeepSeek, timeout và invalid response.
- Cập nhật README thành workflow UI-first.

## 8. Testing strategy

### Unit tests

- Project session và project path.
- Config validation/save/load.
- DTO/query services.
- Credential handling không làm lộ secret.
- Progress event mapping.

### Integration tests

- Init rồi open project.
- Upgrade project cũ.
- Import chapter, import trùng và source hash.
- Translate, resume và force.
- Persist model call audit.
- Context CRUD và conflict resolution.
- Export bản dịch.

### UI tests

- Open project hợp lệ/không hợp lệ.
- Settings validation.
- Import preview.
- Start job và nhận progress.
- UI không bị block khi model đang chạy.
- Hiển thị đúng prompt/output/diagnostic.

### Provider tests

- Ollama/DeepSeek success.
- Timeout và connection error.
- Retry.
- Invalid structured output.
- HTTP error có redaction.

## 9. Tiêu chí nghiệm thu v2

Người dùng phải có thể:

1. Chạy `novel init demo`.
2. Mở app và chọn thư mục `demo`.
3. Chỉnh model/config trong UI.
4. Chọn thư mục input và import chapter.
5. Xem source trước khi dịch.
6. Dịch một chapter hoặc một range.
7. Theo dõi progress mà UI không bị treo.
8. Resume job bị gián đoạn.
9. Xem source, prompt, context, output và metrics của model.
10. Xử lý glossary/conflict.
11. Xem bản dịch cuối và export `novel.txt`.

## 10. Quyết định và giả định

- V2 ưu tiên Windows desktop.
- PySide6 là lựa chọn UI ban đầu, cần xác nhận bằng prototype Phase 0.
- `novel init` không tự động mở app; app có màn hình chọn project.
- API key không lưu trong `novel.yaml`.
- Các CLI command cũ được giữ tạm để tương thích, nhưng không còn là workflow chính.
- MVP chỉ chạy một translation job ghi dữ liệu trên mỗi project tại một thời điểm.
