import os
import sqlite3
import time

from config import DATABASE


def get_db():
    directory = os.path.dirname(DATABASE)
    if directory:
        os.makedirs(directory, exist_ok=True)

    db = sqlite3.connect(DATABASE, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def init_database():
    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS controller_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            fan_state INTEGER NOT NULL DEFAULT 0,
            control_mode TEXT NOT NULL DEFAULT 'manual',
            timer_end REAL,
            cooldown_end REAL,
            automation_enabled INTEGER NOT NULL DEFAULT 1,
            fan_while_printing INTEGER NOT NULL DEFAULT 1,
            fan_on_error INTEGER NOT NULL DEFAULT 1,
            cooldown_minutes INTEGER NOT NULL DEFAULT 30
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS temperature_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            nozzle REAL,
            bed REAL,
            chamber REAL,
            printer_state TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS prints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            started_at REAL,
            finished_at REAL,
            duration_seconds INTEGER,
            final_state TEXT,
            failure_reason TEXT
        )
    """)

    db.execute("""
        INSERT OR IGNORE INTO controller_state (id)
        VALUES (1)
    """)

    db.commit()
    db.close()


def get_state():
    db = get_db()
    row = db.execute("""
        SELECT * FROM controller_state WHERE id = 1
    """).fetchone()
    db.close()
    return row


def update_state(**values):
    if not values:
        return

    allowed = {
        "fan_state", "control_mode", "timer_end", "cooldown_end",
        "automation_enabled", "fan_while_printing",
        "fan_on_error", "cooldown_minutes"
    }

    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Invalid state fields: {', '.join(sorted(unknown))}")

    fields = []
    parameters = []

    for key, value in values.items():
        fields.append(f"{key} = ?")
        parameters.append(value)

    parameters.append(1)

    db = get_db()
    db.execute(
        f"UPDATE controller_state SET {', '.join(fields)} WHERE id = ?",
        parameters
    )
    db.commit()
    db.close()


def add_event(event_type, message):
    db = get_db()
    db.execute("""
        INSERT INTO events (timestamp, event_type, message)
        VALUES (?, ?, ?)
    """, (time.time(), event_type, message))
    db.commit()
    db.close()


def get_events(limit=100):
    limit = max(1, min(int(limit), 500))

    db = get_db()
    rows = db.execute("""
        SELECT * FROM events
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    db.close()

    return [dict(row) for row in rows]


def add_temperature(nozzle, bed, chamber, printer_state):
    db = get_db()
    db.execute("""
        INSERT INTO temperature_history
        (timestamp, nozzle, bed, chamber, printer_state)
        VALUES (?, ?, ?, ?, ?)
    """, (time.time(), nozzle, bed, chamber, printer_state))
    db.commit()
    db.close()


def get_temperature_history(limit=500):
    limit = max(1, min(int(limit), 5000))

    db = get_db()
    rows = db.execute("""
        SELECT * FROM temperature_history
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    db.close()

    return [dict(row) for row in reversed(rows)]


def get_temperature_history_since(seconds):
    seconds = max(60, min(int(seconds), 7 * 24 * 3600))
    cutoff = time.time() - seconds

    db = get_db()
    rows = db.execute("""
        SELECT * FROM temperature_history
        WHERE timestamp >= ?
        ORDER BY timestamp ASC
    """, (cutoff,)).fetchall()
    db.close()

    return [dict(row) for row in rows]


def start_print(filename):
    db = get_db()
    cursor = db.execute("""
        INSERT INTO prints (filename, started_at, final_state)
        VALUES (?, ?, ?)
    """, (filename, time.time(), "RUNNING"))
    db.commit()
    print_id = cursor.lastrowid
    db.close()
    return print_id


def finish_print(print_id, final_state, failure_reason=None):
    if not print_id:
        return

    now = time.time()

    db = get_db()
    row = db.execute("""
        SELECT started_at FROM prints WHERE id = ?
    """, (print_id,)).fetchone()

    if row is None:
        db.close()
        return

    duration = None
    if row["started_at"] is not None:
        duration = max(0, int(now - row["started_at"]))

    db.execute("""
        UPDATE prints
        SET finished_at = ?,
            duration_seconds = ?,
            final_state = ?,
            failure_reason = ?
        WHERE id = ?
    """, (now, duration, final_state, failure_reason, print_id))

    db.commit()
    db.close()


def get_prints(limit=50):
    limit = max(1, min(int(limit), 200))

    db = get_db()
    rows = db.execute("""
        SELECT * FROM prints
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    db.close()

    return [dict(row) for row in rows]
