"""
Tool: lookup_reservation / save_reservation
Stores and retrieves reservations from a local SQLite database.
The DB is created automatically at server/tools/reservations.db on first use.
"""

import sqlite3
import logging
from pathlib import Path

logger  = logging.getLogger("tool.reservation_lookup")
DB_PATH = Path(__file__).resolve().parent / "reservations.db"

# Tool schema
TOOL_SCHEMA = {
    "name":        "lookup_reservation",
    "description": "Look up an existing reservation by the name it was booked under.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The name on the reservation."}
        },
        "required": ["name"]
    }
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _init_db() -> None:
    """Create the reservations table if it does not exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT    DEFAULT '',
            name       TEXT    NOT NULL,
            date       TEXT    DEFAULT '',
            time       TEXT    DEFAULT '',
            guests     TEXT    DEFAULT '',
            dietary    TEXT    DEFAULT '',
            special    TEXT    DEFAULT '',
            status     TEXT    DEFAULT 'confirmed',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def lookup_reservation(name: str) -> dict:
    """
    Look up active reservations whose name contains *name* (case-insensitive).
    Always returns a dict with 'status': 'ok' or 'status': 'error'.
    """
    if not name or not name.strip():
        return {"status": "error", "message": "Please provide a name to look up."}

    _init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            """SELECT name, date, time, guests, dietary, special, status
               FROM   reservations
               WHERE  LOWER(name) LIKE ?
               AND    status != 'cancelled'
               ORDER  BY id DESC""",
            (f"%{name.lower().strip()}%",)
        ).fetchall()
        conn.close()

        if not rows:
            return {
                "status":  "ok",
                "found":   False,
                "message": f"No active reservation found under '{name}'. "
                           "Please check the name or call us on +1-800-555-1234."
            }

        reservations = [
            {
                "name":    r[0], "date":    r[1], "time":    r[2],
                "guests":  r[3], "dietary": r[4], "special": r[5],
                "status":  r[6]
            }
            for r in rows
        ]
        return {"status": "ok", "found": True, "reservations": reservations}

    except Exception as e:
        logger.error(f"[LOOKUP] DB error: {e}")
        return {"status": "error", "message": "Could not access reservation records. Please call us directly."}


def _latest_active_id(conn: sqlite3.Connection, name: str) -> int | None:
    row = conn.execute(
        """SELECT id FROM reservations
           WHERE LOWER(name) = ? AND status != 'cancelled'
           ORDER BY id DESC LIMIT 1""",
        (name.lower().strip(),),
    ).fetchone()
    return row[0] if row else None


def update_reservation(name: str, fields: dict) -> dict:
    """
    Update the latest non-cancelled reservation under *name* with the supplied
    fields. Allowed keys: date, time, guests, dietary, special, status.
    """
    if not name:
        return {"status": "error", "message": "Name is required."}
    allowed = {"date", "time", "guests", "dietary", "special", "status"}
    fields = {k: v for k, v in (fields or {}).items() if k in allowed and v is not None}
    if not fields:
        return {"status": "error", "message": "No valid fields to update."}

    _init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        rid = _latest_active_id(conn, name)
        if rid is None:
            conn.close()
            return {"status": "error", "message": f"No active reservation found under '{name}'."}
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [rid]
        conn.execute(f"UPDATE reservations SET {sets} WHERE id = ?", values)
        conn.commit()
        conn.close()
        logger.info(f"[UPDATE] reservation id={rid} for '{name}' set {fields}")
        return {"status": "ok", "message": f"Reservation for {name} updated.", "fields": fields}
    except Exception as e:
        logger.error(f"[UPDATE] DB error: {e}")
        return {"status": "error", "message": "Could not update reservation."}


def cancel_reservation(name: str) -> dict:
    """Mark the latest active reservation for *name* as cancelled."""
    if not name:
        return {"status": "error", "message": "Name is required."}
    _init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        rid = _latest_active_id(conn, name)
        if rid is None:
            conn.close()
            return {"status": "error", "message": f"No active reservation found under '{name}'."}
        conn.execute("UPDATE reservations SET status = 'cancelled' WHERE id = ?", (rid,))
        conn.commit()
        conn.close()
        logger.info(f"[CANCEL] reservation id={rid} for '{name}' cancelled")
        return {"status": "ok", "message": f"Reservation for {name} cancelled."}
    except Exception as e:
        logger.error(f"[CANCEL] DB error: {e}")
        return {"status": "error", "message": "Could not cancel reservation."}


def save_reservation(name: str, date: str, time: str, guests: str,
                     dietary: str = "", special: str = "",
                     session_id: str = "") -> dict:
    """
    Persist a confirmed reservation to the SQLite database.
    Called automatically by conversation_manager when stage == 'confirmed'.
    Always returns a dict with 'status': 'ok' or 'status': 'error'.
    """
    if not name:
        return {"status": "error", "message": "Cannot save reservation without a name."}

    _init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """INSERT INTO reservations
               (session_id, name, date, time, guests, dietary, special)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, name, date, time, guests, dietary or "", special or "")
        )
        conn.commit()
        conn.close()
        logger.info(f"[SAVE] Reservation persisted — name='{name}' date='{date}' time='{time}' guests='{guests}'")
        return {"status": "ok", "message": f"Reservation for {name} saved successfully."}

    except Exception as e:
        logger.error(f"[SAVE] DB error: {e}")
        return {"status": "error", "message": "Could not save reservation to database."}