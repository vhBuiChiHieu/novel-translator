from __future__ import annotations

import re
import unicodedata

from novel_translator.schemas.context_update import ContextUpdate


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\s*\n\s*", " ", normalized).strip()
    return normalized or None


def normalize_update(update: ContextUpdate) -> ContextUpdate:
    data = update.model_dump()
    for key, value in data.items():
        if isinstance(value, str) or value is None:
            data[key] = _clean(value)
    aliases = [_clean(alias) for alias in update.aliases]
    data["aliases"] = list(
        dict.fromkeys(alias for alias in aliases if alias and alias not in {data["source"], data["translation"]})
    )
    data["related_entities"] = list(dict.fromkeys(_clean(item) for item in update.related_entities if _clean(item)))
    if data["predicate"]:
        data["predicate"] = re.sub(r"\W+", "_", data["predicate"].lower()).strip("_")
    return ContextUpdate.model_validate(data)
