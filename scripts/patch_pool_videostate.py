import sys
from pathlib import Path

p = Path(r"D:\hermes-main\hermes-main\museai\bridge\pool.py")
text = p.read_text(encoding="utf-8")

old = """        vs = data.get("video_state")
        if vs in ("ok", "blocked") and not (vs == "blocked" and _video_states.get(name) == "ok"):
            # Set before the reload so a person's own video test wins over the auto-probe of fresh accounts.
            _video_states[name] = vs
            _json_save(VIDEO_STATE_FILE, _video_states)
        result = await self.reload_accounts()
        acc = self.accounts.get(name)
        return web.json_response({"ok": True, "name": name, "cookies": r["cookies"], **result,
                                  "account": acc.info() if acc else None})"""

new = """        vs = data.get("video_state")
        if vs in ("ok", "blocked"):
            _video_states[name] = vs
            _json_save(VIDEO_STATE_FILE, _video_states)
        result = await self.reload_accounts()
        acc = self.accounts.get(name)
        if acc and vs in ("ok", "blocked"):
            acc.force_video_state(vs)
        return web.json_response({"ok": True, "name": name, "cookies": r["cookies"], **result,
                                  "account": acc.info() if acc else None})"""

norm_text = text.replace("\r\n", "\n")
norm_old = old.replace("\r\n", "\n")
norm_new = new.replace("\r\n", "\n")

if norm_old in norm_text:
    norm_text = norm_text.replace(norm_old, norm_new)
    p.write_text(norm_text, encoding="utf-8")
    print("SUCCESS: Updated video_state handling in pool.py!")
else:
    print("ERROR: old text not found in pool.py")
