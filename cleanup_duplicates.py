"""
Script to find and remove duplicate entries tagged with 'conversation'.
Creates a backup before making any changes.

Duplicates are detected by content containment - when one entry's content
appears inside another (larger) entry, indicating they are snapshots of
the same conversation at different points in time.
"""

import sqlite3
from claude_memory.database import get_db_path, backup_database


def content_overlaps(c1: str, c2: str, chunk_size: int = 200, min_matches: int = 2) -> bool:
    """
    Check if c1's content significantly overlaps with c2.
    Samples multiple chunks from c1 and checks if they exist in c2.
    """
    matches = 0
    for start in range(0, min(len(c1), 1000), chunk_size):
        chunk = c1[start:start + chunk_size]
        if len(chunk) > 100 and chunk in c2:
            matches += 1
            if matches >= min_matches:
                return True
    return False


def find_conversation_duplicates() -> tuple[set, set]:
    """
    Find duplicate entries with 'conversation' category using content containment.
    Returns tuple of (entries_to_keep, entries_to_delete).
    """
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all entries with 'conversation' category
    cursor.execute("""
        SELECT id, title, content, tags, timestamp
        FROM entries
        WHERE category = 'conversation'
        ORDER BY id
    """)
    entries = list(cursor.fetchall())
    conn.close()

    if not entries:
        print("No entries found with 'conversation' category.")
        return set(), set()

    # Build containment graph: for each entry, find which entries contain its content
    contained_in = {e['id']: set() for e in entries}

    for i, e1 in enumerate(entries):
        for j, e2 in enumerate(entries):
            if i == j:
                continue
            if content_overlaps(e1['content'], e2['content']):
                contained_in[e1['id']].add(e2['id'])

    # Find entries to delete: entries whose content is contained in a larger entry
    to_delete = set()
    to_keep = set()

    entry_sizes = {e['id']: len(e['content']) for e in entries}

    for entry in entries:
        eid = entry['id']
        containers = contained_in[eid]
        if containers:
            # This entry's content is in other entries - check if any are larger
            larger = [c for c in containers if entry_sizes[c] > entry_sizes[eid]]
            if larger:
                to_delete.add(eid)
            else:
                to_keep.add(eid)
        else:
            to_keep.add(eid)

    return to_keep, to_delete


def display_results(to_keep: set, to_delete: set) -> None:
    """Display entries to keep and delete for review."""
    if not to_delete:
        print("No duplicates found!")
        return

    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"\n{'='*70}")
    print(f"DEDUPLICATION RESULTS")
    print(f"{'='*70}\n")

    print(f"=== ENTRIES TO KEEP ({len(to_keep)}) ===")
    for eid in sorted(to_keep):
        cursor.execute(
            "SELECT id, title, length(content) as size, timestamp FROM entries WHERE id = ?",
            (eid,)
        )
        row = cursor.fetchone()
        if row:
            print(f"  [KEEP] ID {eid:2d} ({row['size']:5d} chars): {row['title'][:50]}")

    print(f"\n=== ENTRIES TO DELETE ({len(to_delete)}) ===")
    for eid in sorted(to_delete):
        cursor.execute(
            "SELECT id, title, length(content) as size, timestamp FROM entries WHERE id = ?",
            (eid,)
        )
        row = cursor.fetchone()
        if row:
            print(f"  [DEL] ID {eid:2d} ({row['size']:5d} chars): {row['title'][:50]}")

    conn.close()
    print(f"\n{'='*70}")
    print(f"Total: Keep {len(to_keep)}, Delete {len(to_delete)}")
    print(f"{'='*70}\n")


def delete_duplicates(to_delete: set) -> None:
    """Delete the specified entries."""
    if not to_delete:
        return

    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    for delete_id in sorted(to_delete):
        cursor.execute("DELETE FROM entries WHERE id = ?", (delete_id,))
        print(f"  Deleted entry ID {delete_id}")

    conn.commit()
    conn.close()

    print(f"\n[KEEP] Successfully deleted {len(to_delete)} duplicate entries!")


def main():
    """Main cleanup routine."""
    print("\n" + "="*70)
    print("Claude Memory - Conversation Duplicates Cleanup")
    print("="*70 + "\n")

    # Step 1: Backup database
    print("Step 1: Creating database backup...")
    backup_path = backup_database()
    if backup_path:
        print(f"  [KEEP] Backup created: {backup_path}\n")
    else:
        print("  ⚠ No backup created (database may not exist yet)\n")

    # Step 2: Find duplicates using content containment
    print("Step 2: Scanning for duplicates (content containment analysis)...")
    to_keep, to_delete = find_conversation_duplicates()

    # Step 3: Display results
    print("Step 3: Review results:\n")
    display_results(to_keep, to_delete)

    # Step 4: Confirm and delete
    if to_delete:
        response = input("Proceed with deletion? (yes/no): ").strip().lower()
        if response in ['yes', 'y']:
            print("\nStep 4: Deleting duplicates...\n")
            delete_duplicates(to_delete)
            print("\n" + "="*70)
            print("Cleanup complete!")
            print("="*70 + "\n")
        else:
            print("\nCleanup cancelled.")
    else:
        print("No duplicates to delete.")


if __name__ == "__main__":
    main()
