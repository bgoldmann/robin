"""
SQLite database integration for persisting investigations and IOCs.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

from utils import logger

DEFAULT_DB_PATH = Path.home() / ".robin" / "robin.db"


def _ensure_db_dir(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get database connection. Creates DB and tables if needed."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    _ensure_db_dir(path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS investigations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            refined_query TEXT,
            summary TEXT,
            timestamp TEXT NOT NULL,
            search_count INTEGER,
            filtered_count INTEGER,
            scraped_count INTEGER
        );
        CREATE TABLE IF NOT EXISTS search_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            source TEXT,
            UNIQUE(investigation_id, url),
            FOREIGN KEY (investigation_id) REFERENCES investigations(id)
        );
        CREATE TABLE IF NOT EXISTS iocs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id INTEGER NOT NULL,
            ioc_type TEXT NOT NULL,
            value TEXT NOT NULL,
            UNIQUE(investigation_id, ioc_type, value),
            FOREIGN KEY (investigation_id) REFERENCES investigations(id)
        );
        CREATE INDEX IF NOT EXISTS idx_iocs_type ON iocs(ioc_type);
        CREATE INDEX IF NOT EXISTS idx_iocs_value ON iocs(value);
        CREATE INDEX IF NOT EXISTS idx_inv_timestamp ON investigations(timestamp);
    """)


def save_investigation(
    conn: sqlite3.Connection,
    query: str,
    refined_query: str,
    summary: str,
    search_results: List[Dict[str, str]],
    scraped_urls: List[str],
    iocs: Optional[Dict[str, Set[str]]] = None,
) -> int:
    """
    Save an investigation to the database.
    Returns the investigation ID.
    """
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO investigations
           (query, refined_query, summary, timestamp, search_count, filtered_count, scraped_count)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            query,
            refined_query,
            summary,
            datetime.now().isoformat(),
            len(search_results),
            len(scraped_urls),
            len(scraped_urls),
        ),
    )
    inv_id = cur.lastrowid
    for r in search_results:
        url = r.get("link", "")
        title = r.get("title", "")
        source = "telegram" if ("t.me" in url or "telegram://" in url) else "darkweb"
        cur.execute(
            "INSERT OR IGNORE INTO search_results (investigation_id, url, title, source) VALUES (?, ?, ?, ?)",
            (inv_id, url[:2048], title[:512] if title else "", source),
        )
    if iocs:
        for ioc_type, values in iocs.items():
            for v in values:
                cur.execute(
                    "INSERT OR IGNORE INTO iocs (investigation_id, ioc_type, value) VALUES (?, ?, ?)",
                    (inv_id, ioc_type, str(v)[:1024]),
                )
    conn.commit()
    logger.info(f"Saved investigation {inv_id} to database")
    return inv_id


def list_investigations(
    conn: sqlite3.Connection,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List recent investigations."""
    cur = conn.cursor()
    cur.execute(
        """SELECT id, query, refined_query, timestamp, search_count, filtered_count, scraped_count
           FROM investigations ORDER BY timestamp DESC LIMIT ?""",
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]


def get_investigation(
    conn: sqlite3.Connection,
    inv_id: int,
) -> Optional[Dict[str, Any]]:
    """Get a single investigation by ID."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM investigations WHERE id = ?", (inv_id,))
    row = cur.fetchone()
    if not row:
        return None
    data = dict(row)
    cur.execute("SELECT url, title, source FROM search_results WHERE investigation_id = ?", (inv_id,))
    data["search_results"] = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT ioc_type, value FROM iocs WHERE investigation_id = ?", (inv_id,))
    iocs: Dict[str, List[str]] = {}
    for r in cur.fetchall():
        t, v = r["ioc_type"], r["value"]
        if t not in iocs:
            iocs[t] = []
        iocs[t].append(v)
    data["iocs"] = iocs
    return data
