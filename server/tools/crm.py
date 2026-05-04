"""
CRM store — JSON file at <project_root>/crm/crm_db.json.

PRIMARY KEY: session_id (one entry per conversation).
Each entry grows turn-by-turn as the user provides information.

Cross-session recall works via find_latest_by_name(): when a returning user
is identified (e.g. via the frontend's localStorage cache), we look up the
latest record matching that name and pre-seed the new session from it.

Schema:
    {
      "<session_id>": {
        "session_id":          "<uuid>",
        "name":                "Aliza",
        "dietary_preferences": "vegetarian",
        "special_requests":    "window seat",
        "current_booking":     {"date": "...", "time": "...", "guests": "..."},
        "reservations":        [{"date","time","guests","dietary","special",
                                  "status","created_at"}],
        "last_date":  "...", "last_time": "...", "last_guests": "...",
        "created_at": "...", "last_updated": "..."
      }
    }
"""

import json
import threading
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CRM_DIR  = _PROJECT_ROOT / "crm"
CRM_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE  = CRM_DIR / "crm_db.json"

_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(name: str) -> str:
    return (name or "").strip().lower()


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _load_db() -> dict:
    if not DB_FILE.exists():
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_db(data: dict) -> None:
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[CRM ERROR] Could not save to {DB_FILE}: {e}", flush=True)


def _new_record(session_id: str) -> dict:
    return {
        "session_id":          session_id,
        "name":                None,
        "dietary_preferences": None,
        "special_requests":    None,
        "current_booking":     {},
        "reservations":        [],
        "created_at":          _now(),
        "last_updated":        _now(),
    }


# ---------------------------------------------------------------------------
# Public API — session-keyed
# ---------------------------------------------------------------------------

def get_session_record(session_id: str) -> dict:
    """Return the CRM record for *session_id*, or {} if none exists."""
    if not session_id:
        return {}
    with _lock:
        return _load_db().get(session_id, {})


def upsert_session(session_id: str, fields: dict) -> dict:
    """
    Create or update the per-session record. Booking-progress fields
    (date / time / guests) go into ``current_booking``; profile fields
    (name / dietary_preferences / special_requests) live at the top level.
    """
    if not session_id:
        return {"status": "error", "message": "session_id required"}
    fields = {k: v for k, v in (fields or {}).items() if v is not None}
    if not fields:
        return {"status": "noop"}
    print(f"[CRM] upsert_session({session_id[:8]}…, {fields})", flush=True)
    with _lock:
        data = _load_db()
        rec  = data.get(session_id) or _new_record(session_id)
        for k, v in fields.items():
            if k in ("date", "time", "guests"):
                rec.setdefault("current_booking", {})[k] = v
                rec[f"last_{k}"] = v
            elif k == "reservations":
                continue  # use add_reservation_to_session for these
            else:
                rec[k] = v
        rec["last_updated"] = _now()
        data[session_id] = rec
        _save_db(data)
        return {"status": "success", "record": rec}


def add_reservation_to_session(session_id: str, reservation: dict) -> dict:
    """Append a confirmed reservation to the session's history."""
    if not session_id:
        return {"status": "error", "message": "session_id required"}
    entry = dict(reservation)
    entry.setdefault("status", "confirmed")
    entry.setdefault("created_at", _now())
    with _lock:
        data = _load_db()
        rec  = data.get(session_id) or _new_record(session_id)
        rec.setdefault("reservations", []).append(entry)
        for f in ("date", "time", "guests"):
            if entry.get(f):
                rec[f"last_{f}"] = entry[f]
        rec["last_updated"] = _now()
        data[session_id] = rec
        _save_db(data)
        print(f"[CRM] add_reservation({session_id[:8]}…): {entry}", flush=True)
        return {"status": "success", "reservation": entry}


def _latest_active(record: dict) -> dict | None:
    for r in reversed(record.get("reservations") or []):
        if r.get("status") != "cancelled":
            return r
    return None


def update_latest_reservation_in_session(session_id: str, fields: dict) -> dict:
    """Modify the latest non-cancelled reservation in this session's history.
    If the session has no reservations yet but the user is recognized by name
    from a prior session, the prior reservation is copied into this session
    and modified — so each conversation owns its own audit trail.
    """
    if not session_id:
        return {"status": "error", "message": "session_id required"}
    fields = {k: v for k, v in (fields or {}).items() if v is not None}
    with _lock:
        data = _load_db()
        rec  = data.get(session_id) or _new_record(session_id)

        target = _latest_active(rec)
        if target is None and rec.get("name"):
            # Pull from a prior session for the same name
            prior = _find_latest_by_name_unlocked(data, rec["name"], exclude=session_id)
            prior_target = _latest_active(prior) if prior else None
            if prior_target:
                target = dict(prior_target)
                rec.setdefault("reservations", []).append(target)

        if target is None:
            data[session_id] = rec
            _save_db(data)
            return {"status": "error", "message": "no active reservation to update"}

        target.update(fields)
        for f in ("date", "time", "guests"):
            if fields.get(f):
                rec[f"last_{f}"] = fields[f]
        rec["last_updated"] = _now()
        data[session_id] = rec
        _save_db(data)
        print(f"[CRM] update_reservation({session_id[:8]}…): {target}", flush=True)
        return {"status": "success", "reservation": target}


def cancel_latest_reservation_in_session(session_id: str) -> dict:
    return update_latest_reservation_in_session(session_id, {"status": "cancelled"})


# ---------------------------------------------------------------------------
# Cross-session lookup by name (returning users)
# ---------------------------------------------------------------------------

def _find_latest_by_name_unlocked(data: dict, name: str, exclude: str | None = None) -> dict:
    norm = _normalize(name)
    if not norm:
        return {}
    matches = [
        r for sid, r in data.items()
        if sid != exclude and isinstance(r, dict) and _normalize(r.get("name", "")) == norm
    ]
    if not matches:
        return {}
    return max(matches, key=lambda r: r.get("last_updated", r.get("created_at", "")))


def find_latest_by_name(name: str, exclude_session: str | None = None) -> dict:
    """Return the most-recently-updated record for the customer with this name."""
    if not name:
        return {}
    with _lock:
        return _find_latest_by_name_unlocked(_load_db(), name, exclude=exclude_session)


def get_active_reservation(name: str) -> dict:
    """Latest non-cancelled reservation for *name* across all sessions."""
    rec = find_latest_by_name(name)
    return _latest_active(rec) if rec else {}


# ---------------------------------------------------------------------------
# Name-based convenience API (wraps session-based functions above)
# ---------------------------------------------------------------------------

def get_user(name: str) -> dict:
    """Return the most-recent CRM record for a user by name, or {}."""
    return find_latest_by_name(name) if name else {}


def update_user(name: str, fields: dict, session_id: str | None = None) -> dict:
    """Update profile fields for *name*. Uses *session_id* if no prior record exists."""
    if not name:
        return {"status": "error", "message": "Name required"}
    
    # Try to find a prior session to update
    rec = find_latest_by_name(name)
    sid = rec.get("session_id") if rec else session_id
    
    if not sid:
        return {"status": "error", "message": "No session_id provided for new user"}
    
    return upsert_session(sid, fields)


def add_reservation(name: str, reservation: dict, session_id: str | None = None) -> dict:
    """Append a confirmed reservation for *name*."""
    if not name:
        return {"status": "error", "message": "Name required"}
    
    rec = find_latest_by_name(name)
    sid = rec.get("session_id") if rec else session_id
    
    if not sid:
        return {"status": "error", "message": "No session found to add reservation"}
    
    return add_reservation_to_session(sid, reservation)


def cancel_latest_reservation(name: str, session_id: str | None = None) -> dict:
    """Cancel the latest active reservation for *name*."""
    if not name:
        return {"status": "error", "message": "Name required"}
    
    rec = find_latest_by_name(name)
    sid = rec.get("session_id") if rec else session_id
    
    if not sid:
        return {"status": "error", "message": "No session found to cancel reservation"}
    
    return cancel_latest_reservation_in_session(sid)


def update_latest_reservation(name: str, fields: dict, session_id: str | None = None) -> dict:
    """Update the latest active reservation for *name*."""
    if not name:
        return {"status": "error", "message": "Name required"}
    
    rec = find_latest_by_name(name)
    sid = rec.get("session_id") if rec else session_id
    
    if not sid:
        return {"status": "error", "message": "No session found to update reservation"}
    
    return update_latest_reservation_in_session(sid, fields)
