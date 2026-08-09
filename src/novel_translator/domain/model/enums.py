from enum import StrEnum


class ContextType(StrEnum):
    CHARACTER = "character"
    TERM = "term"
    LOCATION = "location"
    ORGANIZATION = "organization"
    RELATIONSHIP = "relationship"
    ADDRESSING = "addressing"
    WORLD_FACT = "world_fact"


class ContextStatus(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ChapterStatus(StrEnum):
    IMPORTED = "imported"
    TRANSLATED = "translated"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ChunkStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConflictStatus(StrEnum):
    OPEN = "open"
    ACCEPT_EXISTING = "accept_existing"
    ACCEPT_CANDIDATE = "accept_candidate"
    CUSTOM = "custom"


class EntityType(StrEnum):
    CHARACTER = "character"
    LOCATION = "location"
    ORGANIZATION = "organization"
