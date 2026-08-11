# Novel Translator

Ứng dụng Windows local-first để dịch tiểu thuyết tiếng Trung sang tiếng Việt. Giao diện web local là workflow chính; PySide6 vẫn được giữ trong giai đoạn chuyển tiếp.

## Yêu cầu

- Python 3.12
- Một nhà cung cấp mô hình:
  - **Ollama** (mặc định), chạy cục bộ tại `http://localhost:11434`; hoặc
  - **DeepSeek API**, với API key trong biến môi trường.

## Cài đặt

Tại thư mục mã nguồn của dự án, tạo môi trường ảo và cài công cụ:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Để dùng giao diện Windows, cài thêm dependency desktop:

```powershell
pip install -e ".[desktop]"
```

Nếu PowerShell chặn việc kích hoạt môi trường ảo, chạy lệnh sau cho riêng cửa sổ hiện tại rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Dùng nhanh với Ollama

Ví dụ dưới đây dùng mô hình mặc định `qwen3:14b`. Hãy bảo đảm Ollama đang chạy và mô hình này đã được tải về trước khi dịch.

### 1. Mở một project

`novel-web` mở project đã có `novel.yaml` và database. Project Picker cũng cho phép tạo project mới bằng cách nhập thư mục cha và tên project. Có thể mở project có sẵn trực tiếp bằng `--project`:

```powershell
novel-web --project C:\path\to\tien-hiep-demo
```

Một project hợp lệ có cấu trúc:

```text
tien-hiep-demo/
├── novel.yaml          # cấu hình dự án
├── data/novel.db       # cơ sở dữ liệu SQLite
├── source/             # bản nguồn đã nhập
├── translated/         # từng chương đã dịch
├── exports/            # bản ghép và ngữ cảnh xuất ra
└── logs/               # nhật ký chạy
```

### Mở ứng dụng desktop

Chạy app từ bất kỳ thư mục nào sau khi cài desktop dependency:

```powershell
novel-translator
```

Chọn thư mục `tien-hiep-demo` trong màn hình Start / Open. App tự kiểm tra project và chạy migration khi mở project cũ. Các màn hình Dashboard, Source / Chapters, Translation Jobs, Results, Context, Settings và Logs hỗ trợ:

- xem trạng thái chapter/job/conflict và health của project;
- preview rồi import source;
- dịch một chapter hoặc một range bằng worker nền, theo dõi chunk progress và resume/force;
- xem source, prompt đã render, context snapshot, output, diagnostic và metrics của từng model call;
- chỉnh cấu hình đã validate, lưu DeepSeek key trong Windows Credential Manager qua `keyring`;
- quản lý glossary/context và export bản dịch hoặc context YAML.

### 2. Kiểm tra hoặc chỉnh cấu hình

Mở `novel.yaml`. Cấu hình mặc định dùng Ollama cục bộ:

```yaml
model:
  provider: ollama
  base_url: http://localhost:11434
  name: qwen3:14b
  request_timeout_seconds: 300
  max_retries: 2
  options:
    temperature: 0.2
    top_p: 0.9
    num_ctx: 16384
    think: false
```

Đổi `model.name` nếu bạn đã tải một model Ollama khác. Có thể ghi đè URL và tên model cho phiên PowerShell hiện tại mà không sửa YAML:

```powershell
$env:NOVEL_TRANSLATOR_OLLAMA_URL = "http://localhost:11434"
$env:NOVEL_TRANSLATOR_MODEL = "qwen3:14b"
```

Các thiết lập dịch quan trọng khác nằm trong `translation`:

- `prompt_version`: `translation-v1` hoặc `translation-v2`.
- `chunk`: kích thước đoạn xử lý; mặc định mục tiêu 6.000 ký tự, tối đa 10.000.
- `continuity`: mặc định gửi 3 đoạn cuối của phần dịch trước cho phần kế tiếp trong cùng chương.

Không cần sửa các giá trị này cho lần dùng đầu tiên.

### 3. Chuẩn bị chương nguồn

Tạo một thư mục bất kỳ chứa các tệp UTF-8. Mỗi tệp phải tên đúng mẫu `chapter_<số>.txt`; số không bắt buộc đủ bốn chữ số.

```text
input/
├── chapter_1.txt
├── chapter_2.txt
└── chapter_003.txt
```

Không để các tệp `.txt` có tên khác trong thư mục nhập; màn hình Source / Chapters của ứng dụng sẽ báo lỗi để tránh gán sai số chương. Tại giao diện này, bạn có thể preview và nhập source, dịch chapter hoặc range, resume/force job, quản lý context và export bản dịch.

## Dùng DeepSeek API

Trong `novel.yaml`, đổi phần model, ví dụ:

```yaml
model:
  provider: deepseek
  name: deepseek-v4-flash
  request_timeout_seconds: 300
  max_retries: 2
  options:
    temperature: 0.2
    top_p: 0.9
    num_ctx: 16384
    think: false
```

Đặt API key trong màn hình Settings; ứng dụng lưu nó trong Windows Credential Manager, không ghi vào `novel.yaml`. Adapter DeepSeek dùng endpoint Chat Completions và yêu cầu đầu ra JSON có cấu trúc.

### Mở ứng dụng web local

Cài web extra và chạy:

```powershell
pip install -e ".[web,dev]"
novel-web --project C:\path\to\tien-hiep-demo
```

Server chỉ bind `127.0.0.1`; mặc định chọn port rảnh và mở browser bằng startup token trong URL fragment. Dùng `--no-open` để in URL và tự mở bằng browser:

```powershell
novel-web --project C:\path\to\tien-hiep-demo --no-open
```

Web app dùng REST `/api/v1` cho truy vấn/lệnh và SSE `/api/v1/events` cho tiến độ. Startup token đổi lấy cookie `HttpOnly`, không được ghi vào project, SQLite, log hoặc frontend state. DeepSeek API key chỉ đi qua endpoint write-only và keyring; settings API chỉ trả dữ liệu an toàn.

Frontend source nằm trong `web-client/`. Build static artifact vào package bằng:

```powershell
npm --prefix web-client install
npm --prefix web-client run build
```

Artifact build cần được copy vào `src/novel_translator/web/static/` trước khi đóng gói bản phát hành.

## Xử lý sự cố thường gặp

- **Không parse được số chương**: đổi tên tệp thành `chapter_1.txt`, `chapter_002.txt`… và dùng mã hóa UTF-8.
- **Không kết nối được Ollama**: khởi động Ollama, kiểm tra model đã được tải và URL `model.base_url` trong Settings.
- **DeepSeek báo thiếu khóa**: thêm API key trong Settings.

Nhật ký dự án được lưu trong `logs/`.

## Phát triển và kiểm tra

Chạy từ thư mục repository:

```powershell
ruff check .
mypy src\novel_translator --exclude migrations
pytest -q
```
