import sqlite3
from claude_memory.database import get_db_path

db_path = get_db_path()
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Get all entries with title containing [conversation]
cursor.execute("SELECT id, title, tags FROM entries WHERE title LIKE '%[conversation]%' ORDER BY id DESC LIMIT 30")
rows = cursor.fetchall()

print(f"Found {len(rows)} entries with '[conversation]' in title:\n")
for row in rows:
    print(f"ID {row[0]}: {row[1][:60]}")
    print(f"  Tags: {row[2]}")

conn.close()
