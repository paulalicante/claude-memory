"""
MCP Server for Claude Memory.
Exposes the memory database to Claude via Model Context Protocol.

Run with: python mcp_server.py
Or configure in Claude Code settings.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from claude_memory.notifications import notify_saved
from claude_memory.ai_query import ask_memories as ai_ask_memories, NoAPIKeyError, AIQueryError

# Database path
DB_PATH = Path(__file__).parent / "memory.db"

# Create MCP server
mcp = FastMCP("Claude Memory")


def get_connection() -> sqlite3.Connection:
    """Get a database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@mcp.tool()
def search_memories(query: str, limit: int = 20, include_archived: bool = False) -> list[dict]:
    """
    Search memories using full-text search.

    Args:
        query: Search terms to find in title, content, or tags
        limit: Maximum number of results (default 20)
        include_archived: If True, include archived memories (default False)

    Returns:
        List of matching memory entries with id, title, category, tags, date, and content
    """
    conn = get_connection()
    cursor = conn.cursor()

    archived_filter = "" if include_archived else "AND (e.archived IS NULL OR e.archived = 0)"

    if query.strip():
        cursor.execute(f"""
            SELECT e.id, e.title, e.category, e.tags, e.date, e.content, e.session_id, e.archived
            FROM entries e
            JOIN entries_fts fts ON e.id = fts.rowid
            WHERE entries_fts MATCH ? {archived_filter}
            ORDER BY e.timestamp DESC
            LIMIT ?
        """, (query, limit))
    else:
        cursor.execute(f"""
            SELECT id, title, category, tags, date, content, session_id, archived
            FROM entries e
            WHERE 1=1 {archived_filter}
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


@mcp.tool()
def get_memory(entry_id: int) -> dict | None:
    """
    Get a specific memory entry by ID.

    Args:
        entry_id: The ID of the memory to retrieve

    Returns:
        The full memory entry or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM entries WHERE id = ?", (entry_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


@mcp.tool()
def get_recent_memories(limit: int = 10, include_archived: bool = False) -> list[dict]:
    """
    Get the most recent memory entries.

    Args:
        limit: Number of entries to return (default 10)
        include_archived: If True, include archived memories (default False)

    Returns:
        List of recent memory entries
    """
    conn = get_connection()
    cursor = conn.cursor()

    archived_filter = "" if include_archived else "WHERE (archived IS NULL OR archived = 0)"

    cursor.execute(f"""
        SELECT id, title, category, tags, date, content, session_id, archived
        FROM entries
        {archived_filter}
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


@mcp.tool()
def get_memories_by_category(category: str, limit: int = 20, include_archived: bool = False) -> list[dict]:
    """
    Get memories filtered by category.

    Args:
        category: The category to filter by
        limit: Maximum results (default 20)
        include_archived: If True, include archived memories (default False)

    Returns:
        List of memories in the specified category
    """
    conn = get_connection()
    cursor = conn.cursor()

    archived_filter = "AND (archived IS NULL OR archived = 0)" if not include_archived else ""

    cursor.execute(f"""
        SELECT id, title, category, tags, date, content, session_id, archived
        FROM entries
        WHERE category = ? {archived_filter}
        ORDER BY timestamp DESC
        LIMIT ?
    """, (category, limit))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


@mcp.tool()
def list_categories() -> list[str]:
    """
    List all categories that have been used.

    Returns:
        List of category names
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT category FROM entries
        WHERE category IS NOT NULL
        ORDER BY category
    """)

    rows = cursor.fetchall()
    conn.close()

    return [row["category"] for row in rows]


@mcp.tool()
def get_memory_stats() -> dict:
    """
    Get statistics about the memory database.

    Returns:
        Dictionary with total entries, entries this week/month, and category count
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Total
    cursor.execute("SELECT COUNT(*) as total FROM entries")
    total = cursor.fetchone()["total"]

    # This week
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) as count FROM entries WHERE date >= ?", (week_ago,))
    this_week = cursor.fetchone()["count"]

    # This month
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) as count FROM entries WHERE date >= ?", (month_ago,))
    this_month = cursor.fetchone()["count"]

    # Categories
    cursor.execute("SELECT COUNT(DISTINCT category) as count FROM entries WHERE category IS NOT NULL")
    categories = cursor.fetchone()["count"]

    conn.close()

    return {
        "total_entries": total,
        "entries_this_week": this_week,
        "entries_this_month": this_month,
        "category_count": categories,
    }


@mcp.tool()
def archive_memory(entry_id: int) -> dict:
    """
    Archive a memory so it doesn't appear in regular searches.
    Archived memories can still be accessed with include_archived=True.

    Args:
        entry_id: The ID of the memory to archive

    Returns:
        Status message with the archived entry's title
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get the entry title first
    cursor.execute("SELECT title FROM entries WHERE id = ?", (entry_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"success": False, "message": f"Memory with ID {entry_id} not found"}

    title = row["title"]

    # Archive it
    cursor.execute("UPDATE entries SET archived = 1 WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()

    return {"success": True, "message": f"Archived: {title}", "id": entry_id, "title": title}


@mcp.tool()
def unarchive_memory(entry_id: int) -> dict:
    """
    Unarchive a memory so it appears in regular searches again.

    Args:
        entry_id: The ID of the memory to unarchive

    Returns:
        Status message with the unarchived entry's title
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get the entry title first
    cursor.execute("SELECT title FROM entries WHERE id = ?", (entry_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"success": False, "message": f"Memory with ID {entry_id} not found"}

    title = row["title"]

    # Unarchive it
    cursor.execute("UPDATE entries SET archived = 0 WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()

    return {"success": True, "message": f"Unarchived: {title}", "id": entry_id, "title": title}


@mcp.tool()
def get_archived_memories(limit: int = 50) -> list[dict]:
    """
    Get all archived memories.

    Args:
        limit: Maximum number of results (default 50)

    Returns:
        List of archived memory entries
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, category, tags, date, content, session_id, archived
        FROM entries
        WHERE archived = 1
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


@mcp.tool()
def add_memory(title: str, content: str, category: str = None, tags: str = None) -> dict:
    """
    Add a new memory entry to the database.

    Args:
        title: Title of the memory
        content: The content/body of the memory
        category: Optional category (e.g., "insight", "thesis", "documentation")
        tags: Optional comma-separated tags

    Returns:
        The created memory entry with its ID
    """
    conn = get_connection()
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    # Get or create session ID
    cursor.execute("""
        SELECT session_id, timestamp FROM entries
        ORDER BY timestamp DESC LIMIT 1
    """)
    row = cursor.fetchone()

    if row is None:
        session_id = f"{today}-01"
    else:
        last_session = row["session_id"]
        last_time = datetime.fromisoformat(row["timestamp"])
        hours_since = (datetime.now() - last_time).total_seconds() / 3600

        if hours_since > 4:
            if last_session.startswith(today):
                try:
                    num = int(last_session.split("-")[-1]) + 1
                except ValueError:
                    num = 1
                session_id = f"{today}-{num:02d}"
            else:
                session_id = f"{today}-01"
        else:
            session_id = last_session

    cursor.execute("""
        INSERT INTO entries (session_id, date, category, tags, title, content)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, today, category, tags, title, content))

    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Show toast notification
    notify_saved(title)

    return {
        "id": entry_id,
        "title": title,
        "content": content,
        "category": category,
        "tags": tags,
        "date": today,
        "session_id": session_id,
    }


@mcp.tool()
def ask_memories(question: str, search_terms: str = None, category: str = None) -> str:
    """
    Ask a question about memories using AI.

    This tool searches for relevant memories and uses Claude to analyze and answer
    questions about them. Great for summarizing, finding patterns, or asking
    natural language questions about your stored knowledge.

    Requires an Anthropic API key configured in config.json.

    Args:
        question: Natural language question to answer (e.g., "What are my thoughts on Tesla?")
        search_terms: Optional specific search terms (defaults to extracting from question)
        category: Optional category filter

    Returns:
        AI-generated answer based on relevant memories

    Examples:
        - "What are my investment theses?"
        - "Summarize my ideas about robotics"
        - "What did I learn about Spanish vocabulary?"
    """
    try:
        return ai_ask_memories(
            question=question,
            search_query=search_terms,
            category=category,
            limit=15,
        )
    except NoAPIKeyError:
        return (
            "Error: No Anthropic API key configured.\n\n"
            "To use AI features, add your API key to config.json:\n"
            '  "ai_api_key": "sk-ant-..."\n\n'
            "You can get an API key at https://console.anthropic.com/"
        )
    except AIQueryError as e:
        return f"AI Error: {e}"


if __name__ == "__main__":
    mcp.run()
