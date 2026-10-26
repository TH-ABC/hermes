"""Telegram alerts for the Muse pool: an account whose session expires (or errors) is reported
once per transition, its recovery once, and a pool-wide "few accounts ready" summary at most hourly.

Env (all optional — without the token+chat id alerts are only printed):
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   bot credentials (never logged)
  MUSE_ALERT_MIN_READY                   summary when fewer accounts than this are ready (default 2)
  MUSE_ALERT_LABEL                       prefix naming this pool in messages (default "Muse pool")
"""

import asyncio
import html
import os
import time
from typing import Optional, Tuple

BAD = ("expired", "error")
SUMMARY_EVERY_S = 3600


class ExpiryAlerts:
    def __init__(self):
        self.token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
        self.chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
        self.min_ready = int(os.environ.get("MUSE_ALERT_MIN_READY", "2") or 2)
        self.label = os.environ.get("MUSE_ALERT_LABEL") or "Muse pool"
        self.bad: dict = {}  # account name -> bad status we already alerted
        self.last_summary = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def transition(self, acc, old: Optional[str], new: str):
        name = html.escape(acc.name)
        if new in BAD and self.bad.get(acc.name) != new:
            self.bad[acc.name] = new
            why = "hết hạn cookie — cần export cookie mới" if new == "expired" else f"lỗi: {html.escape(acc.last_error or '?')[:200]}"
            self._fire(f"⚠️ {self.label}: tài khoản <b>{name}</b> {why}")
        elif new == "ready" and acc.name in self.bad:
            del self.bad[acc.name]
            self._fire(f"✅ {self.label}: tài khoản <b>{name}</b> đã hoạt động lại")

    def forget(self, name: str):
        self.bad.pop(name, None)

    def check_ready(self, accounts):
        ready = sum(1 for a in accounts if a.status == "ready")
        if ready >= min(self.min_ready, len(accounts) or 1):
            return
        if time.time() - self.last_summary < SUMMARY_EVERY_S:
            return
        self.last_summary = time.time()
        bad = [html.escape(a.name) for a in accounts if a.status in BAD]
        self._fire(f"🚨 {self.label}: chỉ còn {ready}/{len(accounts)} tài khoản sẵn sàng"
                   + (f". Hết hạn/lỗi: {', '.join(bad[:20])}" if bad else ""))

    def _fire(self, text: str):
        print(f"[Alert] {text}")
        if not self.enabled:
            return
        try:
            asyncio.get_running_loop().create_task(self.send_now(text))
        except RuntimeError:
            pass

    async def send_now(self, text: str) -> Tuple[bool, str]:
        if not self.enabled:
            return False, "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID chưa cấu hình"
        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as ses:
                async with ses.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                                    json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
                                          "disable_web_page_preview": True}) as r:
                    if r.status == 200:
                        return True, ""
                    return False, f"telegram HTTP {r.status}"
        except Exception as e:
            # never echo the URL (it carries the bot token)
            return False, f"telegram send failed: {type(e).__name__}"
