"""SQLite-backed cross-session entity memory with FTS5."""
from __future__ import annotations
import sqlite3
from datetime import datetime
from pathlib import Path

# Store in ~/.timbre so it persists across installs and locations
_DB_PATH = Path.home() / ".timbre" / "timbre.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            founder         TEXT NOT NULL,
            founder_en      TEXT,
            company         TEXT NOT NULL,
            valuation       TEXT,
            profile_path    TEXT,
            last_researched TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts
        USING fts5(founder, founder_en, company, content=entities, content_rowid=id)
    """)
    con.execute("""
        CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
            INSERT INTO entities_fts(rowid, founder, founder_en, company)
            VALUES (new.id, new.founder, COALESCE(new.founder_en,''), new.company);
        END
    """)
    con.commit()
    return con


def remember(entity: dict, profile_path: str) -> None:
    con = _conn()
    now = datetime.utcnow().isoformat()
    founder = entity.get("founder", "")
    founder_en = entity.get("founder_en", "")
    company = entity.get("company", "")
    valuation = entity.get("valuation", "")

    existing = con.execute(
        "SELECT id FROM entities WHERE founder=? AND company=?", (founder, company)
    ).fetchone()

    if existing:
        con.execute(
            "UPDATE entities SET last_researched=?, profile_path=?, valuation=?, founder_en=? WHERE id=?",
            (now, profile_path, valuation, founder_en, existing["id"]),
        )
        con.execute(
            "UPDATE entities_fts SET founder=?, founder_en=?, company=? WHERE rowid=?",
            (founder, founder_en or "", company, existing["id"]),
        )
    else:
        con.execute(
            "INSERT INTO entities (founder, founder_en, company, valuation, profile_path, last_researched) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (founder, founder_en, company, valuation, profile_path, now),
        )
    con.commit()
    con.close()


def recall(query: str) -> dict | None:
    con = _conn()
    words = [w for w in query.split() if len(w) > 1]
    if not words:
        con.close()
        return None
    fts_query = " OR ".join(words)
    row = con.execute(
        """
        SELECT e.*, rank FROM entities_fts f
        JOIN entities e ON e.id = f.rowid
        WHERE entities_fts MATCH ? ORDER BY rank LIMIT 1
        """,
        (fts_query,),
    ).fetchone()
    con.close()
    return dict(row) if row else None


def list_all() -> list[dict]:
    con = _conn()
    rows = con.execute("SELECT * FROM entities ORDER BY last_researched DESC").fetchall()
    con.close()
    return [dict(r) for r in rows]
