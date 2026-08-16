# Plan: Global Provider và hỗ trợ Gemini

## 1. Mục tiêu

- Đưa cấu hình model/provider ra khỏi phạm vi từng project.
- Lưu cấu hình provider một lần ở cấp ứng dụng và tái sử dụng cho mọi project.
- Bổ sung Gemini như một provider chính thức bên cạnh Ollama và DeepSeek.
- Không lưu API key trong `novel.yaml`, database, log hoặc diagnostics.
- Giữ khả năng đọc và migration từ cấu hình project cũ.
- Giữ snapshot provider/model trong từng translation job để audit và resume ổn định.

## 2. Hiện trạng cần thay đổi

- `ModelSettings` hiện nằm trong `ProjectSettings`.
- `model` hiện được đọc/ghi từ `novel.yaml` của từng project.
- `ConfigService` đang quản lý model cùng các thiết lập project.
- API key keyring hiện dùng `project_name` làm định danh.
- `TranslationService` tạo provider dựa trên model config của project.
- Provider factory hiện chỉ cần mở rộng cho từng provider mới, nhưng chưa có lớp resolver cấp ứng dụng.

Các khu vực liên quan:

- `src/novel_translator/config.py`
- `src/novel_translator/application/services/config_service.py`
- `src/novel_translator/application/session.py`
- `src/novel_translator/application/facade.py`
- `src/novel_translator/application/services/translation_service.py`
- `src/novel_translator/infrastructure/model/factory.py`
- `src/novel_translator/infrastructure/model/ollama_provider.py`
- `src/novel_translator/infrastructure/model/deepseek_provider.py`
- `src/novel_translator/web/routes/settings.py`
- `web-client/src/api.ts`

## 3. Kiến trúc đề xuất

### 3.1. Global provider profiles

Tạo cấu hình cấp ứng dụng, không phụ thuộc project:

```yaml
config_version: 2
active_profile: gemini-default

profiles:
  ollama-local:
    provider: ollama
    base_url: http://localhost:11434
    model: qwen3:14b
    request_timeout_seconds: 300
    max_retries: 2

  deepseek-default:
    provider: deepseek
    base_url: https://api.deepseek.com
    model: deepseek-chat

  gemini-default:
    provider: gemini
    base_url: https://generativelanguage.googleapis.com
    model: gemini-2.5-flash
```

Đường dẫn đề xuất:

- Windows: `%APPDATA%/NovelTranslator/settings.yaml`
- Linux: `~/.config/NovelTranslator/settings.yaml`
- macOS: `~/Library/Application Support/NovelTranslator/settings.yaml`

Dùng `platformdirs` để lấy đường dẫn theo hệ điều hành.

### 3.2. Schema cấu hình

Tách cấu hình provider khỏi `ProjectSettings`:

```python
class ProviderType(str, Enum):
    OLLAMA = "ollama"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"


class CommonModelOptions(BaseModel):
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_output_tokens: int | None = None


class ProviderProfile(BaseModel):
    provider: ProviderType
    base_url: str | None = None
    model: str
    request_timeout_seconds: int = 300
    max_retries: int = 2
    options: CommonModelOptions = Field(default_factory=CommonModelOptions)
    provider_options: dict[str, Any] = Field(default_factory=dict)
    credential_ref: str | None = None


class GlobalProviderSettings(BaseModel):
    config_version: int = 2
    active_profile: str
    profiles: dict[str, ProviderProfile] = Field(default_factory=dict)
```

Các option riêng provider, chẳng hạn `num_ctx` và `think` của Ollama, đặt trong `provider_options` thay vì tiếp tục mở rộng một model dùng chung cho mọi provider.

### 3.3. Global settings service và resolver

Tạo các thành phần:

- `GlobalSettingsStore`: đọc/ghi file cấu hình user-level.
- `GlobalProviderService`: validate, tạo, sửa, xóa, chọn profile.
- `ProviderCredentialStore`: đọc/ghi secret từ keyring.
- `ProviderResolver`: resolve profile hiện tại thành `ModelProvider`.

`ProjectSession` chỉ giữ project settings và project database. Provider được lấy từ application runtime hoặc facade, không gắn vào project session.

Provider cache phải có cơ chế invalidate sau khi profile được cập nhật. Không thay provider giữa một translation operation đang chạy; cấu hình mới chỉ áp dụng cho operation tiếp theo.

## 4. Keyring và bảo mật

Thay cách lưu hiện tại:

```text
service: novel-translator
username: provider-profile:{profile_id}
```

Ví dụ:

```text
provider-profile:deepseek-default
provider-profile:gemini-default
```

YAML chỉ lưu `credential_ref`, không lưu `api_key`.

Yêu cầu:

- Không serialize secret vào settings response.
- Không ghi secret vào request log hoặc provider diagnostics.
- Hỗ trợ biến môi trường cho môi trường CI/headless:
  - `NOVEL_TRANSLATOR_DEEPSEEK_API_KEY`
  - `NOVEL_TRANSLATOR_GEMINI_API_KEY`
- Có trạng thái credential riêng cho từng profile.
- Migration keyring cũ theo `project_name` phải được thực hiện một lần.

## 5. Bổ sung Gemini provider

Tạo file:

```text
src/novel_translator/infrastructure/model/gemini_provider.py
```

### 5.1. Request mapping

Gemini native API cần map:

- system prompt vào `systemInstruction`.
- user prompt vào `contents`.
- `temperature`, `topP`, `topK`, `maxOutputTokens` vào `generationConfig`.
- bật JSON structured output.
- truyền schema tương ứng với `TranslationResponse`.

Response cần đọc từ các phần text trong:

```text
candidates[0].content.parts[*].text
```

Sau đó validate bằng `TranslationResponse.model_validate_json(...)`.

### 5.2. Endpoint và credential

Mặc định dùng endpoint Gemini `generateContent` và header `x-goog-api-key`. `base_url` vẫn cho phép override để test hoặc dùng endpoint tương thích.

Không nên tái sử dụng nguyên payload DeepSeek vì Gemini có request/response shape và usage metadata khác nhau.

### 5.3. Metrics và diagnostics

Map usage metadata của Gemini về `ProviderMetrics`:

- prompt token count → `prompt_tokens`.
- candidate/output token count → `output_tokens`.
- elapsed time → `duration_ms`.

Chuẩn hóa lỗi về các exception hiện có:

- timeout → `ModelTimeoutError`.
- connection error → `ModelConnectionError`.
- HTTP error → `ModelProviderError`.
- JSON/schema không hợp lệ → `ModelInvalidResponseError`.

Tái sử dụng logic sanitize diagnostic và retry hiện có, nhưng kiểm tra lại các mã lỗi retry được của Gemini.

## 6. Provider factory và translation flow

Mở rộng factory để hỗ trợ:

```python
if settings.provider == ProviderType.OLLAMA:
    return OllamaProvider(settings)
if settings.provider == ProviderType.DEEPSEEK:
    return DeepSeekProvider(settings)
if settings.provider == ProviderType.GEMINI:
    return GeminiProvider(settings)
```

Tốt hơn nữa, dùng registry thay vì chuỗi `if/elif`:

```python
PROVIDER_REGISTRY = {
    ProviderType.OLLAMA: OllamaProvider,
    ProviderType.DEEPSEEK: DeepSeekProvider,
    ProviderType.GEMINI: GeminiProvider,
}
```

`TranslationService` nhận provider đã được resolve từ global profile. Provider adapter vẫn không được phép tự ghi database.

## 7. Snapshot trong job và resume

Khi tạo `TranslationJob`, lưu thêm hoặc bảo đảm có:

- `provider`.
- `model_name`.
- `profile_id`.
- `config_hash` hoặc `profile_version`.

Mục đích:

- Job cũ vẫn audit được dù global provider đã đổi.
- Resume có thể phát hiện provider hiện tại khác provider lúc job bắt đầu.
- Không để việc đổi global setting làm thay đổi ngầm job đang chạy.

Nếu resume bằng provider khác, UI nên hiển thị cảnh báo và yêu cầu xác nhận hoặc chỉ cho phép khi có `force`.

## 8. Migration từ `novel.yaml`

### 8.1. Migration lần đầu

Khi mở project cũ:

1. Đọc `model` từ `novel.yaml`.
2. Nếu chưa có global provider profile tương đương, tạo profile mới.
3. Copy credential cũ từ keyring theo `project_name` sang profile mới.
4. Chọn profile vừa import làm active profile nếu chưa có global config.
5. Ghi version migration vào global config.

### 8.2. Compatibility period

Trong giai đoạn chuyển tiếp:

- Ưu tiên global settings.
- Nếu global settings chưa tồn tại, fallback về `novel.yaml`.
- Không ghi model mới vào `novel.yaml`.
- Cho phép người dùng xem hoặc xóa cấu hình model legacy.

Sau khi migration ổn định, có thể loại bỏ fallback ở một phiên bản lớn hơn.

## 9. API và UI

### 9.1. API

Tách phần provider khỏi `/settings` project:

```text
GET    /api/v1/providers
POST   /api/v1/providers
PATCH  /api/v1/providers/{profile_id}
DELETE /api/v1/providers/{profile_id}
POST   /api/v1/providers/{profile_id}/activate
PUT    /api/v1/providers/{profile_id}/credential
GET    /api/v1/providers/{profile_id}/credential/status
POST   /api/v1/providers/{profile_id}/test
```

Các endpoint global không nên bắt buộc project đang mở. Người dùng cần cấu hình provider ngay tại project picker hoặc màn hình application settings.

Endpoint test connection nên chạy qua operation queue nếu có request mạng hoặc timeout dài.

### 9.2. Web và desktop UI

Màn hình Provider Settings nên có:

- danh sách profile.
- provider type.
- model.
- base URL.
- các generation options.
- trạng thái credential.
- nút Test connection.
- nút Set active.
- nút Duplicate profile.

Không hiển thị API key hiện tại; chỉ hiển thị `Configured` hoặc `Not configured`.

Web và desktop phải gọi cùng application service, không tự đọc file global hoặc keyring trực tiếp.

## 10. Test cần bổ sung

### Unit tests

- validate `ProviderProfile` và `GlobalProviderSettings`.
- đọc/ghi global config.
- chọn active profile.
- cache và invalidate provider resolver.
- registry resolve đúng Ollama, DeepSeek và Gemini.
- không serialize credential.
- migration từ `novel.yaml`.

### Gemini provider tests

- request mapping đúng system/user prompt.
- gửi JSON schema.
- parse structured output hợp lệ.
- parse nhiều `parts` trong response.
- response thiếu candidate.
- response thiếu text.
- JSON invalid.
- timeout và connection error.
- retry với HTTP 429/5xx.
- metrics mapping.
- sanitized diagnostics không chứa API key.

### Integration tests

- Hai project dùng chung một global provider.
- Lưu provider mà không thay đổi `novel.yaml` project.
- Đổi active profile rồi chạy operation mới.
- Job cũ vẫn giữ provider/model cũ.
- Không đổi provider giữa các chunk của cùng operation.
- API provider hoạt động khi chưa mở project.

### Frontend tests

- CRUD provider profile.
- activate profile.
- nhập credential và kiểm tra status.
- test connection.
- không render secret trong UI.

## 11. Thứ tự triển khai

### Phase 1: Domain/config

- Tạo `ProviderType`, `ProviderProfile`, `GlobalProviderSettings`.
- Tạo global settings store.
- Tạo keyring credential store.
- Thêm test schema và persistence.

### Phase 2: Resolver và compatibility

- Tạo `ProviderResolver`.
- Cho phép global config override project config.
- Thêm legacy fallback.
- Thêm migration keyring và `config_version`.

### Phase 3: Gemini

- Tạo `GeminiProvider`.
- Đăng ký trong factory/registry.
- Bổ sung retry, metrics, diagnostics.
- Viết provider tests với mocked HTTP.

### Phase 4: Application flow

- Sửa `ApplicationFacade`, `ProjectSession` và `TranslationService`.
- Persist profile snapshot/config hash trong job.
- Đảm bảo cấu hình mới không ảnh hưởng operation đang chạy.

### Phase 5: API/UI

- Thêm global provider routes và schemas.
- Cập nhật web API client.
- Cập nhật desktop UI và web UI.
- Đồng bộ production bundle vào `src/novel_translator/web/static/`.

### Phase 6: Cleanup

- Dừng ghi `model` mới vào `novel.yaml`.
- Giữ fallback legacy trong thời gian cần thiết.
- Cập nhật tài liệu và default config.
- Chạy đầy đủ quality gate:

```text
ruff check .
mypy src/novel_translator --exclude migrations
pytest -q
cd web-client; npm run lint; npm test; npm run build
```

## 12. Tiêu chí hoàn thành

- Người dùng lưu provider một lần và sử dụng được ở mọi project.
- Provider settings không còn phụ thuộc `project_name`.
- API key chỉ nằm trong keyring hoặc environment variable.
- Ollama và DeepSeek vẫn tương thích.
- Gemini dịch được bằng structured output hợp lệ.
- Job/resume/audit giữ đúng thông tin provider tại thời điểm chạy.
- Project cũ tự migration hoặc fallback mà không cần sửa thủ công.
- Web UI và desktop UI dùng chung logic cấu hình.
