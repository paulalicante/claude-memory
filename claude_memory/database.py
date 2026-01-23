"""
Database operations for Claude Memory app.
SQLite with FTS5 full-text search.
"""

import sqlite3
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .config import Config, get_app_dir
from . import constants


def get_db_path() -> Path:
    """Get the database file path."""
    config = Config()
    return Path(config.database_path)


def get_backup_dir() -> Path:
    """Get the backup directory path."""
    return get_app_dir() / constants.DEFAULT_BACKUP_DIR


def backup_database() -> Optional[Path]:
    """Create a backup of the database. Returns backup path or None if no db exists."""
    db_path = get_db_path()
    if not db_path.exists():
        return None

    backup_dir = get_backup_dir()
    backup_dir.mkdir(exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    backup_path = backup_dir / f"memory_{today}.db"

    # Only backup if we haven't already today
    if not backup_path.exists():
        shutil.copy2(db_path, backup_path)

    return backup_path


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_database() -> None:
    """Initialize the database schema."""
    conn = get_connection()
    cursor = conn.cursor()

    # Main entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            date TEXT NOT NULL,
            category TEXT,
            tags TEXT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            source_conversation TEXT
        )
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON entries(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON entries(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON entries(session_id)")

    # Add archived column if it doesn't exist (migration)
    cursor.execute("PRAGMA table_info(entries)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'archived' not in columns:
        cursor.execute("ALTER TABLE entries ADD COLUMN archived INTEGER DEFAULT 0")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_archived ON entries(archived)")

    # Add pdf_path column if it doesn't exist (migration for PDF support)
    cursor.execute("PRAGMA table_info(entries)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'pdf_path' not in columns:
        cursor.execute("ALTER TABLE entries ADD COLUMN pdf_path TEXT")

    # Trusted contacts table - people you've emailed become trusted senders
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trusted_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_received DATETIME,
            email_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trusted_email ON trusted_contacts(email)")

    # Saved emails table - track which email IDs have been saved to prevent duplicates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gmail_id TEXT UNIQUE NOT NULL,
            entry_id INTEGER,
            saved_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (entry_id) REFERENCES entries(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_id ON saved_emails(gmail_id)")

    # Check if FTS table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='entries_fts'
    """)
    if not cursor.fetchone():
        # Create FTS5 virtual table
        cursor.execute("""
            CREATE VIRTUAL TABLE entries_fts USING fts5(
                title, content, tags,
                content='entries',
                content_rowid='id'
            )
        """)

        # Triggers to keep FTS in sync
        cursor.execute("""
            CREATE TRIGGER entries_ai AFTER INSERT ON entries BEGIN
                INSERT INTO entries_fts(rowid, title, content, tags)
                VALUES (new.id, new.title, new.content, new.tags);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER entries_ad AFTER DELETE ON entries BEGIN
                INSERT INTO entries_fts(entries_fts, rowid, title, content, tags)
                VALUES('delete', old.id, old.title, old.content, old.tags);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER entries_au AFTER UPDATE ON entries BEGIN
                INSERT INTO entries_fts(entries_fts, rowid, title, content, tags)
                VALUES('delete', old.id, old.title, old.content, old.tags);
                INSERT INTO entries_fts(rowid, title, content, tags)
                VALUES (new.id, new.title, new.content, new.tags);
            END
        """)

    conn.commit()
    conn.close()


def get_current_session_id() -> str:
    """
    Get or create a session ID.
    New session if: first entry of day OR >4 hours since last entry.
    Format: YYYY-MM-DD-NN
    """
    config = Config()
    timeout_hours = config.session_timeout_hours
    today = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    # Get the last entry
    cursor.execute("""
        SELECT session_id, timestamp FROM entries
        ORDER BY timestamp DESC LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if row is None:
        # No entries yet, start first session
        return f"{today}-01"

    last_session_id = row["session_id"]
    last_timestamp = datetime.fromisoformat(row["timestamp"])

    # Check if we need a new session
    hours_since_last = (datetime.now() - last_timestamp).total_seconds() / 3600

    if hours_since_last > timeout_hours:
        # Timeout exceeded, new session
        if last_session_id.startswith(today):
            # Same day, increment session number
            try:
                session_num = int(last_session_id.split("-")[-1]) + 1
            except ValueError:
                session_num = 1
            return f"{today}-{session_num:02d}"
        else:
            # New day
            return f"{today}-01"
    else:
        # Continue existing session
        return last_session_id


def add_entry(
    title: str,
    content: str,
    category: Optional[str] = None,
    tags: Optional[str] = None,
    source_conversation: Optional[str] = None,
    pdf_path: Optional[str] = None,
) -> int:
    """
    Add a new entry to the database.
    Returns the entry ID.
    """
    session_id = get_current_session_id()
    today = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO entries (session_id, date, category, tags, title, content, source_conversation, pdf_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, today, category, tags, title, content, source_conversation, pdf_path),
    )

    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return entry_id


def search_entries(
    query: str = "",
    category: Optional[str] = None,
    days: Optional[int] = None,
    limit: int = 100,
) -> list[dict]:
    """
    Search entries using FTS5 and filters.
    Returns list of entry dicts.
    """
    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    # Base query - join with FTS if there's a search query
    if query.strip():
        # Use both FTS5 (for word prefix) and LIKE (for substring within words)
        # This handles both "paul*" matching "paulspainward" as a word
        # and "paulspain" matching within "paulspainward"
        search_terms = query.strip().split()
        fts_query = ' '.join([f"{term}*" for term in search_terms])

        base_sql = """
            SELECT DISTINCT e.* FROM entries e
            LEFT JOIN entries_fts fts ON e.id = fts.rowid
            WHERE (entries_fts MATCH ?
                   OR LOWER(e.title) LIKE ?
                   OR LOWER(e.content) LIKE ?)
        """
        params.append(fts_query)
        like_pattern = f"%{query.lower()}%"
        params.append(like_pattern)
        params.append(like_pattern)
    else:
        base_sql = "SELECT * FROM entries e WHERE 1=1"

    # Category filter
    if category:
        conditions.append("e.category = ?")
        params.append(category)

    # Date filter
    if days is not None:
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        conditions.append("e.date >= ?")
        params.append(cutoff_date)

    # Build final query
    if conditions:
        base_sql += " AND " + " AND ".join(conditions)

    base_sql += " ORDER BY e.timestamp DESC LIMIT ?"
    params.append(limit)

    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_entry_by_id(entry_id: int) -> Optional[dict]:
    """Get a single entry by ID."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM entries WHERE id = ?", (entry_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_recent_entries(limit: int = 10) -> list[dict]:
    """Get the most recent entries."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM entries ORDER BY timestamp DESC LIMIT ?", (limit,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_categories() -> list[str]:
    """Get all unique categories."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT DISTINCT category FROM entries WHERE category IS NOT NULL ORDER BY category"
    )
    rows = cursor.fetchall()
    conn.close()

    return [row["category"] for row in rows]


def get_entries_by_category(category: str, limit: int = 50) -> list[dict]:
    """Get entries filtered by category."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM entries WHERE category = ? ORDER BY timestamp DESC LIMIT ?",
        (category, limit),
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_statistics() -> dict:
    """Get entry statistics."""
    conn = get_connection()
    cursor = conn.cursor()

    # Total entries
    cursor.execute("SELECT COUNT(*) as total FROM entries")
    total = cursor.fetchone()["total"]

    # Entries this week
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) as count FROM entries WHERE date >= ?", (week_ago,))
    this_week = cursor.fetchone()["count"]

    # Entries this month
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) as count FROM entries WHERE date >= ?", (month_ago,))
    this_month = cursor.fetchone()["count"]

    # Categories count
    cursor.execute("SELECT COUNT(DISTINCT category) as count FROM entries WHERE category IS NOT NULL")
    categories = cursor.fetchone()["count"]

    conn.close()

    return {
        "total": total,
        "this_week": this_week,
        "this_month": this_month,
        "categories": categories,
    }


def delete_entry(entry_id: int) -> bool:
    """Delete an entry by ID. Returns True if deleted."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return deleted


# ============================================================================
# Trusted Contacts Functions
# ============================================================================

def add_trusted_contact(email: str, name: Optional[str] = None) -> bool:
    """
    Add an email address as a trusted contact.
    Returns True if added, False if already exists.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO trusted_contacts (email, name) VALUES (?, ?)",
            (email.lower().strip(), name),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Already exists
        return False
    finally:
        conn.close()


def add_trusted_contacts(emails: list[str]) -> int:
    """
    Add multiple email addresses as trusted contacts.
    Returns count of newly added contacts.
    """
    added = 0
    for email in emails:
        if add_trusted_contact(email):
            added += 1
    return added


def is_trusted_contact(email: str) -> bool:
    """Check if an email address is a trusted contact."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM trusted_contacts WHERE email = ?",
        (email.lower().strip(),)
    )
    result = cursor.fetchone() is not None
    conn.close()

    return result


def get_trusted_contacts(limit: int = 100) -> list[dict]:
    """Get all trusted contacts."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM trusted_contacts ORDER BY added_date DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def remove_trusted_contact(email: str) -> bool:
    """Remove a trusted contact. Returns True if removed."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM trusted_contacts WHERE email = ?",
        (email.lower().strip(),)
    )
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return deleted


def update_trusted_contact_received(email: str) -> None:
    """Update last_received timestamp and increment email_count for a contact."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE trusted_contacts
        SET last_received = CURRENT_TIMESTAMP, email_count = email_count + 1
        WHERE email = ?
        """,
        (email.lower().strip(),)
    )
    conn.commit()
    conn.close()


# ============================================================================
# Saved Emails Functions (duplicate prevention)
# ============================================================================

def is_email_saved(gmail_id: str) -> bool:
    """Check if an email has already been saved by its Gmail ID."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM saved_emails WHERE gmail_id = ?",
        (gmail_id,)
    )
    result = cursor.fetchone() is not None
    conn.close()

    return result


def mark_email_saved(gmail_id: str, entry_id: Optional[int] = None) -> None:
    """Mark an email as saved to prevent duplicate saves."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO saved_emails (gmail_id, entry_id) VALUES (?, ?)",
            (gmail_id, entry_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Already saved
    finally:
        conn.close()
