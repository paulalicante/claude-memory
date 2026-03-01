"""
Retroactively apply topic extraction to all conversation entry titles.
No API calls - uses regex to extract file names, function names, and keywords.
"""

import re
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'memory.db')


SKIP_ABBRS = {
    'THE', 'AND', 'FOR', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HAS', 'HER',
    'WAS', 'ONE', 'OUR', 'OUT', 'ARE', 'HIS', 'HOW', 'ITS', 'LET', 'MAY',
    'NEW', 'NOW', 'OLD', 'SEE', 'WAY', 'WHO', 'DID', 'GET', 'GOT', 'HAD',
    'HIM', 'USE', 'WILL', 'BEEN', 'EACH', 'MAKE', 'LIKE', 'LONG', 'LOOK',
    'MANY', 'SOME', 'THEM', 'THEN', 'THIS', 'WHAT', 'WITH', 'HAVE', 'FROM',
    'THAT', 'THEY', 'SAID', 'JUST', 'ALSO', 'INTO', 'OVER', 'SUCH', 'TAKE',
    'THAN', 'VERY', 'WHEN', 'COME', 'COULD', 'ABOUT', 'AFTER', 'BACK',
    'ONLY', 'DONE', 'HERE', 'MUST', 'SURE', 'YEAH', 'DOES', 'STILL', 'WELL',
    'DONT', 'WANT', 'RIGHT', 'KNOW', 'NEED',
}


def extract_topics(content, max_topics=3):
    """Extract key topics from conversation content."""
    # Strip IDE metadata tags
    content = re.sub(r'<[^>]+>[^<]*</[^>]+>', '', content)

    topics = []
    seen = set()

    def add_topic(t):
        key = t.lower()
        if key not in seen:
            seen.add(key)
            topics.append(t)

    # 1. File names (highest priority)
    for m in re.finditer(r'\b([a-zA-Z_][\w-]*\.(py|js|ts|tsx|jsx|json|md|html|css|bat|sh|yaml|yml|toml|sql))\b', content):
        add_topic(m.group(1))
        if len(topics) >= max_topics:
            return topics

    # 2. Abbreviations and tech terms (e.g., MSIX, API, CORS, OAuth, PyQt6)
    for m in re.finditer(r'\b([A-Z][A-Z0-9]{2,}[a-z]*|[A-Z][a-z]+[A-Z]\w*)\b', content):
        term = m.group(1)
        if term.upper() not in SKIP_ABBRS and len(term) >= 3:
            add_topic(term)
            if len(topics) >= max_topics:
                return topics

    # 3. Function/class names
    for m in re.finditer(r'\b(?:def|function|async|class)\s+([a-zA-Z_]\w+)', content):
        add_topic(m.group(1))
        if len(topics) >= max_topics:
            return topics

    # 4. Action keywords (lowest priority)
    keywords = [
        'commit', 'push', 'merge', 'deploy', 'fix', 'bug', 'error', 'crash',
        'install', 'update', 'test', 'build', 'refactor', 'optimize',
        'database', 'api', 'server', 'login', 'auth', 'payment',
        'debug', 'config', 'setup', 'migrate', 'docker', 'git'
    ]
    lower = content.lower()
    for kw in keywords:
        if kw in lower:
            add_topic(kw)
            if len(topics) >= max_topics:
                return topics

    return topics


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all conversation entries with "Part N" in title
    cur.execute("SELECT id, title, content FROM entries WHERE category='conversation' AND title LIKE '%Part %'")
    rows = cur.fetchall()

    print(f"Found {len(rows)} entries to process...")

    updated = 0
    skipped = 0

    for row in rows:
        eid = row['id']
        old_title = row['title']
        content = row['content'] or ''

        # Extract part number
        part_match = re.search(r'\(Part (\d+)\)', old_title)
        if not part_match:
            skipped += 1
            continue
        part_num = part_match.group(1)

        # Extract platform prefix
        prefix_match = re.match(r'^([^:]+):', old_title)
        prefix = prefix_match.group(1) if prefix_match else 'Chat'

        topics = extract_topics(content)
        if not topics:
            skipped += 1
            continue

        new_title = f"{prefix}: {', '.join(topics)} (Part {part_num})"

        if new_title != old_title:
            cur.execute('UPDATE entries SET title=? WHERE id=?', (new_title, eid))
            # Update FTS index
            try:
                cur.execute('UPDATE entries_fts SET title=? WHERE rowid=?', (new_title, eid))
            except Exception:
                pass  # FTS update might fail if schema differs
            updated += 1

    conn.commit()
    conn.close()

    print(f"Updated: {updated}")
    print(f"Skipped (no topics found): {skipped}")
    print(f"Total processed: {len(rows)}")


if __name__ == '__main__':
    main()
