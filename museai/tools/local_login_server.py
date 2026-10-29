#!/usr/bin/env python3
"""
Trình đăng nhập local cho nút "Đăng nhập local" trên dashboard.
Chạy trên máy có màn hình (IP dân dụng): mở Chrome thật, bạn tự giải captcha, cookie được đẩy
thẳng lên pool (VPS) qua POST /v1/accounts. Dashboard nói chuyện với server này ở 127.0.0.1.

  python3 tools/local_login_server.py [--port 8771]
"""
import argparse
import asyncio
import json
import os
import sys
import urllib.request
from datetime import datetime

os.environ["MUSE_LOGIN_MANUAL"] = "1"  # before auto_login is imported
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from aiohttp import web  # noqa: E402
from bridge import auto_login, gologin_browser  # noqa: E402

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Private-Network": "true",
}


def _post_json(url: str, key: str, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-API-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}"}


def _name(line: str):
    try:
        return auto_login.parse_account_string(line)["name"]
    except Exception:
        return None


STOP = {"flag": False, "browser": None}
HOLD = {"fut": None}  # resolved by /confirm with "ok" | "fail" while a logged-in Chrome is kept open for a manual video test


async def handle_confirm(request):
    data = await request.json()
    fut = HOLD["fut"]
    if fut and not fut.done():
        fut.set_result("ok" if data.get("result") == "ok" else "blocked")
    return web.json_response({"ok": True}, headers=CORS)



async def handle_stop(request):
    STOP["flag"] = True
    if HOLD["fut"] and not HOLD["fut"].done():
        HOLD["fut"].set_result("skip")
    b = STOP["browser"]
    if b:
        try:
            await b.close()
        except Exception:
            pass
    return web.json_response({"ok": True}, headers=CORS)


async def handle_login(request: web.Request) -> web.StreamResponse:
    data = await request.json()
    lines = [l.strip() for l in str(data.get("accounts_raw") or "").splitlines() if l.strip() and not l.startswith("#")]
    skip = set(data.get("skip") or [])
    skipped = []
    if skip:
        skipped = [l for l in lines if _name(l) in skip]
        lines = [l for l in lines if _name(l) not in skip]
    target = str(data.get("target") or "").rstrip("/")
    key = str(data.get("key") or "")
    overwrite = bool(data.get("overwrite"))
    resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache", **CORS})
    await resp.prepare(request)

    async def push(message, status="", progress=None, data=None):
        ev = {"type": "log", "message": message, "status": status, "progress": progress, "data": data,
              "timestamp": datetime.now().isoformat()}
        try:
            await resp.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
        except Exception:
            pass

    from playwright.async_api import async_playwright
    total, ok = len(lines), 0
    if skipped:
        await push(f"⏭ Bỏ qua {len(skipped)} tài khoản đang hoạt động (chỉ đăng nhập lại khi expired)", "SKIP")
    if not total:
        await push("Không có tài khoản nào cần đăng nhập.", "ALL_DONE", {"total": 0, "current": 0})
        await resp.write_eof()
        return resp
    auto_login.MANUAL_CAPTCHA = True
    pw = await async_playwright().start()
    use_gologin = gologin_browser.available() and os.environ.get("MUSE_LOGIN_GOLOGIN", "1") != "0"
    if use_gologin:
        await push("🦊 Dùng profile GoLogin (token) — mỗi tài khoản một profile sạch, xoá sau khi xong", "GOLOGIN")
    else:
        await push("🌐 Dùng Chrome thông thường (nếu gặp reCAPTCHA, bạn có thể tự click giải trực tiếp trên cửa sổ)", "CHROME")
    STOP["flag"] = False
    try:
        for idx, raw in enumerate(lines, 1):
            if STOP["flag"]:
                await push("⏹ Đã dừng theo yêu cầu.", "STOPPED")
                break
            try:
                label = auto_login.parse_account_string(raw)["email"]
            except Exception:
                label = f"Dòng #{idx}"
            prog = {"current": idx, "total": total, "email": label}
            await push(f"Đang xử lý [{idx}/{total}]: {label}...", "ACCOUNT_START", prog)
            loop = asyncio.get_running_loop()
            handle, browser, ctx = None, None, None
            verdict = {"v": "skip"}

            async def hold(r, prog=prog, label=label, verdict=verdict):
                # Keep the logged-in Chrome open: the person tries a video in it, then answers on the page.
                HOLD["fut"] = loop.create_future()
                await push(f"🍪 Đăng nhập xong {label} — Chrome vẫn mở, hãy thử tạo video rồi bấm kết quả ở trang này.",
                           "READY", prog, {"name": r["name"], "cookies": r["cookies"]})
                verdict["v"] = await HOLD["fut"]
                HOLD["fut"] = None

            try:
                if use_gologin:
                    handle = await gologin_browser.open_profile(f"muse-{label.split('@')[0]}"[:60])
                    browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{handle['port']}")
                    ctx = browser.contexts[0]
                else:
                    browser = await pw.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
                STOP["browser"] = browser
                res = await auto_login.extract_account_cookies(
                    browser, raw, logger=lambda m, st=None: loop.create_task(push(m, st or "", prog)), context=ctx, hold=hold)
            except Exception as e:
                res = {"ok": False, "error": str(e)}
            finally:
                STOP["browser"] = None
                try:
                    if browser:
                        await browser.close()
                except Exception:
                    pass
                if handle:
                    await gologin_browser.close_profile(handle)
            if STOP["flag"]:
                continue
            if not res.get("ok"):
                await push(f"❌ Thất bại {label}: {res.get('error')}", "ERROR", prog)
                continue
            if verdict["v"] == "skip":
                continue
            video_state = verdict["v"]  # "ok" | "blocked" (blocked = image-only account, still goes into the pool)
            await push(f"🎬 {label}: tạo video OK" if video_state == "ok"
                       else f"🖼️ {label}: không tạo được video — nạp vào Pool để chỉ tạo ảnh", "VIDEOOK", prog)
            if not key:
                # Dashboard logs in with a session cookie, not an API key: hand the cookies to the opener page.
                ok += 1
                await push(f"🍪 Đăng nhập xong {label} ({res['name']}) — chuyển cookie cho dashboard nạp vào Pool...", "COOKIE",
                           prog, {"name": res["name"], "cookies": res["cookies"], "overwrite": overwrite,
                                  "video_state": video_state})
                continue
            w = await asyncio.to_thread(_post_json, f"{target}/v1/accounts", key,
                                        {"name": res["name"], "cookies": res["cookies"], "overwrite": overwrite,
                                         "video_state": video_state})
            if w.get("ok"):
                ok += 1
                await push(f"✅ Đã nạp {label} ({res['name']}) vào Pool", "SUCCESS", prog)
            else:
                await push(f"❌ Không nạp được {label} lên pool: {w.get('error')}", "ERROR", prog)
    finally:
        await pw.stop()
    await push(f"Hoàn thành: nạp {ok}/{total} tài khoản", "ALL_DONE", {"total": total, "current": total})
    await resp.write_eof()
    return resp



PAGE = r"""<!doctype html><meta charset=utf-8><title>Đăng nhập local</title>
<style>button{padding:6px 12px;border:0;border-radius:6px;cursor:pointer;margin-right:6px}body{font:14px system-ui;background:#111;color:#ddd;margin:0;padding:20px}h3{margin:0 0 8px}
#st{color:#9aa;margin-bottom:8px}#bar{height:6px;background:#333;border-radius:3px;margin-bottom:10px}
#bar i{display:block;height:6px;width:0;background:#7c7cff;border-radius:3px}
pre{background:#000;padding:12px;border-radius:8px;height:70vh;overflow:auto;white-space:pre-wrap;font-size:12px}</style>
<h3>🖥️ Đăng nhập local — tự giải captcha trên cửa sổ Chrome vừa mở</h3><div id=st>Đang khởi động...</div>
<button id=stop style="margin:0 0 8px;padding:6px 14px;background:#c33;color:#fff;border:0;border-radius:6px;cursor:pointer">⏹ Dừng</button>
<div id=ready style="display:none;background:#1b1b2e;border:1px solid #7c7cff;border-radius:8px;padding:12px;margin-bottom:10px">
<b id=rname></b> — Chrome đang mở, hãy tự thử tạo video trên cửa sổ đó.
<textarea id=rjson readonly rows=3 style="width:100%;margin:8px 0;background:#000;color:#9c9;border:1px solid #333;font:11px monospace"></textarea>
<button id=cjson>📋 Copy cookie JSON</button>
<button id=vok style="background:#2a7;color:#fff">✅ Tạo được video — nạp Pool</button>
<button id=vfail style="background:#a52;color:#fff">🖼️ Không tạo được video — nạp Pool (chỉ tạo ảnh)</button></div>
<div id=bar><i></i></div><pre id=log></pre>
<script>
(async()=>{
const $=s=>document.querySelector(s), log=$("#log");
let cfg; try{cfg=JSON.parse(decodeURIComponent(escape(atob(location.hash.slice(1)))))}catch(e){}
history.replaceState(null,"",location.pathname);
if(!cfg){$("#st").textContent="Mở trang này từ nút 'Đăng nhập local' trên dashboard.";return}
$("#stop").onclick=async()=>{await fetch("/stop",{method:"POST"});$("#st").textContent="Đã dừng";add("⏹ Đã bấm Dừng — đóng Chrome và bỏ qua phần còn lại")};
const ans=async r=>{$("#ready").style.display="none";await fetch("/confirm",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({result:r})})};
$("#vok").onclick=()=>ans("ok");$("#vfail").onclick=()=>ans("fail");
$("#cjson").onclick=()=>{$("#rjson").select();navigator.clipboard&&navigator.clipboard.writeText($("#rjson").value)};
const add=m=>{log.textContent+="["+new Date().toLocaleTimeString("vi-VN")+"] "+m+"\n";log.scrollTop=log.scrollHeight};
window.addEventListener("message",e=>{if(e.data&&e.data.museAck)add((e.data.ok?"✅ Đã nạp "+e.data.name+" vào Pool":"❌ Không nạp được "+e.data.name+": "+e.data.error))});
const r=await fetch("/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(cfg)});
const rd=r.body.getReader(),dec=new TextDecoder();let buf="";
for(;;){const{done,value}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});
 const bl=buf.split("\n\n");buf=bl.pop();
 for(const b of bl)for(const l of b.split("\n")){if(!l.startsWith("data: "))continue;
  const ev=JSON.parse(l.slice(6));if(ev.message)add(ev.message);
  if(ev.status=="READY"){$("#rname").textContent=ev.data.name;$("#rjson").value=JSON.stringify(ev.data.cookies);$("#ready").style.display="block";window._rd=ev.data}
  if(ev.status=="COOKIE"){if(window.opener)window.opener.postMessage({museLocal:1,...ev.data},cfg.target);else add("⚠️ Mất liên kết với dashboard — mở lại từ nút trên dashboard.")}
  if(ev.progress){$("#bar i").style.width=Math.round((ev.progress.current||0)/(ev.progress.total||1)*100)+"%";
   if(ev.status=="ACCOUNT_START")$("#st").textContent="Đang xử lý: "+(ev.progress.email||"")}
  if(ev.status=="ALL_DONE")$("#st").textContent="Hoàn thành! Tải lại dashboard để thấy tài khoản."}}
})();
</script>"""


async def handle_page(request):
    return web.Response(text=PAGE, content_type="text/html")


async def handle_options(request):
    return web.Response(status=204, headers=CORS)


async def handle_ping(request):
    return web.json_response({"ok": True}, headers=CORS)


def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8771)
    a = ap.parse_args()
    app = web.Application()
    app.router.add_route("OPTIONS", "/{tail:.*}", handle_options)
    app.router.add_get("/", handle_page)
    app.router.add_get("/ping", handle_ping)
    app.router.add_post("/login", handle_login)
    app.router.add_post("/stop", handle_stop)
    app.router.add_post("/confirm", handle_confirm)
    print(f"Local login server: http://127.0.0.1:{a.port}  (để cửa sổ này mở, rồi bấm nút 'Đăng nhập local' trên dashboard)")
    web.run_app(app, host="127.0.0.1", port=a.port, print=None)


if __name__ == "__main__":
    main()
