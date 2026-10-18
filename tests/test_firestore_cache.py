"""Tests for the Firestore cache module. No real Firestore connection needed."""
import datetime
import json
from unittest.mock import MagicMock, patch

import pytest

from policy_wind_tunnel.civic.firestore_cache import (
    CACHE_TTL_DAYS,
    FirestoreCache,
    _doc_id,
)


def _make_cache(db=None):
    """Build a FirestoreCache with db injected directly (skips __init__ import)."""
    c = object.__new__(FirestoreCache)
    c._db = db
    return c


def _stub_doc(payload, days_ago=0):
    doc = MagicMock()
    doc.exists = True
    cached_at = (datetime.date.today() - datetime.timedelta(days=days_ago)).isoformat()
    doc.to_dict.return_value = {
        "_cached_at": cached_at,
        "_payload": json.dumps(payload),
    }
    return doc


def _stub_collection(db, doc_value):
    col = MagicMock()
    col.document.return_value.get.return_value = doc_value
    db.collection.return_value = col
    return col


# --- _doc_id ---

def test_doc_id_joins_key_parts():
    assert _doc_id(("in", "person", "rahul gandhi")) == "in__person__rahul_gandhi"


def test_doc_id_lowercases():
    assert _doc_id(("IN", "PERSON", "Modi")) == "in__person__modi"


def test_doc_id_strips_slashes():
    assert "/" not in _doc_id(("a/b", "c"))


# --- FirestoreCache.available ---

def test_available_false_when_no_db():
    assert not _make_cache(db=None).available


def test_available_true_when_db_set():
    assert _make_cache(db=MagicMock()).available


# --- FirestoreCache.get ---

def test_get_returns_none_when_db_none():
    assert _make_cache().get(("in", "person", "modi")) is None


def test_get_returns_payload_for_fresh_entry():
    db = MagicMock()
    payload = {"name": "Narendra Modi", "career": []}
    _stub_collection(db, _stub_doc(payload, days_ago=1))
    result = _make_cache(db).get(("in", "person", "modi"))
    assert result == payload


def test_get_returns_none_for_expired_entry():
    db = MagicMock()
    _stub_collection(db, _stub_doc({"name": "old"}, days_ago=CACHE_TTL_DAYS + 1))
    assert _make_cache(db).get(("in", "person", "old")) is None


def test_get_returns_none_when_doc_does_not_exist():
    db = MagicMock()
    missing = MagicMock()
    missing.exists = False
    _stub_collection(db, missing)
    assert _make_cache(db).get(("in", "person", "nobody")) is None


def test_get_returns_none_on_firestore_exception():
    db = MagicMock()
    db.collection.side_effect = RuntimeError("network error")
    assert _make_cache(db).get(("in", "person", "x")) is None


def test_get_returns_none_when_payload_missing():
    db = MagicMock()
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = {"_cached_at": datetime.date.today().isoformat()}
    _stub_collection(db, doc)
    assert _make_cache(db).get(("in", "person", "x")) is None


# --- FirestoreCache.put ---

def test_put_writes_to_correct_collection_and_doc():
    db = MagicMock()
    col = MagicMock()
    db.collection.return_value = col
    key = ("in", "person", "kejriwal")
    _make_cache(db).put(key, {"name": "Arvind Kejriwal"})
    db.collection.assert_called_once_with("pwt_lookup_cache")
    col.document.assert_called_once_with(_doc_id(key))
    col.document().set.assert_called_once()
    written = col.document().set.call_args[0][0]
    assert written["_key"] == list(key)
    assert written["_cached_at"] == datetime.date.today().isoformat()
    assert json.loads(written["_payload"]) == {"name": "Arvind Kejriwal"}


def test_put_is_silent_when_db_none():
    _make_cache(db=None).put(("in", "x"), {"v": 1})  # must not raise


def test_put_is_silent_on_firestore_exception():
    db = MagicMock()
    db.collection.side_effect = RuntimeError("quota exceeded")
    _make_cache(db).put(("in", "x"), {"v": 1})  # must not raise


# --- get_cache singleton ---

def test_get_cache_returns_same_instance():
    from policy_wind_tunnel.civic import firestore_cache
    firestore_cache._instance = None
    with patch.dict("os.environ", {}, clear=False):
        import os
        os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
        c1 = firestore_cache.get_cache()
        c2 = firestore_cache.get_cache()
        assert c1 is c2
    firestore_cache._instance = None


def test_get_cache_unavailable_without_project(monkeypatch):
    from policy_wind_tunnel.civic import firestore_cache
    firestore_cache._instance = None
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    c = firestore_cache.get_cache()
    assert not c.available
    firestore_cache._instance = None
