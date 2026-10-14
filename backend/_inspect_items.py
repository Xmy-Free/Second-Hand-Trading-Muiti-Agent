import sqlite3

conn = sqlite3.connect(r'e:\project\大三上\Second-Hand-Trading-Muiti-Agent\backend\campus_mas.db')
cur = conn.cursor()

cur.execute("PRAGMA table_info(item)")
print("COLUMNS:")
for r in cur.fetchall():
    print(r)

print("\nALL ITEMS:")
cur.execute("SELECT id, title, category, image_url, status FROM item ORDER BY id")
for r in cur.fetchall():
    print(r)
