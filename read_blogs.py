import sqlite3
conn = sqlite3.connect('dulich.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT id, title, destination, summary FROM blogs ORDER BY id')
for row in cur.fetchall():
    print("ID:", row["id"], "| Dest:", row["destination"])
    print("  Title:", row["title"])
    print("  Summary:", row["summary"])
    print()
conn.close()
