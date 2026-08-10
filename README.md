# Novel Translator

Ứng dụng Windows local-first để dịch tiểu thuyết tiếng Trung sang tiếng Việt. Giao diện desktop là workflow chính; CLI vẫn được giữ để bootstrap và tương thích.

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
novel --help
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

### 1. Tạo dự án

```powershell
novel init tien-hiep-demo
cd tien-hiep-demo
```

Lệnh tạo cấu trúc sau:

```text
tien-hiep-demo/
├── novel.yaml          # cấu hình dự án
├── data/novel.db       # cơ sở dữ liệu SQLite
├── source/             # bản nguồn đã nhập
├── translated/         # từng chương đã dịch
├── exports/            # bản ghép và ngữ cảnh xuất ra
└── logs/               # nhật ký chạy
```

Từ bước này trở đi, luôn chạy các lệnh `novel` trong thư mục chứa `novel.yaml`.

### Workflow desktop (khuyến nghị)

Chạy app từ bất kỳ thư mục nào:

```powershell
novel app
```

Chọn thư mục `tien-hiep-demo` trong màn hình Start / Open. App tự kiểm tra project và chạy migration khi mở project cũ. Các màn hình Dashboard, Source / Chapters, Translation Jobs, Results, Context, Settings và Logs hỗ trợ:

- xem trạng thái chapter/job/conflict và health của project;
- preview rồi import source;
- dịch một chapter hoặc một range bằng worker nền, theo dõi chunk progress và resume/force;
- xem source, prompt đã render, context snapshot, output, diagnostic và metrics của từng model call;
- chỉnh cấu hình đã validate, lưu DeepSeek key trong Windows Credential Manager qua `keyring`;
- quản lý glossary/context và export bản dịch hoặc context YAML.

Các lệnh CLI bên dưới vẫn hoạt động cho automation hoặc môi trường không có UI.

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

Không để các tệp `.txt` có tên khác trong thư mục nhập; lệnh nhập sẽ báo lỗi để tránh gán sai số chương.

### 4. Nhập chương

```powershell
novel import .\input
```

Nội dung được chuẩn hóa và sao chép vào `source/chapter_0001.txt`, `source/chapter_0002.txt`… Đồng thời hệ thống ghi nhận số chương trong `data/novel.db`.

### 5. Dịch

Dịch một chương:

```powershell
novel translate 1
```

Dịch tuần tự một khoảng chương (nên dùng khi dịch từ đầu truyện, vì ngữ cảnh chương trước sẽ sẵn sàng cho chương sau):

```powershell
novel translate-range 1 20
```

Sau khi thành công, chương 1 nằm tại `translated/chapter_0001.txt`. CLI in tiến trình từng phần, tổng token và thời gian xử lý.

Nếu tiến trình bị gián đoạn hoặc một phần bị lỗi, chạy lại với `--resume` để dùng lại công việc chưa hoàn tất:

```powershell
novel translate 1 --resume
```

Một chương đã hoàn tất không được dịch lại mặc định. Chỉ khi bạn thực sự muốn tạo một lượt dịch mới, dùng:

```powershell
novel translate 1 --force
```

Không sửa trực tiếp tệp trong `source/` sau khi đã dịch. Nếu nguồn thay đổi, nhập lại bằng `novel import` trước; hệ thống kiểm tra mã băm để không vô tình nối tiếp bản dịch từ nội dung cũ.

### 6. Ghép toàn bộ bản dịch

```powershell
novel export
```

Lệnh ghép tất cả chương đã dịch theo số chương và ghi ra `exports/novel.txt`.

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

Đặt API key trong môi trường, không ghi vào `novel.yaml` và không commit key:

```powershell
$env:NOVEL_TRANSLATOR_DEEPSEEK_API_KEY = "your-api-key"
novel translate 1
```

Biến môi trường này chỉ tồn tại trong cửa sổ PowerShell hiện tại. Adapter DeepSeek dùng endpoint Chat Completions và yêu cầu đầu ra JSON có cấu trúc.

## Quản lý ngữ cảnh dịch

Trong quá trình dịch, mô hình có thể đề xuất tên riêng và thuật ngữ. Các mục được xác nhận sẽ được dùng cho các phần dịch sau; khi cách dịch mới mâu thuẫn với mục đã xác nhận, hệ thống tạo conflict thay vì tự ghi đè.

Xem ngữ cảnh:

```powershell
novel context list
novel context list --type character --status confirmed
```

`--type` nhận `character`, `location`, `organization` hoặc `term`; `--status` thường là `candidate`, `confirmed` hoặc `rejected`.

Xuất ngữ cảnh hiện có:

```powershell
novel context export
```

Tệp được ghi tại `exports/context.yaml`, có thể chỉnh sửa và nhập lại. Chỉ bốn nhóm sau được nhập thủ công:

```yaml
characters:
  - source: 张三
    translation: Trương Tam
    description: Nhân vật chính
locations:
  - source: 青云城
    translation: Thành Thanh Vân
    description: null
organizations: []
terms:
  - source: 灵石
    translation: linh thạch
    description: Đơn vị tiền tệ tu tiên
```

Nhập danh sách này vào dự án:

```powershell
novel context import .\glossary.yaml
```

Các mục nhập tay được đánh dấu là `confirmed`. Nếu nguồn đã tồn tại, lệnh nhập không ghi đè mục đó.

Kiểm tra và xử lý mâu thuẫn:

```powershell
novel context conflicts
novel context resolve 3
```

`resolve` hỏi lựa chọn: giữ bản hiện có, chấp nhận đề xuất, nhập bản dịch tùy chỉnh hoặc hủy.

## Xử lý sự cố thường gặp

- **“Current directory is not a novel project”**: chạy `cd <tên-dự-án>` trước mọi lệnh trừ `novel init`.
- **“Import directory does not exist”**: kiểm tra lại đường dẫn truyền cho `novel import`.
- **Không parse được số chương**: đổi tên tệp thành `chapter_1.txt`, `chapter_002.txt`… và dùng mã hóa UTF-8.
- **“Chapter … was not imported”**: chạy `novel import` trước khi dịch chương đó.
- **“Chapter already translated”**: dùng `--resume` cho job dở dang hoặc `--force` để tạo lượt dịch mới.
- **Không kết nối được Ollama**: khởi động Ollama, kiểm tra model đã được tải và URL `model.base_url` (hoặc `NOVEL_TRANSLATOR_OLLAMA_URL`).
- **DeepSeek báo thiếu khóa**: đặt `NOVEL_TRANSLATOR_DEEPSEEK_API_KEY` trong cùng cửa sổ terminal đang chạy `novel`.

Nhật ký dự án được lưu trong `logs/`.

## Phát triển và kiểm tra

Chạy từ thư mục repository:

```powershell
ruff check .
mypy src\novel_translator --exclude migrations
pytest -q
```
