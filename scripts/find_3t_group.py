import sys
import json
import urllib.request

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

req = urllib.request.Request("http://127.0.0.1:3050/groups")
with urllib.request.urlopen(req, timeout=5) as resp:
    data = json.loads(resp.read().decode('utf-8'))

for g in data.get("groups", []):
    if "3TGLOBAL" in g.get("name", ""):
        print(f"Group ID: {g['id']}")
        print(f"Group Name: {g['name']}")
        print(f"Total Members: {g.get('totalMembers')}")
        print("Members:")
        for m in g.get("members", []):
            print(f" - {m.get('name')} (UID: {m.get('uid')})")
