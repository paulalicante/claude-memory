import sqlite3
from claude_memory.database import get_db_path

db_path = get_db_path()
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Get sample tags
cursor.execute("SELECT DISTINCT tags FROM entries LIMIT 20")
tags = cursor.fetchall()

print("Sample tags in database:")
for tag in tags:
    print(f"  '{tag[0]}'")

# Count conversation entries
cursor.execute("SELECT COUNT(*) FROM entries WHERE tags LIKE ?", ('%conversation%',))
count = cursor.fetchone()[0]
print(f"\nEntries with 'conversation' in tags: {count}")

conn.close()
