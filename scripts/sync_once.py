import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import auto_sync_enterprise_daemon as daemon
res = daemon.sync_pool_accounts()
print("Sync result:", res)

import json
p = Path("D:/hermes-main/storage/pool_accounts.json")
if p.exists():
    data = json.loads(p.read_text(encoding="utf-8"))
    for a in data.get("accounts", []):
        print(a["name"], "->", a.get("reset_time_str"), "|", a.get("reset_label"), "| video_state:", a.get("video_state"))
