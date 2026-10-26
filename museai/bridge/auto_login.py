"""Hotmail/Outlook -> muse.ai auto-login: reads Meta's 6-digit OTP (Microsoft OAuth refresh
token, or Outlook webmail as a fallback), signs in on the pool's own Chromium and returns the
muse.ai cookies. Ported from 3T_Colab/MuseAI. Credentials are used in memory only — never
logged, never echoed back, never written anywhere but the resulting cookies/<name>.json.
"""
import asyncio
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Set, Tuple

ACCOUNT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
# Set when a person is at the screen of a headed browser and will tick any reCAPTCHA.
MANUAL_CAPTCHA = bool(os.environ.get("MUSE_LOGIN_MANUAL"))

# Meta asks some accounts (not all) for a reCAPTCHA after the OTP; fail that account at once instead of
# clicking a greyed-out Continue for ~45s.
CAPTCHA_ERROR = "Meta yêu cầu reCAPTCHA"

_STEALTH_JS = """
// 1. Mask navigator.webdriver
try {
    delete Object.getPrototypeOf(navigator).webdriver;
} catch (e) {}
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true
});

// 2. Realistic window.chrome object
window.chrome = {
    app: {
        isInstalled: false,
        InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
        RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }
    },
    runtime: {
        OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
        OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
        PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
        PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
        PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
        RequestUpdateCheckStatus: { NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' }
    },
    csi: function() {},
    loadTimes: function() {}
};

// 3. WebGL Vendor & Renderer spoofing (Hides Google SwiftShader / llvmpipe on Linux VPS)
const maskWebGL = (proto) => {
    if (!proto || !proto.getParameter) return;
    const origGetParam = proto.getParameter;
    proto.getParameter = function(param) {
        // UNMASKED_VENDOR_WEBGL (0x9245 / 37445)
        if (param === 37445) return 'Google Inc. (Intel)';
        // UNMASKED_RENDERER_WEBGL (0x9246 / 37446)
        if (param === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        // VENDOR (0x1F00 / 7936)
        if (param === 7936) return 'WebKit';
        // RENDERER (0x1F01 / 7937)
        if (param === 7937) return 'WebKit WebGL';
        return origGetParam.apply(this, arguments);
    };
};
if (window.WebGLRenderingContext) maskWebGL(WebGLRenderingContext.prototype);
if (window.WebGL2RenderingContext) maskWebGL(WebGL2RenderingContext.prototype);

// 4. Realistic navigator.plugins & mimeTypes
function createPlugin(name, description, filename) {
    const p = Object.create(Plugin.prototype);
    Object.defineProperties(p, {
        name: { value: name, enumerable: true },
        description: { value: description, enumerable: true },
        filename: { value: filename, enumerable: true },
        length: { value: 0, enumerable: true }
    });
    return p;
}
const pluginList = [
    createPlugin('PDF Viewer', 'Portable Document Format', 'internal-pdf-viewer'),
    createPlugin('Chrome PDF Viewer', 'Portable Document Format', 'internal-pdf-viewer'),
    createPlugin('Chromium PDF Viewer', 'Portable Document Format', 'internal-pdf-viewer'),
    createPlugin('Microsoft Edge PDF Viewer', 'Portable Document Format', 'internal-pdf-viewer'),
    createPlugin('WebKit built-in PDF', 'Portable Document Format', 'internal-pdf-viewer')
];
const pArr = Object.create(PluginArray.prototype);
pluginList.forEach((p, idx) => {
    Object.defineProperty(pArr, idx, { value: p, enumerable: true });
    Object.defineProperty(pArr, p.name, { value: p, enumerable: false });
});
Object.defineProperty(pArr, 'length', { value: pluginList.length, enumerable: true });
Object.defineProperty(navigator, 'plugins', { get: () => pArr, configurable: true });

// 5. Notification Permissions
if (navigator.permissions && navigator.permissions.query) {
    const origQuery = navigator.permissions.query;
    navigator.permissions.query = (param) => (
        param && param.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission || 'default' })
            : origQuery(param)
    );
}

// 6. Realistic system values
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'], configurable: true });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8, configurable: true });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8, configurable: true });
"""


async def _human_click(page, locator, hover_delay: Tuple[float, float] = (0.4, 0.8)):
    """Simulates a natural, human-like curved mouse trajectory, hover, and click."""
    box = await locator.bounding_box()
    if not box:
        await locator.click()
        return

    pad_x = max(2.0, min(10.0, box["width"] * 0.25))
    pad_y = max(2.0, min(8.0, box["height"] * 0.25))
    dest_x = box["x"] + random.uniform(pad_x, max(pad_x + 1.0, box["width"] - pad_x))
    dest_y = box["y"] + random.uniform(pad_y, max(pad_y + 1.0, box["height"] - pad_y))

    # Move via intermediate curved waypoint
    mid_x = dest_x + random.uniform(-25, 25)
    mid_y = dest_y + random.uniform(-20, 20)
    await page.mouse.move(mid_x, mid_y, steps=random.randint(6, 12))
    await asyncio.sleep(random.uniform(0.04, 0.12))

    # Settle onto target
    await page.mouse.move(dest_x, dest_y, steps=random.randint(8, 16))
    await asyncio.sleep(random.uniform(*hover_delay))
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.08, 0.16))
    await page.mouse.up()

def _get_random_portrait_path() -> Optional[str]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    portraits_dir = os.path.join(base_dir, "assets", "portraits")
    if os.path.exists(portraits_dir):
        files = [os.path.join(portraits_dir, f) for f in os.listdir(portraits_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if files:
            return random.choice(files)
    scratch_img = os.path.join(os.path.dirname(base_dir), "scratch", "sample_portrait.jpg")
    if os.path.exists(scratch_img):
        return scratch_img
    return None


async def _has_recaptcha(page, body_text: str) -> bool:
    """The checkbox lives in a google.com iframe, so the page's own text may not mention it."""
    if "not a robot" in body_text or "recaptcha" in body_text:
        return True
    return any("recaptcha" in (f.url or "") for f in page.frames)


async def _solve_meta_recaptcha(page, ctx, logger=None) -> bool:
    """
    Tự động xử lý và giải reCAPTCHA checkpoint của Meta:
    1. Định vị iframe reCAPTCHA anchor trong page.frames (xử lý cả trường hợp nested).
    2. Kiểm tra xem checkbox đã được tick xanh chưa.
    3. Nếu chưa tick xanh: mô phỏng chuột người dùng click vào checkbox.
    4. Nếu Google mở popup câu đố (bframe):
       - Di chuyển chuột, hover và click nút Audio Challenge.
       - Kiểm tra nếu Google báo 'Try again later / automated queries' -> log cảnh báo và trả về False để xoay IP retry.
       - Tải file âm thanh, chuyển đổi WAV qua ffmpeg, nhận diện giọng nói bằng SpeechRecognition.
       - Gõ kết quả dạng người thật vào '#audio-response' và bấm nút Verify.
    5. Trả về True nếu checkbox đã tích xanh (được xác thực).
    """
    log = logger or (lambda msg, st=None: None)
    
    # 1. Tìm iframe reCAPTCHA anchor trong các frame (kể cả nested iframe)
    anchor_frame = None
    for _ in range(12):
        for fr in page.frames:
            u = fr.url or ""
            if "recaptcha" in u and "anchor" in u and "bframe" not in u:
                anchor_frame = fr
                break
        if anchor_frame:
            break
        await asyncio.sleep(0.5)
        
    if not anchor_frame:
        return False
        
    try:
        # Kiểm tra xem đã tick xanh sẵn chưa
        if await anchor_frame.locator('#recaptcha-anchor[aria-checked="true"], .recaptcha-checkbox-checked').count() > 0:
            return True
            
        chk = anchor_frame.locator('#recaptcha-anchor, .recaptcha-checkbox').first
        try:
            await chk.wait_for(state="visible", timeout=12000)
        except Exception:
            pass

        if await chk.count() > 0 and await chk.is_visible():
            log("Phát hiện checkbox reCAPTCHA ('I'm not a robot') — di chuyển chuột và click...", "STEP_CAPTCHA")
            await _human_click(page, chk, hover_delay=(0.5, 1.0))
            log("Đã click vào ô reCAPTCHA, đang chờ Google xác thực...", "STEP_CAPTCHA")
            
            # Đợi 4 giây kiểm tra xem có được tích xanh luôn không
            for _ in range(5):
                await asyncio.sleep(1)
                if await anchor_frame.locator('#recaptcha-anchor[aria-checked="true"], .recaptcha-checkbox-checked').count() > 0:
                    log("✅ reCAPTCHA đã xác thực thành công (tích xanh)!", "STEP_CAPTCHA")
                    return True

        # 2. Thử giải qua Audio Challenge nếu xuất hiện popup bframe
        bframe = None
        for _ in range(12):
            bframe = next((fr for fr in page.frames if "recaptcha" in (fr.url or "") and "bframe" in (fr.url or "")), None)
            if bframe:
                break
            await asyncio.sleep(0.5)

        if bframe:
            # Human pause to read challenge prompt
            await asyncio.sleep(random.uniform(1.2, 2.0))
            audio_btn = bframe.locator('#recaptcha-audio-button').first
            try:
                await audio_btn.wait_for(state="visible", timeout=8000)
            except Exception:
                pass

            if await audio_btn.count() > 0 and await audio_btn.is_visible():
                log("Màn hình thử thách hiện ra — di chuyển chuột bấm Audio Challenge...", "STEP_CAPTCHA")
                await _human_click(page, audio_btn, hover_delay=(0.6, 1.2))
                await asyncio.sleep(2.5)
                
                bframe_text = await bframe.inner_text("body")
                if "try again later" in bframe_text.lower() or "automated queries" in bframe_text.lower():
                    log("Google chặn giải âm thanh cho IP này ('automated queries').", "WARN")
                    return False
                
                audio_link = None
                candidates = [
                    '#audio-source',
                    '.rc-audiochallenge-tdownload-link',
                    'a.rc-audiochallenge-download-link',
                    'a[href*="audio.mp3"]',
                    'a[href*="payload"]',
                    'audio source',
                    'audio'
                ]
                for sel in candidates:
                    loc = bframe.locator(sel).first
                    if await loc.count() > 0:
                        src = await loc.get_attribute('src') or await loc.get_attribute('href')
                        if src:
                            audio_link = src
                            break

                if audio_link:
                    log("Đang tải file âm thanh và nhận diện giọng nói...", "STEP_CAPTCHA")
                    resp = await ctx.request.get(audio_link)
                    audio_data = await resp.body()
                    
                    import tempfile
                    import subprocess
                    import shutil
                    
                    mp3_path = None
                    wav_path = None
                    try:
                        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                            tf.write(audio_data)
                            mp3_path = tf.name
                        wav_path = mp3_path.replace(".mp3", ".wav")
                        
                        ffmpeg_paths = [
                            "/home/muse/.cache/ms-playwright/ffmpeg-1011/ffmpeg-linux",
                            "/usr/local/bin/ffmpeg",
                            "/usr/bin/ffmpeg",
                            "ffmpeg"
                        ]
                        ffmpeg_bin = shutil.which("ffmpeg") or next((p for p in ffmpeg_paths if os.path.exists(p)), "ffmpeg")
                        subprocess.run([ffmpeg_bin, "-y", "-i", mp3_path, "-ar", "16000", "-ac", "1", wav_path],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                        
                        import speech_recognition as sr
                        r = sr.Recognizer()
                        with sr.AudioFile(wav_path) as source:
                            audio = r.record(source)
                        text = r.recognize_google(audio)
                        if text:
                            log(f"Đã nhận diện âm thanh: '{text}' — đang điền và xác nhận...", "STEP_CAPTCHA")
                            resp_inp = bframe.locator('#audio-response').first
                            await _human_click(page, resp_inp, hover_delay=(0.2, 0.4))
                            await resp_inp.press_sequentially(text, delay=random.randint(50, 110))
                            await asyncio.sleep(random.uniform(0.4, 0.8))
                            verify_btn = bframe.locator('#recaptcha-verify-button').first
                            await _human_click(page, verify_btn, hover_delay=(0.3, 0.6))
                            await asyncio.sleep(2.5)
                    except Exception as ex:
                        log(f"Audio Challenge chưa giải được ({ex}), tiếp tục chờ...", "WARN")
                    finally:
                        for p in [mp3_path, wav_path]:
                            if p and os.path.exists(p):
                                try:
                                    os.remove(p)
                                except Exception:
                                    pass
                                    
                    if await anchor_frame.locator('#recaptcha-anchor[aria-checked="true"], .recaptcha-checkbox-checked').count() > 0:
                        log("✅ reCAPTCHA đã giải thành công qua Audio Challenge!", "STEP_CAPTCHA")
                        return True
    except Exception as e:
        log(f"Lỗi khi xử lý reCAPTCHA: {e}", "WARN")
        
    try:
        return await anchor_frame.locator('#recaptcha-anchor[aria-checked="true"], .recaptcha-checkbox-checked').count() > 0
    except Exception:
        return False
DEFAULT_CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
MICROSOFT_MESSAGES_URL = "https://outlook.office.com/api/v2.0/me/messages?$top=10"
_LOGIN_ENTRY_URLS = ("https://muse.ai/?return_to=%2F", "https://muse.ai/business", "https://muse.ai/")
_EMAIL_INPUT = 'input[aria-label="Mobile number or email"], input[placeholder*="email" i], input'
MICROSOFT_JUNK_URL ="https://outlook.office.com/api/v2.0/me/MailFolders/JunkEmail/messages?$top=10"


# React-controlled inputs ignore a plain .value write: reset the value tracker, set through the
# native setter and fire input/change. Values travel as an evaluate() ARGUMENT, never spliced
# into the script text.
_SET_INPUT_JS = """({value, otp}) => {
  const inps = Array.from(document.querySelectorAll('input:not([type="hidden"])'));
  const inp = otp
    ? (inps.find(i => (i.getAttribute('aria-label') || '').includes('6-digit') || i.maxLength === 6) || inps[0])
    : document.querySelector('input');
  if (!inp) return;
  inp.focus();
  const tracker = inp._valueTracker;
  if (tracker) tracker.setValue('');
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
  if (setter) setter.call(inp, value);
  inp.dispatchEvent(otp
    ? new InputEvent('input', {bubbles: true, cancelable: true, inputType: 'insertText', data: value})
    : new Event('input', {bubbles: true}));
  inp.dispatchEvent(new Event('change', {bubbles: true}));
}"""


def is_probable_token(val: str) -> bool:
    """Detects whether a string is a Microsoft OAuth refresh token vs a plain password."""
    if not val:
        return False
    val = val.strip()
    return len(val) >= 50


def format_playwright_proxy(proxy_str: str) -> Optional[Dict[str, str]]:
    """Formats proxy string into Playwright proxy dictionary."""
    if not proxy_str:
        return None
    raw = proxy_str.strip()
    if raw.startswith(("http://", "https://", "socks5://", "socks4://")):
        parsed = urllib.parse.urlparse(raw)
        server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
        cfg = {"server": server}
        if parsed.username:
            cfg["username"] = parsed.username
        if parsed.password:
            cfg["password"] = parsed.password
        return cfg
    parts = raw.split(":")
    if len(parts) == 2:
        return {"server": f"http://{parts[0]}:{parts[1]}"}
    elif len(parts) == 4:
        return {"server": f"http://{parts[0]}:{parts[1]}", "username": parts[2], "password": parts[3]}
    return {"server": raw}


def sanitize_account_name(email: str) -> str:
    """Generates a safe account name conforming to ACCOUNT_NAME_RE."""
    prefix = email.split("@")[0].strip()
    clean = re.sub(r"[^A-Za-z0-9_-]", "_", prefix)
    clean = clean.strip("_") or "acc"
    return clean[:40]


def parse_account_string(raw: str) -> Dict[str, Any]:
    """
    Intelligently parses account string:
    - email|password|refreshToken|client_id
    - email|password|refreshToken
    - email|refreshToken|client_id
    - email|refreshToken
    - email|password
    """
    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("Chuỗi tài khoản rỗng")

    delimiter = "|"
    if "|" in cleaned:
        delimiter = "|"
    elif "\t" in cleaned:
        delimiter = "\t"
    elif cleaned.count(":") >= 2 and "@" in cleaned.split(":")[0]:
        delimiter = ":"

    parts = [p.strip() for p in cleaned.split(delimiter) if p.strip()]
    if not parts:
        raise ValueError("Không thể phân tích dòng tài khoản")

    email = parts[0].strip()
    if "@" not in email:
        raise ValueError("Email không hợp lệ (định dạng: email|mật_khẩu[|refresh_token|client_id])")

    password = ""
    refresh_token = None
    client_id = DEFAULT_CLIENT_ID

    if len(parts) == 1:
        pass
    elif len(parts) == 2:
        val = parts[1]
        if is_probable_token(val):
            refresh_token = val
        else:
            password = val
    elif len(parts) == 3:
        p1, p2 = parts[1], parts[2]
        if is_probable_token(p1):
            refresh_token = p1
            client_id = p2 or DEFAULT_CLIENT_ID
        elif is_probable_token(p2):
            password = p1
            refresh_token = p2
        else:
            password = p1
            if len(p2) == 36 and "-" in p2:
                client_id = p2
    else:  # >= 4 parts
        p1, p2, p3 = parts[1], parts[2], parts[3]
        if is_probable_token(p2):
            password = p1
            refresh_token = p2
            client_id = p3 or DEFAULT_CLIENT_ID
        elif is_probable_token(p1):
            refresh_token = p1
            client_id = p2 or DEFAULT_CLIENT_ID
        else:
            password = p1
            for p in parts[2:]:
                if is_probable_token(p):
                    refresh_token = p
                    break

    proxy = None
    for p in parts[1:]:
        if p.startswith(("http://", "https://", "socks5://", "socks4://")):
            proxy = p
            break
        elif (p.count(":") in (1, 3)) and not is_probable_token(p) and not (len(p) == 36 and "-" in p):
            proxy = p
            break

    name = sanitize_account_name(email)

    return {
        "email": email,
        "password": password,
        "refresh_token": refresh_token,
        "client_id": client_id,
        "name": name,
        "proxy": proxy,
        "has_oauth": bool(refresh_token and len(refresh_token) > 30),
    }


def parse_batch_accounts(text: str) -> List[Dict[str, Any]]:
    results = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            acc = parse_account_string(line)
            results.append(acc)
        except Exception:
            continue
    return results


def _get_access_token_sync(refresh_token: str, client_id: str = DEFAULT_CLIENT_ID) -> str:
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "https://outlook.office.com/Mail.ReadWrite offline_access"
    }).encode("utf-8")
    req = urllib.request.Request(MICROSOFT_TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        res = urllib.request.urlopen(req, timeout=15)
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8"))
            why = (err.get("error_description") or err.get("error") or "").split("\r\n")[0][:160]
        except Exception:
            why = ""
        raise ValueError(f"Microsoft từ chối refresh token (HTTP {e.code}): {why or 'token hết hạn/bị thu hồi hoặc sai client_id'}") from None
    body = json.loads(res.read().decode("utf-8"))
    token = body.get("access_token")
    if not token:
        raise ValueError("Không lấy được access token từ Microsoft OAuth.")
    return token


def _get_recent_message_ids_sync(refresh_token: str, client_id: str = DEFAULT_CLIENT_ID) -> Set[str]:
    try:
        access_token = _get_access_token_sync(refresh_token, client_id)
        req = urllib.request.Request(MICROSOFT_MESSAGES_URL, headers={"Authorization": f"Bearer {access_token}"})
        res = urllib.request.urlopen(req, timeout=10)
        body = json.loads(res.read().decode("utf-8"))
        messages = body.get("value", [])
        return {msg.get("Id") for msg in messages if msg.get("Id")}
    except Exception:
        return set()


def _wait_for_meta_otp_sync(
    refresh_token: str,
    client_id: str = DEFAULT_CLIENT_ID,
    timeout_seconds: int = 40,
    interval_seconds: int = 3,
    min_datetime: Optional[datetime] = None,
    ignore_ids: Optional[Set[str]] = None
) -> Optional[str]:
    access_token = _get_access_token_sync(refresh_token, client_id)
    start_time = time.time()
    ignore_ids = ignore_ids or set()

    while time.time() - start_time < timeout_seconds:
        try:
            messages = []
            for target_url in [MICROSOFT_MESSAGES_URL, MICROSOFT_JUNK_URL]:
                try:
                    req = urllib.request.Request(target_url, headers={"Authorization": f"Bearer {access_token}"})
                    res = urllib.request.urlopen(req, timeout=8)
                    data = json.loads(res.read().decode("utf-8")).get("value", [])
                    messages.extend(data)
                except Exception:
                    pass

            for msg in messages:
                msg_id = msg.get("Id")
                if msg_id and msg_id in ignore_ids:
                    continue

                if min_datetime:
                    rec_str = msg.get("ReceivedDateTime") or msg.get("CreatedDateTime")
                    if rec_str:
                        try:
                            rec_dt = datetime.fromisoformat(rec_str.replace("Z", "+00:00"))
                            if rec_dt < min_datetime - timedelta(seconds=20):
                                continue
                        except Exception:
                            pass

                subject = msg.get("Subject", "")
                preview = msg.get("BodyPreview", "")
                sender = msg.get("From", {}).get("EmailAddress", {}).get("Address", "")

                is_meta = (
                    "meta" in sender.lower() or
                    any(k in subject.lower() or k in preview.lower() for k in [
                        "meta", "muse", "security code", "verification code",
                        "confirm your email", "mã xác nhận", "mã đăng nhập", "đăng nhập"
                    ])
                )
                if is_meta:
                    code_match = re.search(r"\b(\d{6})\b", subject) or re.search(r"\b(\d{6})\b", preview)
                    if code_match:
                        return code_match.group(1)
        except Exception:
            pass
        time.sleep(interval_seconds)
    return None


async def fetch_webmail_otp_async(browser, email: str, password: str, timeout_seconds: int = 50, logger=None) -> Optional[str]:
    """Automates login.live.com to read OTP when no OAuth token is available."""
    log = logger or (lambda m, s=None: None)
    log(f"Đang mở phiên duyệt web Outlook để đăng nhập {email}...", "STEP_WEBMAIL")
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    page = await ctx.new_page()
    try:
        await page.goto("https://login.live.com/", timeout=25000)
        
        # Email
        email_inp = await page.wait_for_selector('input[type="email"], input[name="loginfmt"]', timeout=15000)
        await email_inp.fill(email)
        await page.locator('input[type="submit"], button[type="submit"], #idSIButton9').first.click()
        await asyncio.sleep(2)
        
        # Password
        pwd_inp = await page.wait_for_selector('input[type="password"], input[name="passwd"]', timeout=15000)
        await pwd_inp.fill(password)
        await page.locator('input[type="submit"], button[type="submit"], #idSIButton9').first.click()
        await asyncio.sleep(3)
        
        # Intermediate prompts (terms, stay signed in)
        for _ in range(5):
            body_text = (await page.inner_text("body")).lower()
            if "updating our terms" in body_text or "services agreement" in body_text:
                nxt = page.locator('input[type="submit"], button[type="submit"], button:has-text("Next"), input[value="Next"]').first
                if await nxt.count() > 0:
                    await nxt.click()
                    await asyncio.sleep(2)
            elif "stay signed in" in body_text or "duy trì đăng nhập" in body_text:
                btn_yes = page.locator('#idSIButton9, input[type="submit"], button[type="submit"]').first
                if await btn_yes.count() > 0:
                    await btn_yes.click()
                    await asyncio.sleep(2)
            elif "outlook" in page.url or "inbox" in page.url:
                break
            await asyncio.sleep(1)

        # Inbox
        log("Mở hòm thư Outlook Web để đọc mã OTP...", "STEP_WEBMAIL_INBOX")
        await page.goto("https://outlook.live.com/mail/0/inbox", timeout=30000)
        await asyncio.sleep(4)

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            body_text = await page.inner_text("body")
            if any(k in body_text.lower() for k in ["meta", "muse", "security code", "mã"]):
                matches = re.findall(r"\b(\d{6})\b", body_text)
                if matches:
                    return matches[0]
            await asyncio.sleep(3)
            try:
                ref_btn = page.locator('button[aria-label*="Refresh" i], button[aria-label*="Đồng bộ" i]').first
                if await ref_btn.count() > 0:
                    await ref_btn.click()
            except Exception:
                pass
        return None
    except Exception as e:
        log(f"Lỗi đọc Webmail: {e}", "WARN")
        return None
    finally:
        try:
            await ctx.close()
        except Exception:
            pass


async def extract_account_cookies(browser, raw_account: str, logger=None, context=None, hold=None) -> Dict[str, Any]:
    """
    Fully automated login & cookie extraction on a running Playwright browser instance.
    Returns: {"ok": True, "name": ..., "email": ..., "cookies": [...], "hatch_sess": ...}
    hold: optional async callback(result) awaited once logged in, before the context is closed — lets a
    person use the live browser (e.g. test video generation) first.
    """
    log = logger or (lambda msg, st=None: print(f"[{st or 'INFO'}] {msg}"))
    email = "unknown"
    name = "unknown"
    ctx = None
    own_ctx = context is None  # a caller-supplied context (GoLogin profile) is closed by its owner

    try:
        acc = parse_account_string(raw_account)
        email = acc["email"]
        name = acc["name"]
        ctx_kwargs: Dict[str, Any] = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800},
            "locale": "en-US",
            "timezone_id": "Asia/Ho_Chi_Minh",
        }
        if acc.get("proxy"):
            log(f"Tài khoản cấu hình proxy riêng: {acc['proxy']}", "PROXY")
            pw_proxy = format_playwright_proxy(acc["proxy"])
            if pw_proxy:
                ctx_kwargs["proxy"] = pw_proxy
                ctx_kwargs["timezone_id"] = "America/New_York"

        if own_ctx:
            ctx = await browser.new_context(**ctx_kwargs)
            await ctx.add_init_script(_STEALTH_JS)
        else:
            ctx = context  # GoLogin/Orbita profile brings its own fingerprint: no stealth patches
            await ctx.clear_cookies()
        page = await ctx.new_page()

        # 1. Open Muse.ai. The bare root now 307s a signed-out visitor to auth.muse.ai/aymh/, a
        # Meta error page with no form; any path carrying ?return_to (or /business) still renders
        # the "Mobile number or email" login card — try those first.
        log(f"Đang mở trang đăng nhập muse.ai...", "STEP_OPEN")
        for entry in _LOGIN_ENTRY_URLS:
            try:
                await page.goto(entry, timeout=25000)
                await page.locator(_EMAIL_INPUT).first.wait_for(state="visible", timeout=8000)
                break
            except Exception:
                continue
        await asyncio.sleep(1)

        # Snapshot existing message IDs
        pre_msg_ids = set()
        if acc["has_oauth"]:
            try:
                pre_msg_ids = await asyncio.to_thread(_get_recent_message_ids_sync, acc["refresh_token"], acc["client_id"])
            except Exception:
                pass

        # 2. Fill Email
        log(f"Điền email {email} và gửi yêu cầu đăng nhập...", "STEP_EMAIL")
        inp = page.locator(_EMAIL_INPUT).first
        await inp.wait_for(state="visible", timeout=15000)
        await inp.fill(email)

        await page.evaluate(_SET_INPUT_JS, {"value": email, "otp": False})
        await asyncio.sleep(0.5)

        req_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        btn = page.locator('form button[type="submit"], button:has-text("Continue"), button:has-text("Log in")').first
        await btn.click()
        try:
            await inp.press("Enter")
        except Exception:
            pass

        # 3. Wait for OTP screen
        log("Chờ màn hình nhập mã xác thực OTP...", "STEP_WAIT_OTP")
        otp_loc = page.locator('input[aria-label*="code" i], input[placeholder*="code" i], input[aria-label*="digit" i], input').first
        try:
            await otp_loc.wait_for(state="visible", timeout=15000)
        except Exception:
            if await btn.count() > 0:
                await btn.click()
                await otp_loc.wait_for(state="visible", timeout=15000)

        # 4. Fetch OTP
        otp_code = None
        if acc["has_oauth"]:
            log("Đang gọi Microsoft Graph API lấy mã OTP...", "STEP_FETCH_OTP")
            otp_code = await asyncio.to_thread(
                _wait_for_meta_otp_sync,
                acc["refresh_token"],
                acc["client_id"],
                timeout_seconds=35,
                interval_seconds=3,
                min_datetime=req_time,
                ignore_ids=pre_msg_ids
            )
        elif acc["password"]:
            log("Không có OAuth token. Tự động mở Webmail đọc thư...", "STEP_FETCH_OTP")
            otp_code = await fetch_webmail_otp_async(browser, email, acc["password"], timeout_seconds=45, logger=log)

        if not otp_code:
            raise TimeoutError(f"Không nhận được mã OTP xác thực cho {email} sau thời gian chờ.")

        log("Đã nhận mã OTP, đang tự động nhập...", "STEP_SUBMIT_OTP")

        # 5. Fill OTP into Muse
        await otp_loc.fill(otp_code)
        await page.evaluate(_SET_INPUT_JS, {"value": otp_code, "otp": True})
        await asyncio.sleep(0.5)

        cf_btn = page.locator('button:has-text("Next"), form button[type="submit"], button:has-text("Confirm"), button:has-text("Continue"), button:has-text("Tiếp tục"), button:has-text("Xác nhận")').first
        if await cf_btn.count() > 0:
            try:
                await cf_btn.click(timeout=3000)
            except Exception:
                pass
        try:
            await otp_loc.press("Enter")
        except Exception:
            pass

        # 6. Wait for session & handle onboarding
        log("Đang chờ phiên đăng nhập hoàn tất...", "STEP_WAIT_LOGIN")
        logged_in = False
        hatch_sess_val = None

        captcha_attempted = False
        captcha_blocked = False
        selfie_attempted = False

        for i in range(240 if MANUAL_CAPTCHA else 45):
            await asyncio.sleep(1)
            cookies = await ctx.cookies(["https://muse.ai", "https://auth.meta.com"])
            hatch_cookie = next((c for c in cookies if c.get("name") == "hatch_sess"), None)

            body_text = (await page.inner_text("body")).lower()

            # Xử lý trường hợp Meta báo "We couldn't complete that request. Try again."
            if "couldn't complete that request" in body_text or "we couldn't complete that request" in body_text:
                if i % 3 == 0:
                    log("Meta báo lỗi 'We couldn't complete that request' — đang thử bấm lại Next...", "WARN")
                    nxt = page.locator('button:has-text("Next"), form button[type="submit"], button:has-text("Continue")').first
                    if await nxt.count() > 0:
                        try:
                            await nxt.click(timeout=3000)
                        except Exception:
                            pass

            # Stage 1: Màn hình ban đầu "Confirm you're human to use your account" có nút Continue bật sẵn
            if "confirm you're human" in body_text and not (await _has_recaptcha(page, body_text)):
                cp_btn = page.locator('div[role="button"]:has-text("Continue"), button:has-text("Continue"), [role="button"]:has-text("Continue")').first
                if await cp_btn.count() > 0:
                    is_dis = await cp_btn.get_attribute("aria-disabled")
                    if is_dis != "true" and not (await cp_btn.is_disabled()):
                        log("Meta yêu cầu xác nhận không phải robot — bấm Continue...", "STEP_CHECKPOINT")
                        try:
                            await _human_click(page, cp_btn, hover_delay=(0.3, 0.6))
                        except Exception:
                            try:
                                await cp_btn.click(timeout=3000)
                            except Exception:
                                pass
                        await asyncio.sleep(2)

            # Stage 2: Meta checkpoint reCAPTCHA: tự động giải reCAPTCHA & bấm Continue
            if MANUAL_CAPTCHA and (await _has_recaptcha(page, body_text)):
                # A person is at the headed window: leave the captcha (and its Continue button) to them.
                if i % 15 == 0:
                    log("⚠️ Gặp reCAPTCHA — hãy tự giải và bấm Continue trên cửa sổ Chrome vừa mở...", "STEP_CAPTCHA")
            elif (await _has_recaptcha(page, body_text)) and not captcha_attempted:
                captcha_attempted = True
                solved = await _solve_meta_recaptcha(page, ctx, logger=log)
                if solved:
                    cp_btn = page.locator('div[role="button"]:has-text("Continue"), button:has-text("Continue"), [role="button"]:has-text("Continue")').first
                    for _ in range(8):
                        if await cp_btn.count() > 0:
                            is_dis = await cp_btn.get_attribute("aria-disabled")
                            if is_dis != "true" and not (await cp_btn.is_disabled()):
                                log("reCAPTCHA đã xác thực thành công, đang bấm Continue...", "STEP_CHECKPOINT")
                                try:
                                    await _human_click(page, cp_btn, hover_delay=(0.3, 0.6))
                                except Exception:
                                    try:
                                        await cp_btn.click(timeout=3000)
                                    except Exception:
                                        pass
                                break
                        await asyncio.sleep(1)
                else:
                    captcha_blocked = True
                    if not MANUAL_CAPTCHA:
                        log("Không tự động vượt qua được reCAPTCHA checkpoint.", "WARN")
                    else:
                        log("Đang chờ bạn tick reCAPTCHA trên cửa sổ trình duyệt...", "STEP_CAPTCHA")

            # Meta checkpoint "Upload a verification selfie"
            if ("upload a verification selfie" in body_text or "verification selfie" in body_text) and not selfie_attempted:
                selfie_attempted = True
                log("Meta yêu cầu tải ảnh selfie xác thực khuôn mặt — đang tự động tải ảnh chân dung...", "STEP_CHECKPOINT")
                file_inps = await page.locator('input[type="file"]').all()
                portrait_path = _get_random_portrait_path()

                if len(file_inps) == 0:
                    nxt_btn = page.locator('button:has-text("Continue"), div[role="button"]:has-text("Continue"), button:has-text("Next"), div[role="button"]:has-text("Next"), button:has-text("Upload"), button:has-text("Take")').first
                    if await nxt_btn.count() > 0:
                        try:
                            await _human_click(page, nxt_btn)
                            await asyncio.sleep(2)
                            file_inps = await page.locator('input[type="file"]').all()
                        except Exception:
                            pass

                if len(file_inps) > 0 and portrait_path:
                    log(f"Đã chọn ảnh chân dung ({os.path.basename(portrait_path)}), đang tải lên form xác thực...", "STEP_CHECKPOINT")
                    await file_inps[0].set_input_files(portrait_path)
                    await asyncio.sleep(2)

                    sub = page.locator('div[role="button"]:has-text("Continue"), button:has-text("Continue"), [role="button"]:has-text("Continue"), button:has-text("Submit"), div[role="button"]:has-text("Submit"), div[role="button"]:has-text("Confirm")').first
                    for _ in range(8):
                        if await sub.count() > 0:
                            is_dis = await sub.get_attribute("aria-disabled")
                            if is_dis != "true" and not (await sub.is_disabled()):
                                log("Đang bấm Continue gửi ảnh selfie cho Meta...", "STEP_CHECKPOINT")
                                try:
                                    await _human_click(page, sub)
                                except Exception:
                                    try:
                                        await sub.click(timeout=3000)
                                    except Exception:
                                        pass
                                log("Đang chờ Meta xử lý và xác thực ảnh selfie đã gửi...", "STEP_CHECKPOINT")
                                await asyncio.sleep(6)
                                break
                        await asyncio.sleep(1)

            # Age confirmation
            if "birthday" in body_text or "confirm your age" in body_text or "sinh" in body_text:
                log("Xác nhận độ tuổi (chọn năm sinh 1995)...", "STEP_ONBOARDING")
                sel = page.locator('select').first
                if await sel.count() > 0:
                    try:
                        await sel.select_option(value="1995")
                    except Exception:
                        pass
                b_btn = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Tiếp tục")').first
                if await b_btn.count() > 0:
                    try:
                        await b_btn.click(timeout=3000)
                    except Exception:
                        pass

            if hatch_cookie:
                # hatch_sess is also issued to logged-out visitors, so only accept it once a muse.ai page
                # served with this context carries the VM gatewayUrl (the same test the pool's health check uses).
                try:
                    resp = await ctx.request.get("https://muse.ai/", timeout=15000)
                    html = await resp.body()
                    live = bool(re.search(rb'gatewayUrl.*?wss://', html) or (b"gatewayUrl" in html and b"wss://" in html))
                except Exception:
                    live = False
                if live:
                    logged_in = True
                    hatch_sess_val = hatch_cookie.get("value")
                    log(f"Phiên đăng nhập hợp lệ (có gatewayUrl) sau {i+1}s!", "SUCCESS")
                    break

        if not logged_in or not hatch_sess_val:
            # Leave evidence of what the page showed after the OTP (no cookies / OTP in it).
            detail = ""
            try:
                body = (await page.inner_text("body"))[:300].replace("\n", " | ")
                detail = f" [url={page.url[:80]}; trang hiển thị: {body}]"
                shot_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch")
                os.makedirs(shot_dir, exist_ok=True)
                await page.screenshot(path=os.path.join(shot_dir, f"login_fail_{name}.png"))
            except Exception:
                pass
            if "upload a verification selfie" in body_text or "verification selfie" in body_text:
                raise RuntimeError(
                    "Meta đã tạm khóa tài khoản này và yêu cầu 'Upload a verification selfie' (xác minh khuôn mặt). "
                    "Vui lòng đăng nhập tài khoản này trên trình duyệt thông thường để hoàn tất xác minh khuôn mặt."
                )
            if (await _has_recaptcha(page, body_text)) or captcha_blocked:
                raise RuntimeError(
                    "Meta yêu cầu reCAPTCHA dạng hình ảnh phức tạp — hệ thống đã tự động thử bấm và giải âm thanh nhưng bị Google giới hạn ('automated queries'). "
                    "Vui lòng đăng nhập tài khoản này trên Chrome bằng tay rồi dán cookie (Cookie-Editor → Export JSON) vào ô 'Thêm tài khoản'."
                )
            raise RuntimeError("Không đăng nhập được: phiên chưa hợp lệ sau khi xác nhận OTP." + detail)

        # 7. Extract normalized cookies
        all_raw_cookies = await ctx.cookies(["https://muse.ai", "https://auth.meta.com"])
        muse_cookies = []
        for c in all_raw_cookies:
            dom = c.get("domain") or ""
            if "muse.ai" not in dom:
                continue
            pw_c = {
                "name": c.get("name"),
                "value": str(c.get("value")),
                "domain": dom if dom.startswith(".") else f".{dom}",
                "path": c.get("path") or "/",
                "secure": bool(c.get("secure", True)),
                "httpOnly": bool(c.get("httpOnly", False)),
                "sameSite": c.get("sameSite", "Lax")
            }
            if c.get("expires"):
                pw_c["expires"] = float(c["expires"])
            muse_cookies.append(pw_c)

        result = {
            "ok": True,
            "name": name,
            "email": email,
            "cookies": muse_cookies,
            "cookie_count": len(muse_cookies),
            "hatch_sess": hatch_sess_val
        }
        if hold:
            await hold(result)
        return result

    except Exception as e:
        log(f"Lỗi đăng nhập {email}: {e}", "ERROR")
        return {
            "ok": False,
            "name": name,
            "email": email,
            "error": str(e)
        }
    finally:
        if ctx is not None and own_ctx:
            try:
                await ctx.close()
            except Exception:
                pass
