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
    for m in re.finditer(r'\b([a-zA-Z_][\w-]*\.(py|js|ts|tsx|jsx|json|md|html|css|bat|sh|yaml|yml|toml|sql|dart|swift|kt|rb|go|rs|vue|svelte))\b', content):
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

    # 3. Function/method names — both declarations AND calls like _get_zoom()
    for m in re.finditer(r'\b(?:def|function|async|class)\s+([a-zA-Z_]\w+)', content):
        add_topic(m.group(1))
        if len(topics) >= max_topics:
            return topics
    # Method calls with underscores (likely meaningful): _apply_zoom(), get_config()
    for m in re.finditer(r'\b([a-z][a-z_]+[a-z])\s*\(', content):
        name = m.group(1)
        if '_' in name and len(name) > 5:
            add_topic(name + '()')
            if len(topics) >= max_topics:
                return topics

    # 4. Backtick-quoted terms (often important: `MSIX`, `zoom`, `supabase`)
    for m in re.finditer(r'`([^`]{2,30})`', content):
        term = m.group(1).strip()
        if term and not term.startswith(('http', '//', '#')) and ' ' not in term:
            add_topic(term)
            if len(topics) >= max_topics:
                return topics

    # 5. Action keywords (lowest priority)
    keywords = [
        'commit', 'push', 'merge', 'deploy', 'fix', 'bug', 'error', 'crash',
        'install', 'update', 'test', 'build', 'refactor', 'optimize',
        'database', 'api', 'server', 'login', 'auth', 'payment',
        'debug', 'config', 'setup', 'migrate', 'docker', 'git',
        'zoom', 'blur', 'animation', 'recording', 'export', 'render',
        'supabase', 'stripe', 'firebase', 'flutter', 'react',
    ]
    lower = content.lower()
    for kw in keywords:
        if kw in lower:
            add_topic(kw)
            if len(topics) >= max_topics:
                return topics

    return topics


GENERIC_MESSAGES = {
    'continue', 'yes', 'no', 'ok', 'yes please', 'go ahead', 'go for it',
    'sure', 'thanks', 'thank you', 'please', 'do it', 'lets do it',
    'sounds good', 'perfect', 'great', 'nice', 'cool', 'agreed',
}


def get_first_meaningful_message(content, max_len=50):
    """Extract the first meaningful message from conversation content.
    Tries Human first, then Claude's response if Human is generic."""
    # Try Human first
    human_match = re.search(r'\*\*Human:\*\*\s*\n(.+?)(?:\n---|\n\*\*)', content, re.DOTALL)
    if human_match:
        msg = human_match.group(1).strip()
        msg = re.sub(r'<[^>]+>[^<]*</[^>]+>', '', msg).strip()
        if msg and len(msg) >= 8 and msg.lower() not in GENERIC_MESSAGES:
            if len(msg) > max_len:
                msg = msg[:max_len] + '...'
            return msg

    # Human was generic/missing — use first sentence of Claude's response
    claude_match = re.search(r'\*\*Claude:\*\*\s*\n(.+?)(?:\n---|\n\*\*|\Z)', content, re.DOTALL)
    if claude_match:
        msg = claude_match.group(1).strip()
        # Take first sentence only
        sentence_end = re.search(r'[.!?\n]', msg)
        if sentence_end:
            msg = msg[:sentence_end.start()].strip()
        msg = re.sub(r'<[^>]+>[^<]*</[^>]+>', '', msg).strip()
        # Remove leading filler words
        msg = re.sub(r'^(Done|Good|Great|OK|Sure|Right|Yes|Excellent|Alright|Perfect)[.,!]?\s*', '', msg).strip()
        # Remove leading "Now " or "Let me " to get to the meat
        msg = re.sub(r'^(Now|Now,|Let me|I\'ll|I will|I can see|I see)\s+', '', msg).strip()
        if msg and len(msg) >= 8:
            if len(msg) > max_len:
                msg = msg[:max_len] + '...'
            return msg

    return None


def retitle_entry(cur, eid, old_title, content):
    """Try to retitle a single entry. Returns True if updated."""
    # Extract part number if present
    part_match = re.search(r'\(Part (\d+)\)', old_title)
    part_suffix = f" (Part {part_match.group(1)})" if part_match else ''

    # Extract time if present, e.g., "(14:08)"
    time_match = re.search(r'\((\d{1,2}:\d{2})\)', old_title)
    time_suffix = f" ({time_match.group(1)})" if time_match and not part_match else ''

    # Try topic extraction first
    topics = extract_topics(content)
    if topics:
        new_title = f"{', '.join(topics)}{part_suffix}{time_suffix}"
    else:
        # Fall back to first user message
        user_msg = get_first_meaningful_message(content)
        if not user_msg:
            return False
        new_title = f"{user_msg}{part_suffix}{time_suffix}"

    if new_title != old_title:
        cur.execute('UPDATE entries SET title=? WHERE id=?', (new_title, eid))
        try:
            cur.execute('UPDATE entries_fts SET title=? WHERE rowid=?', (new_title, eid))
        except Exception:
            pass
        return True
    return False


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get ALL conversation entries (not just "Part N" ones)
    cur.execute("SELECT id, title, content FROM entries WHERE category='conversation'")
    rows = cur.fetchall()

    print(f"Found {len(rows)} conversation entries to process...")

    updated = 0
    skipped = 0

    for row in rows:
        eid = row['id']
        old_title = row['title']
        content = row['content'] or ''

        if retitle_entry(cur, eid, old_title, content):
            updated += 1
        else:
            skipped += 1

    conn.commit()
    conn.close()

    print(f"Updated: {updated}")
    print(f"Skipped (no topics found): {skipped}")
    print(f"Total processed: {len(rows)}")


if __name__ == '__main__':
    main()
