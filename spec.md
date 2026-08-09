# Novel Translator — SPEC.md

## 1. Tổng quan

**Tên tạm thời:** `novel-translator`

**Mục tiêu:** xây dựng một công cụ dịch truyện chữ **Trung Quốc → Tiếng Việt** theo hướng local-first, CLI-first, có khả năng quản lý context dài hạn của cả bộ truyện, đảm bảo tính nhất quán tên riêng, thuật ngữ, quan hệ nhân vật và cách xưng hô giữa hàng trăm hoặc hàng nghìn chương.

Tool **không tự chứa model inference**. Model là một dependency bên ngoài, được gọi thông qua `ModelProvider`.

Phiên bản đầu tiên sử dụng:

- Python 3.12
- Ollama làm model provider mặc định
- SQLite làm persistence
- CLI làm giao diện chính
- Pydantic cho request/response schema
- SQLAlchemy 2.x cho persistence
- Alembic cho database migration
- Jinja2 cho prompt template
- httpx cho HTTP client
- Typer cho CLI
- pytest cho testing

Nguyên tắc kiến trúc cốt lõi:

> **Model stateless — Tool stateful.**

Model chỉ nhận prompt đã được chuẩn hóa, dịch đoạn văn hiện tại và đề xuất context mới. Tool chịu trách nhiệm toàn bộ việc đọc context, chọn context liên quan, merge, deduplicate, conflict handling, persistence, resume và export.

---

# 2. Phạm vi V0.1

## 2.1. Hỗ trợ

V0.1 chỉ hỗ trợ:

- Source language: Chinese (`zh`)
- Target language: Vietnamese (`vi`)
- Input: plain text `.txt`
- Output: plain text `.txt`
- One novel per project
- Ollama local API
- Sequential chapter translation
- Sequential chunk translation
- Structured model output
- Context extraction trong cùng một request dịch
- Context Store bằng SQLite
- Exact-match context retrieval
- Relationship expansion depth = 1
- Previous chunk tail
- Resume khi job bị lỗi
- Conflict detection
- Context provenance
- Prompt versioning
- Translation job metrics

## 2.2. Chưa làm trong V0.1

Không triển khai:

- GUI
- Web UI
- FastAPI server
- Vector database
- Embedding
- Semantic RAG
- EPUB
- PDF
- OCR
- Multi-user
- Cloud deployment
- Multi-language
- Translation memory kiểu CAT tool đầy đủ
- Distributed workers
- Celery / Redis
- Automatic model benchmarking
- Model fallback tự động
- Multi-model translation pipeline
- Automatic rewriting bằng model thứ hai

---

# 3. Mục tiêu chất lượng

Tool phải ưu tiên:

1. Tính nhất quán tên riêng.
2. Tính nhất quán thuật ngữ.
3. Tính nhất quán cách xưng hô.
4. Không tự ý đổi mapping đã được Context Store xác nhận.
5. Không để context hallucination mới ghi đè context cũ.
6. Không cần gửi toàn bộ context của truyện vào mỗi request.
7. Có khả năng debug lại bất kỳ chunk nào.
8. Có khả năng resume an toàn.
9. Có khả năng thay Ollama bằng provider khác mà không thay business logic.
10. Không bắt model quản lý state.

---

# 4. Kiến trúc tổng thể

```text
Raw Chapter
    │
    ▼
Text Preprocessor
    │
    ▼
Chunk Builder
    │
    ▼
Context Detector
    │
    ▼
Context Retriever
    │
    ▼
Prompt Builder
    │
    ▼
ModelProvider
    │
    ▼
Ollama
    │
    ▼
Structured JSON
    │
    ▼
Response Validator
    │
    ▼
Context Update Processor
    │
    ├── Normalize
    ├── Deduplicate
    ├── Merge
    ├── Conflict Detection
    └── Provenance
    │
    ▼
SQLite
    │
    ▼
Translated Chapter
```

---

# 5. Kiến trúc module

```text
src/
└── novel_translator/
    ├── cli/
    │   ├── app.py
    │   ├── project.py
    │   ├── import_cmd.py
    │   ├── translate.py
    │   ├── context.py
    │   ├── conflicts.py
    │   └── export.py
    │
    ├── application/
    │   ├── services/
    │   │   ├── project_service.py
    │   │   ├── import_service.py
    │   │   ├── translation_service.py
    │   │   ├── chapter_translation_service.py
    │   │   ├── chunk_translation_service.py
    │   │   ├── context_service.py
    │   │   └── export_service.py
    │   │
    │   └── dto/
    │       ├── translation_job.py
    │       ├── chapter_result.py
    │       └── chunk_result.py
    │
    ├── domain/
    │   ├── model/
    │   │   ├── novel.py
    │   │   ├── chapter.py
    │   │   ├── entity.py
    │   │   ├── relationship.py
    │   │   ├── addressing_rule.py
    │   │   ├── terminology.py
    │   │   ├── context_fact.py
    │   │   ├── translation_job.py
    │   │   └── translation_chunk.py
    │   │
    │   ├── context/
    │   │   ├── detector.py
    │   │   ├── retriever.py
    │   │   ├── merger.py
    │   │   ├── normalizer.py
    │   │   ├── conflict_detector.py
    │   │   └── policies.py
    │   │
    │   ├── translation/
    │   │   ├── chunker.py
    │   │   ├── prompt_builder.py
    │   │   ├── response_validator.py
    │   │   └── continuity.py
    │   │
    │   └── repositories/
    │       ├── novel_repository.py
    │       ├── chapter_repository.py
    │       ├── context_repository.py
    │       ├── job_repository.py
    │       └── conflict_repository.py
    │
    ├── infrastructure/
    │   ├── model/
    │   │   ├── provider.py
    │   │   ├── ollama_provider.py
    │   │   └── exceptions.py
    │   │
    │   ├── persistence/
    │   │   ├── database.py
    │   │   ├── orm/
    │   │   ├── repositories/
    │   │   └── migrations/
    │   │
    │   ├── filesystem/
    │   │   ├── project_fs.py
    │   │   └── chapter_fs.py
    │   │
    │   └── config/
    │       └── settings.py
    │
    ├── schemas/
    │   ├── translation_request.py
    │   ├── translation_response.py
    │   ├── context_update.py
    │   └── context_snapshot.py
    │
    ├── prompts/
    │   └── translation_v1.jinja2
    │
    ├── config.py
    ├── constants.py
    └── main.py
```

Kiến trúc có thể xem là một biến thể nhẹ của Clean Architecture.

Không yêu cầu tuân thủ tuyệt đối các rule học thuật. Mục tiêu chính:

```text
domain
↑
application
↑
infrastructure
```

Domain không được phụ thuộc trực tiếp vào Ollama, SQLAlchemy, CLI hoặc filesystem.

---

# 6. Project layout runtime

Mỗi truyện được quản lý dưới một project riêng.

```text
projects/
└── my_novel/
    ├── novel.yaml
    ├── data/
    │   └── novel.db
    │
    ├── source/
    │   ├── chapter_0001.txt
    │   ├── chapter_0002.txt
    │   └── ...
    │
    ├── translated/
    │   ├── chapter_0001.txt
    │   ├── chapter_0002.txt
    │   └── ...
    │
    ├── exports/
    │
    └── logs/
```

---

# 7. Cấu hình project

`novel.yaml`

```yaml
project:
  name: my_novel

novel:
  title: ""
  source_language: zh
  target_language: vi

genre:
  - xianxia

model:
  provider: ollama
  base_url: http://localhost:11434
  name: qwen3:14b

  request_timeout_seconds: 300

  options:
    temperature: 0.2
    top_p: 0.9
    num_ctx: 16384
    think: false

translation:
  prompt_version: translation-v1

  chunk:
    target_chars: 6000
    max_chars: 10000
    min_chars: 2000

  continuity:
    include_previous_tail: true
    previous_tail_paragraphs: 3

context:
  relation_depth: 1

  max_characters_per_request: 30
  max_terms_per_request: 50
  max_relationships_per_request: 30
  max_facts_per_request: 20

  auto_confirm:
    character: true
    term: true
    location: true
    organization: true
    addressing: false
    relationship: false
    world_fact: false

  minimum_confidence:
    auto_confirm: 0.90
```

---

# 8. ModelProvider abstraction

Application layer không được gọi Ollama trực tiếp.

Interface:

```python
from typing import Protocol

class ModelProvider(Protocol):

    def translate(
        self,
        request: TranslationRequest,
    ) -> TranslationResponse:
        ...
```

Provider implementations tương lai:

```text
ModelProvider
├── OllamaProvider          V0.1
├── LlamaCppProvider        future
├── OpenAIProvider          future
└── CustomHttpProvider      future
```

---

# 9. Ollama Provider

V0.1 gọi Ollama qua HTTP bằng `httpx`.

Không dùng Ollama Python SDK để tránh binding quá chặt vào dependency.

Base URL mặc định:

```text
http://localhost:11434
```

Endpoint:

```text
POST /api/chat
```

Request concept:

```json
{
  "model": "qwen3:14b",
  "messages": [
    {
      "role": "system",
      "content": "SYSTEM PROMPT"
    },
    {
      "role": "user",
      "content": "TRANSLATION PROMPT"
    }
  ],
  "format": {
    "...": "JSON Schema generated from Pydantic"
  },
  "stream": false,
  "think": false,
  "options": {
    "temperature": 0.2,
    "top_p": 0.9,
    "num_ctx": 16384
  }
}
```

Provider phải:

1. Build HTTP request.
2. Gửi request.
3. Check HTTP status.
4. Parse Ollama response.
5. Parse `message.content` thành `TranslationResponse`.
6. Collect metrics.
7. Raise typed exception nếu lỗi.

Các exception:

```python
class ModelProviderError(Exception):
    pass

class ModelTimeoutError(ModelProviderError):
    pass

class ModelConnectionError(ModelProviderError):
    pass

class ModelInvalidResponseError(ModelProviderError):
    pass
```

---

# 10. Structured Output

Không parse output dạng:

```text
### TRANSLATION
...

### CONTEXT_UPDATE
...
```

V0.1 bắt buộc sử dụng JSON structured output.

Pydantic schema là source of truth.

---

# 11. TranslationResponse

```python
from pydantic import BaseModel, Field

class TranslationResponse(BaseModel):
    translation: str = Field(min_length=1)
    context_updates: list["ContextUpdate"] = []
```

---

# 12. ContextUpdate

```python
from enum import StrEnum

class ContextType(StrEnum):
    CHARACTER = "character"
    TERM = "term"
    LOCATION = "location"
    ORGANIZATION = "organization"
    RELATIONSHIP = "relationship"
    ADDRESSING = "addressing"
    WORLD_FACT = "world_fact"
```

Base schema:

```python
class ContextUpdate(BaseModel):
    type: ContextType

    source: str | None = None
    translation: str | None = None

    description: str | None = None

    aliases: list[str] = []

    related_entities: list[str] = []

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )
```

V0.1 có thể dùng schema chung trước.

V0.2 có thể chuyển sang discriminated union:

```text
CharacterUpdate
TermUpdate
RelationshipUpdate
AddressingUpdate
...
```

---

# 13. Context categories

Context được chia thành 7 nhóm.

## 13.1. CHARACTER

Ví dụ:

```text
叶辰 = Diệp Thần
苏雨柔 = Tô Vũ Nhu
```

Thông tin tùy chọn:

- role
- gender
- description
- aliases
- titles

Không được bắt model suy đoán gender nếu source không rõ.

---

## 13.2. TERM

Các thuật ngữ cần giữ translation nhất quán.

Ví dụ:

```text
筑基 = Trúc Cơ
金丹 = Kim Đan
元婴 = Nguyên Anh
```

Term mapping đã confirmed phải được xem là authoritative.

---

## 13.3. LOCATION

Ví dụ:

```text
青云山 = Thanh Vân Sơn
```

---

## 13.4. ORGANIZATION

Ví dụ:

```text
天玄宗 = Thiên Huyền Tông
```

---

## 13.5. RELATIONSHIP

Ví dụ:

```text
苏雨柔 sister_of 苏清雪
林凡 disciple_of 苏清雪
```

Relationship không được ghi thành prose blob nếu có thể biểu diễn structured.

---

## 13.6. ADDRESSING

Dùng riêng cho xưng hô.

Ví dụ:

```text
speaker: 林凡
listener: 苏清雪

speaker_pronoun: đệ tử
listener_pronoun: sư tôn
```

Có thể chứa mapping title:

```text
师尊 -> sư tôn
苏师妹 -> Tô sư muội
```

---

## 13.7. WORLD_FACT

Thông tin thế giới có ích lâu dài.

Ví dụ:

```text
天玄宗位于东域
Thiên Huyền Tông nằm tại Đông Vực.
```

Không lưu các hành động tạm thời hoặc sự kiện không ảnh hưởng tới dịch sau này.

---

# 14. Context states

Mỗi context record phải có status:

```text
CANDIDATE
CONFIRMED
REJECTED
```

Rule:

- `CONFIRMED`: được phép dùng khi build prompt.
- `CANDIDATE`: chưa đưa vào prompt mặc định.
- `REJECTED`: không sử dụng.

Auto confirm chỉ áp dụng khi:

1. Không conflict.
2. Confidence đạt threshold.
3. Context type cho phép auto confirm.
4. Source xuất hiện trực tiếp trong current source chunk khi type yêu cầu.

---

# 15. Context authority

Context Store là source of truth mạnh hơn model.

Nếu database có:

```text
叶辰 = Diệp Thần
```

model không được phép đổi thành:

```text
叶辰 = Diệp Trần
```

Prompt phải nói rõ:

```text
Existing confirmed mappings are authoritative.

Never replace, reinterpret, or improve an existing translation mapping.
```

Nếu model trả mapping khác:

```text
existing: Diệp Thần
candidate: Diệp Trần
```

Tool:

- không overwrite
- tạo conflict record
- giữ mapping cũ

---

# 16. Context provenance

Mỗi context item phải biết nó xuất phát từ đâu.

Tối thiểu:

```text
novel_id
chapter_id
chunk_id
model_name
prompt_version
created_at
```

Có thể thêm:

```text
source_excerpt
confidence
```

Mục tiêu:

- debug hallucination
- audit
- review
- rollback sau này

---

# 17. Context normalization

ContextUpdate phải đi qua normalizer trước khi merge.

Normalizer xử lý:

- trim whitespace
- Unicode normalization
- Chinese fullwidth punctuation
- collapse repeated spaces
- loại bỏ newline không cần thiết
- normalize empty string thành `None`
- normalize aliases
- remove exact duplicate aliases
- source không được trùng alias
- translation không được trùng alias nếu không hợp lý

Không tự sửa Hán tự sang giản thể/phồn thể ở V0.1 ngoài Unicode normalization.

---

# 18. Context merge algorithm

Pseudo flow:

```text
ContextUpdate
    │
    ▼
Normalize
    │
    ▼
Validate
    │
    ▼
Find exact existing record
    │
    ├── Exact same
    │      └── Ignore duplicate
    │
    ▼
Find same source key
    │
    ├── Same translation
    │      └── Merge missing metadata
    │
    ▼
Translation conflict?
    │
    ├── Yes
    │      ├── Do not overwrite
    │      └── Create ContextConflict
    │
    ▼
Apply AutoConfirmPolicy
    │
    ▼
Insert
```

---

# 19. Merge rule examples

## Duplicate

DB:

```text
叶辰 = Diệp Thần
```

Model:

```text
叶辰 = Diệp Thần
```

Result:

```text
ignore
```

---

## Metadata enrichment

DB:

```text
叶辰 = Diệp Thần
description = null
```

Model:

```text
叶辰 = Diệp Thần
description = nội môn đệ tử
```

Result:

```text
merge description
```

---

## Translation conflict

DB:

```text
叶辰 = Diệp Thần
```

Model:

```text
叶辰 = Diệp Trần
```

Result:

```text
keep Diệp Thần
create conflict
```

---

# 20. Conflict entity

Bảng:

```text
context_conflict
```

Fields:

```text
id
novel_id

context_type
source_key

existing_value
candidate_value

chapter_id
chunk_id

status

created_at
resolved_at
```

Status:

```text
OPEN
ACCEPT_EXISTING
ACCEPT_CANDIDATE
CUSTOM
```

CLI V0.1 chỉ cần:

```bash
novel context conflicts
```

và:

```bash
novel context resolve <id>
```

---

# 21. Exact-match Context Retriever

V0.1 chưa dùng embeddings.

Algorithm:

1. Load all CONFIRMED entities/terms/locations/organizations.
2. Check source key có xuất hiện trong current Chinese chunk hay không.
3. Collect matched items.
4. Expand relationship depth 1.
5. Collect addressing rules giữa matched characters.
6. Limit result theo config.
7. Sort deterministic.
8. Build ContextSnapshot.

Pseudo:

```python
for item in known_context:
    if item.source_key in source_text:
        matched.add(item)
```

Với Chinese novel, exact string matching đủ hữu ích cho V0.1.

---

# 22. Relationship expansion

Config mặc định:

```yaml
relation_depth: 1
```

Ví dụ text có:

```text
苏雨柔
```

Retriever tìm:

```text
苏雨柔 = Tô Vũ Nhu
```

Sau đó expand:

```text
苏雨柔 sister_of 苏清雪
```

và lấy:

```text
苏清雪 = Tô Thanh Tuyết
```

Không recursively expand tiếp qua:

```text
苏清雪 master_of 林凡
```

trừ khi `林凡` xuất hiện trực tiếp trong chunk.

---

# 23. Context Snapshot

Trước mỗi request, ContextRetriever tạo `ContextSnapshot`.

Ví dụ:

```python
class ContextSnapshot(BaseModel):
    characters: list[CharacterContext]
    terms: list[TermContext]
    locations: list[LocationContext]
    organizations: list[OrganizationContext]
    relationships: list[RelationshipContext]
    addressing_rules: list[AddressingContext]
    world_facts: list[WorldFactContext]
```

Snapshot phải được persist cùng `translation_chunk`.

Lý do:

Nếu 3 tháng sau Context DB thay đổi, vẫn phải biết model đã nhìn thấy context nào lúc dịch chunk đó.

---

# 24. Ba lớp context trong prompt

Prompt context gồm:

## GLOBAL CONTEXT

Luôn có:

- Chinese → Vietnamese
- genre
- global translation style
- global rules

## STORY CONTEXT

Dynamic:

- characters
- terms
- locations
- organizations
- relationships
- addressing rules
- world facts

## LOCAL CONTEXT

Dynamic:

- previous translation tail
- current chapter metadata

---

# 25. Translation style mặc định

Prompt mặc định hướng tới truyện mạng Trung Quốc.

Rule baseline:

- Dịch tự nhiên, trôi chảy bằng tiếng Việt.
- Không dịch word-by-word nếu khiến câu văn cứng.
- Không tự thêm tình tiết.
- Không tự bỏ chi tiết.
- Không giải thích ngoài bản dịch.
- Giữ format đoạn văn.
- Giữ format hội thoại.
- Ưu tiên Hán Việt hợp lý cho tiên hiệp, huyền huyễn, võ hiệp.
- Không hiện đại hóa cách nói nếu ngữ cảnh mang phong cách cổ trang.
- Existing mappings phải được dùng chính xác.
- Cách xưng hô phải ưu tiên Context Store.
- Nếu không đủ context để xác định xưng hô, dùng cách trung tính phù hợp nhất.
- Không tự invent relationship chỉ để phục vụ translation.
- Context update chỉ chứa thông tin có giá trị lâu dài.

---

# 26. Điều kiện để model tạo ContextUpdate

Model chỉ nên tạo context update nếu thông tin:

- mới
- explicit hoặc có độ chắc chắn cao
- có khả năng cần ở chương sau
- ảnh hưởng tới consistency

Nên lưu:

- nhân vật mới
- tên dịch mới
- title quan trọng
- thuật ngữ mới
- tổ chức mới
- địa danh mới
- relationship mới
- addressing rule mới
- world fact có giá trị lâu dài

Không lưu:

- thời tiết
- mô tả cảnh vật thông thường
- hành động một lần
- câu thoại bình thường
- cảm xúc tức thời
- thông tin đã có trong Context Store
- phỏng đoán
- suy luận không explicit

---

# 27. Prompt template

File:

```text
prompts/translation_v1.jinja2
```

Concept:

```jinja2
You are a professional Chinese-to-Vietnamese web novel translator.

## CORE RULES

- Translate only from Chinese to Vietnamese.
- Preserve meaning.
- Produce natural Vietnamese novel prose.
- Existing confirmed mappings are authoritative.
- Never replace or reinterpret confirmed mappings.
- Do not add explanations.
- Do not omit content.
- Preserve paragraphs and dialogue structure.

## CONTEXT UPDATE RULES

Only report NEW long-term information useful for future translation consistency.

Good context updates:
- new character
- new term
- new organization
- new location
- explicit relationship
- important addressing convention
- long-term world fact

Do not report:
- temporary events
- normal actions
- scenery
- already known facts
- guesses
- uncertain interpretations

## STORY CONTEXT

### Characters
{% for item in characters %}
- {{ item.source_name }} = {{ item.translated_name }}
  {% if item.description %}{{ item.description }}{% endif %}
{% endfor %}

### Terms
{% for item in terms %}
- {{ item.source }} = {{ item.translation }}
{% endfor %}

### Organizations
...

### Locations
...

### Relationships
...

### Addressing
...

### World Facts
...

## PREVIOUS TRANSLATION TAIL

This is context only.
DO NOT translate it again.

{{ previous_translation_tail }}

## CURRENT CHINESE TEXT

{{ source_text }}

Return only the required structured response.
```

Prompt phải nằm ngoài Python business logic.

---

# 28. Prompt versioning

Config:

```yaml
translation:
  prompt_version: translation-v1
```

Database lưu:

```text
prompt_version
```

cho mỗi translation chunk.

Không sửa file `translation_v1.jinja2` sau khi đã dùng production translation.

Nếu cải tiến:

```text
translation_v2.jinja2
translation_v3.jinja2
```

---

# 29. Text preprocessing

Input chapter phải được normalize trước khi chunk.

V0.1 xử lý:

- UTF-8
- normalize line endings về `\n`
- strip BOM
- trim trailing spaces mỗi line
- collapse hơn 3 blank lines thành tối đa 2
- không sửa Chinese punctuation
- không convert simplified/traditional
- không thay nội dung

---

# 30. Chunking

Mục tiêu:

- không cắt giữa paragraph nếu có thể
- không tạo chunk quá nhỏ
- không vượt max chars trừ trường hợp một paragraph đơn lẻ quá dài

Default:

```yaml
target_chars: 6000
max_chars: 10000
min_chars: 2000
```

Algorithm:

1. Split chapter thành paragraphs theo blank line.
2. Append paragraphs cho tới gần `target_chars`.
3. Nếu thêm paragraph tiếp theo vượt `max_chars`, finalize chunk.
4. Nếu chunk cuối < `min_chars`, merge vào chunk trước nếu không vượt limit quá nhiều.
5. Nếu một paragraph > `max_chars`, fallback split theo Chinese sentence punctuation:
   - `。`
   - `！`
   - `？`
   - `……`
6. Không split character-by-character trừ emergency fallback.

---

# 31. Previous chunk tail

Chunk N nhận local context từ chunk N-1.

Default:

```yaml
previous_tail_paragraphs: 3
```

Input:

```text
previous_translation_tail
```

chứa 3 đoạn cuối **bản dịch tiếng Việt** của chunk trước.

Prompt phải nói rõ:

```text
DO NOT translate this content again.
```

Mục tiêu:

- giữ speaker continuity
- giữ mood
- giảm lỗi pronoun
- giữ continuity giữa chunk

Chunk đầu tiên:

```text
previous_translation_tail = ""
```

---

# 32. Chapter translation flow

```text
Load chapter
    │
    ▼
Normalize source
    │
    ▼
Build chunks
    │
    ▼
Create TranslationJob
    │
    ▼
For each chunk
    │
    ├── detect known context
    ├── retrieve context
    ├── build snapshot
    ├── build prompt
    ├── call provider
    ├── validate response
    ├── normalize updates
    ├── merge updates
    ├── save translation
    ├── save snapshot
    └── commit
    │
    ▼
Assemble translated chapter
    │
    ▼
Write translated/chapter_xxxx.txt
    │
    ▼
Mark job completed
```

---

# 33. Translation chunk transaction

Mỗi chunk phải transaction-safe.

Concept:

```text
BEGIN TRANSACTION

save model response
save translated text
save context snapshot
merge context updates
save conflicts
mark chunk completed

COMMIT
```

Nếu bất kỳ bước nào lỗi:

```text
ROLLBACK
```

Không được có trạng thái:

```text
translation saved
context merge half completed
```

---

# 34. Resume

Mỗi chunk có status:

```text
PENDING
RUNNING
COMPLETED
FAILED
```

Chapter Job status:

```text
PENDING
RUNNING
COMPLETED
FAILED
PARTIAL
```

Nếu process chết ở chunk 14:

```text
1-13 = COMPLETED
14 = FAILED
15+ = PENDING
```

Command:

```bash
novel translate 53 --resume
```

bắt đầu lại từ chunk chưa completed đầu tiên.

Không dịch lại chunk completed.

---

# 35. Retry policy

V0.1 retry tối đa:

```text
2 retries
```

Áp dụng cho:

- timeout
- connection reset
- temporary HTTP errors
- invalid structured response

Không retry vô hạn.

Config:

```yaml
model:
  max_retries: 2
```

Retry phải được log.

---

# 36. Response validation

`TranslationResponse` sau khi parse Pydantic vẫn phải qua sanity validation.

Checks:

- `translation` không rỗng
- translation không bằng source
- translation length không bất thường
- số context update không vượt hard limit
- confidence nằm 0..1
- source key hợp lệ
- context update type hợp lệ

Có thể dùng heuristic:

```text
translation_length / source_length
```

Nếu ratio quá thấp hoặc quá cao thì warning hoặc fail.

V0.1 chỉ cần configurable broad threshold:

```yaml
validation:
  min_length_ratio: 0.25
  max_length_ratio: 4.0
```

Không dùng ratio làm quality score tuyệt đối.

---

# 37. Database schema

## novel

```text
id
project_name
title
source_language
target_language
created_at
updated_at
```

---

## chapter

```text
id
novel_id

chapter_number
source_path
translated_path

source_hash

status

created_at
updated_at
```

Unique:

```text
(novel_id, chapter_number)
```

---

## entity

Dùng cho:

```text
CHARACTER
LOCATION
ORGANIZATION
```

Fields:

```text
id
novel_id

entity_type

source_name
translated_name

description

status

first_seen_chapter_id
first_seen_chunk_id

created_by_model
prompt_version

created_at
updated_at
```

Unique candidate key:

```text
(novel_id, entity_type, source_name)
```

---

## entity_alias

```text
id
entity_id

alias
alias_type

created_at
```

Alias type:

```text
SOURCE_ALIAS
TITLE
NICKNAME
```

---

## terminology

```text
id
novel_id

source_term
translated_term

description

status

first_seen_chapter_id
first_seen_chunk_id

created_by_model
prompt_version

created_at
updated_at
```

Unique:

```text
(novel_id, source_term)
```

---

## relationship

```text
id
novel_id

subject_entity_id
predicate
object_entity_id

description

status

first_seen_chapter_id
first_seen_chunk_id

confidence

created_at
updated_at
```

Predicate V0.1 free string nhưng normalize lowercase snake_case.

Ví dụ:

```text
sister_of
master_of
disciple_of
father_of
mother_of
enemy_of
friend_of
member_of
```

---

## addressing_rule

```text
id
novel_id

speaker_entity_id
listener_entity_id

speaker_pronoun
listener_pronoun

source_title
translated_title

description

status

first_seen_chapter_id
first_seen_chunk_id

created_at
updated_at
```

Không bắt buộc speaker/listener cả hai nếu rule là global title.

---

## context_fact

```text
id
novel_id

subject
fact_key
fact_value

description

status

first_seen_chapter_id
first_seen_chunk_id

confidence

created_at
updated_at
```

---

## translation_job

```text
id
novel_id
chapter_id

model_provider
model_name
prompt_version

status

started_at
finished_at

total_prompt_tokens
total_output_tokens
total_duration_ms

created_at
updated_at
```

---

## translation_chunk

```text
id
translation_job_id
chapter_id

chunk_index

source_text
translated_text

previous_translation_tail

context_snapshot_json
raw_model_response_json

prompt_hash

status
error_message

prompt_tokens
output_tokens
duration_ms

created_at
updated_at
```

Unique:

```text
(translation_job_id, chunk_index)
```

---

## context_conflict

```text
id
novel_id

context_type
source_key

existing_value
candidate_value

chapter_id
chunk_id

status

created_at
resolved_at
```

---

# 38. Source hash

Khi import chapter:

```text
SHA-256(source text)
```

lưu thành `source_hash`.

Nếu source file thay đổi sau khi đã dịch:

CLI phải cảnh báo:

```text
Source chapter has changed since previous translation.
```

Không silently reuse old translation.

---

# 39. Prompt hash

Mỗi chunk lưu hash của rendered prompt:

```text
SHA-256(prompt)
```

Dùng để:

- debug
- reproducibility
- detect prompt changes
- audit

Không cần persist full prompt nếu context snapshot + template version đủ reconstruct, nhưng V0.1 có thể persist full prompt nếu muốn debug dễ.

---

# 40. CLI

Entry point:

```bash
novel
```

## Init

```bash
novel init my-novel
```

Tạo project structure.

---

## Import

```bash
novel import ./chapters
```

Import `.txt`.

Naming convention:

```text
chapter_0001.txt
chapter_0002.txt
```

Nếu filename không parse được chapter number thì báo lỗi.

---

## Translate one chapter

```bash
novel translate 1
```

---

## Resume

```bash
novel translate 1 --resume
```

---

## Force retranslate

```bash
novel translate 1 --force
```

`--force` phải tạo TranslationJob mới.

Không delete history job cũ.

---

## Translate range

V0.1 optional nhưng nên có:

```bash
novel translate-range 1 20
```

Sequential.

Không parallel translate chapters vì context chapter trước có thể ảnh hưởng chapter sau.

---

## Context list

```bash
novel context list
```

Filter:

```bash
novel context list --type character
novel context list --type term
novel context list --status confirmed
```

---

## Conflicts

```bash
novel context conflicts
```

---

## Resolve conflict

```bash
novel context resolve 17
```

Interactive CLI:

```text
Existing: Diệp Thần
Candidate: Diệp Trần

[1] Keep existing
[2] Accept candidate
[3] Custom
[4] Cancel
```

---

## Export

```bash
novel export
```

V0.1 concat các translated chapter thành:

```text
exports/novel.txt
```

---

# 41. Import rules

Input encoding:

```text
UTF-8
```

Nếu decode fail:

- không tự đoán encoding
- báo error rõ ràng

Chapter order dựa vào chapter number, không dựa vào filesystem order.

---

# 42. Context retrieval ordering

Để prompt deterministic, context phải sort.

Recommended:

Characters:

```text
direct match first
then relation-expanded
alphabetical by source_name
```

Terms:

```text
longest source term first
```

Relationships:

```text
subject source
predicate
object source
```

Addressing:

```text
speaker
listener
```

Deterministic prompt rất quan trọng cho debugging.

---

# 43. Context size limits

Không để story context tăng không kiểm soát.

Config:

```yaml
context:
  max_characters_per_request: 30
  max_terms_per_request: 50
  max_relationships_per_request: 30
  max_facts_per_request: 20
```

Priority:

1. Direct source match.
2. Addressing involving direct matched characters.
3. Relationship depth 1.
4. Related entities.
5. World facts.

Nếu vượt limit, drop priority thấp trước.

---

# 44. Alias detection

Retriever cũng phải check aliases.

Ví dụ entity:

```text
canonical:
苏清雪

aliases:
苏仙子
清雪
```

Nếu text chứa:

```text
苏仙子
```

vẫn retrieve entity:

```text
苏清雪 = Tô Thanh Tuyết
```

Không coi alias là entity riêng.

---

# 45. Addressing priority

Khi build prompt, addressing context có priority cao.

Priority:

```text
exact speaker + listener rule
>
specific source title mapping
>
character general rule
>
global style
>
model inference
```

Tool không tự thay pronoun trong translated output V0.1.

Tool chỉ cung cấp context cho model.

---

# 46. Model output không được tự ghi DB

Luồng bắt buộc:

```text
Model
↓
TranslationResponse
↓
ResponseValidator
↓
ContextNormalizer
↓
ContextMergePolicy
↓
Repository
```

Không có code path:

```text
OllamaProvider -> SQLAlchemy
```

---

# 47. Model metric collection

Nếu provider cung cấp:

- prompt tokens
- output tokens
- total duration
- eval duration

lưu vào `translation_chunk`.

Chapter aggregate:

```text
total_prompt_tokens
total_output_tokens
total_duration_ms
```

CLI sau chapter:

```text
Chapter 53 completed

Chunks: 12
Prompt tokens: 42,310
Output tokens: 18,902
Duration: 04:53
Context updates: 7
Conflicts: 1
```

---

# 48. Logging

Python stdlib `logging` đủ cho V0.1.

Console:

```text
INFO
WARNING
ERROR
```

File:

```text
logs/novel-translator.log
```

Không log toàn bộ raw source ở INFO.

Có thể log chunk index, chapter, timings, update count.

Ví dụ:

```text
INFO chapter=53 chunk=4 model=qwen3:14b duration_ms=24210 updates=2
```

---

# 49. Security

Tool local-first.

Không có auth V0.1.

Không expose HTTP server.

Không execute code từ model output.

Không deserialize pickle.

Prompt template là local trusted files.

Database queries dùng SQLAlchemy parameter binding.

---

# 50. Configuration loading

Priority:

```text
CLI flags
>
environment variables
>
novel.yaml
>
defaults
```

Environment variables example:

```text
NOVEL_TRANSLATOR_OLLAMA_URL
NOVEL_TRANSLATOR_MODEL
NOVEL_TRANSLATOR_LOG_LEVEL
```

Không cần `.env` dependency bắt buộc.

Có thể hỗ trợ `.env` optional sau.

---

# 51. Core interfaces

## ContextRetriever

```python
class ContextRetriever(Protocol):

    def retrieve(
        self,
        novel_id: int,
        source_text: str,
    ) -> ContextSnapshot:
        ...
```

V0.1:

```text
ExactMatchContextRetriever
```

---

## ContextMerger

```python
class ContextMerger(Protocol):

    def merge(
        self,
        updates: list[ContextUpdate],
        provenance: ContextProvenance,
    ) -> ContextMergeResult:
        ...
```

---

## PromptBuilder

```python
class PromptBuilder(Protocol):

    def build(
        self,
        request: PromptBuildRequest,
    ) -> RenderedPrompt:
        ...
```

---

## Chunker

```python
class ChapterChunker(Protocol):

    def split(
        self,
        source_text: str,
    ) -> list[SourceChunk]:
        ...
```

---

# 52. Application service responsibilities

## TranslationService

Orchestrates chapter translation.

Không chứa SQL details.

---

## ChunkTranslationService

Một chunk:

```text
retrieve
build prompt
call model
validate
merge
persist
```

---

## ContextService

- list
- confirm
- reject
- conflict resolve
- manual edit future

---

# 53. Repository contracts

Domain/application layer dùng interfaces.

Ví dụ:

```python
class ContextRepository(Protocol):

    def find_confirmed_entities(
        self,
        novel_id: int,
    ) -> list[Entity]:
        ...

    def find_entity_by_source(
        self,
        novel_id: int,
        source_name: str,
    ) -> Entity | None:
        ...

    def save_entity(
        self,
        entity: Entity,
    ) -> Entity:
        ...
```

SQLAlchemy implementation ở infrastructure.

---

# 54. SQLAlchemy

Sử dụng SQLAlchemy 2.x style.

Không dùng legacy Query API.

Session per application operation.

Transactions explicit.

SQLite pragmas nên bật:

```text
foreign_keys = ON
journal_mode = WAL
```

WAL không bắt buộc nhưng nên bật.

---

# 55. Alembic

Database schema phải dùng migration từ đầu.

Không dùng:

```python
Base.metadata.create_all()
```

làm production migration mechanism.

Có thể dùng create_all trong unit test SQLite in-memory.

---

# 56. Testing strategy

## Unit tests

Test:

- chunking
- normalization
- duplicate merge
- conflict detection
- auto confirm policy
- exact context matching
- alias matching
- relationship expansion
- prompt rendering
- response validation

---

## Integration tests

SQLite temp DB:

- insert context
- retrieve
- merge
- conflict
- transaction rollback
- resume state

---

## Provider tests

Mock Ollama HTTP bằng:

```text
respx
```

hoặc `httpx.MockTransport`.

Không yêu cầu Ollama thật trong CI.

---

## End-to-end local test

Optional marker:

```text
@pytest.mark.ollama
```

Test chỉ chạy khi Ollama local available.

---

# 57. Minimum test cases

Bắt buộc có ít nhất:

1. Entity exact match.
2. Alias match.
3. Term exact match.
4. Relationship depth 1.
5. Duplicate context ignored.
6. Same source + same translation metadata merge.
7. Same source + different translation -> conflict.
8. Candidate context không được retrieve.
9. Confirmed context được retrieve.
10. Failed chunk rollback.
11. Resume skip completed chunks.
12. Source hash change warning.
13. Structured output parse success.
14. Structured output invalid -> provider error.
15. Previous tail correctly passed.
16. Prompt deterministic.
17. Chapter chunks reassembled đúng thứ tự.

---

# 58. Dependency proposal

`pyproject.toml`

Runtime:

```text
python >= 3.12, < 3.13

typer
pydantic
pydantic-settings
sqlalchemy
alembic
httpx
jinja2
pyyaml
```

Dev:

```text
pytest
pytest-cov
respx
ruff
mypy
```

Optional:

```text
rich
```

Typer sử dụng Rich internally trong nhiều trường hợp, nhưng không cần build UI phức tạp.

---

# 59. Code quality

Use:

```text
ruff
mypy
pytest
```

Target:

```text
Python 3.12
```

Type hints bắt buộc cho public APIs.

Không yêu cầu 100% mypy strict ở V0.1 nhưng core domain nên typed rõ.

---

# 60. Error handling

Application errors:

```text
ProjectNotFoundError
ChapterNotFoundError
ChapterAlreadyTranslatedError
InvalidProjectConfigError
SourceChangedError
TranslationFailedError
ContextConflictError
```

CLI convert exception thành human-readable error.

Không show stacktrace mặc định.

Có option:

```bash
--debug
```

để show traceback.

---

# 61. Translation consistency strategy

Consistency được đảm bảo bằng nhiều lớp:

```text
Context Store
+
Confirmed mapping authority
+
Exact retrieval
+
Relationship expansion
+
Addressing rules
+
Previous chunk tail
+
Conflict prevention
+
Prompt versioning
+
Context provenance
```

Không dựa vào model memory.

---

# 62. Chinese-specific optimization

Vì tool chỉ dùng Trung → Việt, V0.1 có thể tối ưu trực tiếp cho Chinese novel.

## String matching

Không cần tokenizer riêng để detect entity ở V0.1.

Chinese names và terms thường match trực tiếp theo substring.

---

## Chinese sentence splitting

Fallback chunk split hỗ trợ:

```text
。
！
？
；
……
```

Không dùng dấu `,` hoặc `，` làm primary sentence boundary.

---

## Hán Việt consistency

Model prompt phải ưu tiên existing Context Store.

Tool không tự transliterate Chinese characters sang Hán Việt bằng dictionary trong V0.1.

Lý do:

- tên riêng có thể có nhiều cách đọc
- model có thể chọn mapping từ context
- user có thể manual override

Có thể thêm Sino-Vietnamese dictionary V0.2.

---

# 63. Manual context bootstrap

V0.1 nên hỗ trợ import context ban đầu bằng file JSON hoặc YAML.

Command optional:

```bash
novel context import context.yaml
```

Ví dụ:

```yaml
characters:
  - source: 林凡
    translation: Lâm Phàm
    description: Nam chính

terms:
  - source: 筑基
    translation: Trúc Cơ

organizations:
  - source: 天玄宗
    translation: Thiên Huyền Tông
```

Imported context mặc định:

```text
CONFIRMED
```

Provenance:

```text
created_by_model = null
source = manual_import
```

---

# 64. Context export

Nên hỗ trợ:

```bash
novel context export
```

Output:

```text
exports/context.yaml
```

Dùng để:

- backup
- manual edit
- migrate
- inspect
- share

---

# 65. Re-translation strategy

Nếu user chạy:

```bash
novel translate 53 --force
```

Tool:

1. Tạo TranslationJob mới.
2. Không delete job cũ.
3. Có thể sử dụng Context Store hiện tại.
4. Ghi output chapter mới sau khi job hoàn tất.
5. Không overwrite translated file giữa chừng.

Safe write:

```text
chapter_0053.txt.tmp
↓
complete
↓
atomic rename
```

---

# 66. Chapter output assembly

Translated chunks join bằng:

```text
\n\n
```

nhưng phải cố giữ paragraph structure từ chunk output.

Không thêm header nếu source không có.

Optional config V0.2 mới thêm chapter title formatting.

---

# 67. Model switching

Nếu config đổi:

```yaml
model:
  name: translategemma:12b
```

application layer không đổi.

Tuy nhiên provider capability phải kiểm tra:

```text
supports_chat
supports_structured_output
supports_thinking_flag
```

V0.1 có thể assume Ollama model support đủ tốt với JSON schema.

Nếu model không tuân thủ schema:

```text
provider retry
```

Nếu vẫn fail:

```text
chunk FAILED
```

---

# 68. Capability abstraction future

Future:

```python
class ModelCapabilities(BaseModel):
    structured_output: bool
    system_prompt: bool
    thinking_control: bool
```

V0.1 chưa cần expose nhiều.

---

# 69. Performance assumptions

V0.1 translate sequentially.

Không parallel chunks.

Lý do:

- context update của chunk N phải có thể dùng cho chunk N+1
- previous translation tail
- deterministic
- tránh tranh chấp SQLite
- tránh VRAM contention

---

# 70. Future semantic retrieval

Architecture phải cho phép thay:

```text
ExactMatchContextRetriever
```

bằng:

```text
CompositeContextRetriever
├── ExactEntityRetriever
├── RelationshipRetriever
├── RecentContextRetriever
└── SemanticFactRetriever
```

mà không đổi `TranslationService`.

---

# 71. V0.2 roadmap

Sau khi V0.1 ổn:

- EPUB import/export
- Manual context editor
- Better CLI review
- Context history
- Context rollback
- Sino-Vietnamese dictionary
- Translation QA pass
- Chapter summary
- Better addressing engine
- Retry policies per error
- Model benchmark command
- Translation statistics
- Multiple prompt profiles
- Semantic fact retrieval

---

# 72. V0.3 roadmap

- FastAPI
- Web UI
- Multi-provider
- llama.cpp provider
- Remote model API
- Embeddings
- Semantic RAG
- Translation comparison
- Optional second-pass editor
- Background worker architecture

---

# 73. Development milestones

## Milestone 1 — Bootstrap

- Python 3.12 project
- pyproject
- CLI
- config loader
- project init
- logging

Acceptance:

```bash
novel init demo
```

tạo project hợp lệ.

---

## Milestone 2 — Persistence

- SQLite
- SQLAlchemy
- Alembic
- repositories
- entity / term / relationship schema

Acceptance:

- migration chạy được
- CRUD context cơ bản hoạt động

---

## Milestone 3 — Import + Chunk

- import `.txt`
- source hash
- normalize
- chunker

Acceptance:

```bash
novel import ./chapters
```

tạo chapter records.

---

## Milestone 4 — Context Engine

- exact detection
- alias detection
- relationship expansion
- context snapshot
- merge
- conflict

Acceptance:

input chứa:

```text
林凡
```

retriever lấy đúng context liên quan.

---

## Milestone 5 — Ollama Provider

- httpx
- `/api/chat`
- structured JSON
- timeout
- retry
- metrics

Acceptance:

mock provider test pass và local Ollama e2e chạy được.

---

## Milestone 6 — Translation Pipeline

- prompt builder
- response validator
- translate chunk
- transaction
- previous tail

Acceptance:

```bash
novel translate 1
```

tạo translation và context updates.

---

## Milestone 7 — Resume

- chunk status
- failed job
- resume

Acceptance:

kill process giữa chapter rồi:

```bash
novel translate 1 --resume
```

không chạy lại completed chunks.

---

## Milestone 8 — Context CLI

- list
- conflicts
- resolve
- import/export

Acceptance:

user có thể inspect và sửa conflict.

---

# 74. Definition of Done V0.1

V0.1 được coi là hoàn tất khi:

- Python 3.12 chạy ổn.
- Project init hoạt động.
- Import chapter TXT hoạt động.
- SQLite migration hoạt động.
- Chapter được chunk đúng.
- Ollama provider hoạt động.
- Structured response được validate.
- Model có thể trả translation + context update.
- Context update được normalize.
- Duplicate không tạo record mới.
- Conflict không overwrite context cũ.
- Context confirmed được retrieve cho chunk sau.
- Relationship depth 1 hoạt động.
- Previous tail hoạt động.
- Chunk translation transaction-safe.
- Job resume hoạt động.
- Output chapter được assemble.
- Prompt version được lưu.
- Context snapshot được lưu.
- Model metrics được lưu.
- Context provenance được lưu.
- Có unit + integration tests cho core flow.
- Không có direct dependency Ollama trong domain/application logic.

---

# 75. Out-of-scope guarantees

V0.1 không hứa:

- bản dịch hoàn hảo
- automatic literary editing
- automatic fact verification
- perfect pronoun resolution
- perfect relationship extraction
- zero hallucination
- semantic retrieval toàn truyện

Tool chỉ đảm bảo infrastructure tốt để:

- context nhất quán hơn
- lỗi model không dễ đầu độc toàn project
- có thể review/debug
- có thể thay model
- có thể nâng cấp pipeline sau

---

# 76. Nguyên tắc cuối cùng

Tool này không nên được xây như:

```text
AI Translator
```

mà nên được coi là:

```text
Chinese → Vietnamese
Novel Translation Context Engine
+
Translation Orchestrator
+
Model Adapter
```

Model chỉ là một dependency có thể thay.

Giá trị cốt lõi của project nằm ở:

```text
context retrieval
context normalization
context persistence
context authority
context conflict handling
chunk continuity
prompt construction
structured validation
resume
debuggability
```

Nếu những phần trên được tách sạch từ V0.1, project có thể đổi từ:

```text
Ollama + Qwen
```

sang:

```text
Ollama + TranslateGemma
```

hoặc:

```text
llama.cpp
```

hoặc cloud provider khác mà không phải viết lại engine.
