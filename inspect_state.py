import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect(r'C:\Users\ADMIN\AppData\Local\hermes\state.db')

rows = conn.execute("SELECT id, session_id, role, content, tool_calls FROM messages ORDER BY id DESC LIMIT 15").fetchall()
for r in reversed(rows):
    print(f"ID: {r[0]} | ROLE: {r[2]}")
    if r[4]:
        print("TOOL_CALLS:", r[4])
    print("CONTENT:", r[3])
    print("=" * 60)
