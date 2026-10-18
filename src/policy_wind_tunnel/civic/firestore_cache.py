"""
Persistent Firestore cache for Gemini-grounded lookups.

Falls back to a no-op if:
- google-cloud-firestore is not installed
- GOOGLE_CLOUD_PROJECT is not set
- Firestore is unreachable (network error at init time)

TTL: cached entries older than CACHE_TTL_DAYS are treated as missing and
refreshed, so MP detail stays reasonably current.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Any

CACHE_TTL_DAYS = 7
_COLLECTION = "pwt_lookup_cache"
_log = logging.getLogger(__name__)


def _doc_id(key: tuple[str, ...]) -> str:
    return "__".join(key).replace("/", "-").replace(" ", "_").lower()[:500]


class FirestoreCache:
    def __init__(self) -> None:
        self._db: Any = None
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        if not project:
            return
        try:
            from google.cloud import firestore  # type: ignore[import-untyped]
            self._db = firestore.Client(project=project)
            _log.info("Firestore cache connected (project=%s)", project)
        except Exception as exc:  # noqa: BLE001
            _log.warning("Firestore cache unavailable: %s", exc)

    @property
    def available(self) -> bool:
        return self._db is not None

    def get(self, key: tuple[str, ...]) -> dict[str, Any] | None:
        if self._db is None:
            return None
        try:
            doc = self._db.collection(_COLLECTION).document(_doc_id(key)).get()
            if not doc.exists:
                return None
            data = doc.to_dict() or {}
            cached_at_str = data.get("_cached_at", "")
            if cached_at_str:
                cached_at = datetime.date.fromisoformat(cached_at_str)
                if (datetime.date.today() - cached_at).days > CACHE_TTL_DAYS:
                    _log.debug("Firestore cache expired for %s", key)
                    return None
            payload = data.get("_payload")
            if payload is None:
                return None
            return json.loads(payload) if isinstance(payload, str) else payload
        except Exception as exc:  # noqa: BLE001
            _log.warning("Firestore cache get failed: %s", exc)
            return None

    def put(self, key: tuple[str, ...], value: dict[str, Any]) -> None:
        if self._db is None:
            return
        try:
            self._db.collection(_COLLECTION).document(_doc_id(key)).set({
                "_cached_at": datetime.date.today().isoformat(),
                "_key": list(key),
                "_payload": json.dumps(value),
            })
            _log.debug("Firestore cache written for %s", key)
        except Exception as exc:  # noqa: BLE001
            _log.warning("Firestore cache put failed: %s", exc)


_instance: FirestoreCache | None = None


def get_cache() -> FirestoreCache:
    global _instance
    if _instance is None:
        _instance = FirestoreCache()
    return _instance
