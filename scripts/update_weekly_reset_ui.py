import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

script_path = Path(r"D:\hermes-main\hermes-main\scripts\build_full_app_fleet.py")
content = script_path.read_text(encoding="utf-8")

# 1. Update Table header
content = content.replace(
    '<th class="py-3 px-4">⚡ Token Còn Lại (Đo Lường)</th>',
    '<th class="py-3 px-4">⚡ Mức Sử Dụng & Token</th>'
)
content = content.replace(
    '<th class="py-3 px-4 text-center">⏱️ Reset Token</th>',
    '<th class="py-3 px-4 text-center">⏱️ Chu Kỳ Đặt Lại (Tuần)</th>'
)

# 2. Update Token metrics calculations in JS
old_metrics = """        // Token metrics
        const tokensTot = acc.tokens_total || 500;
        const tokensUsed = (acc.tokens_used !== undefined) ? acc.tokens_used : ((acc.done || 0) * 10);
        const tokensRem = (acc.tokens_remaining !== undefined) ? acc.tokens_remaining : Math.max(0, tokensTot - tokensUsed);
        const pct = (acc.token_percent !== undefined) ? acc.token_percent : Math.round((tokensRem / tokensTot) * 100);
        const resetStr = acc.reset_time_str || 'Reset sau 17h';
        const resetSec = acc.reset_countdown_seconds || 61200;"""

new_metrics = """        // Token metrics (Chu kỳ đặt lại hàng tuần theo Meta AI Engine)
        const tokensTot = acc.tokens_total || 500;
        const tokensUsed = (acc.tokens_used !== undefined) ? acc.tokens_used : ((acc.done || 0) * 10);
        const tokensRem = (acc.tokens_remaining !== undefined) ? acc.tokens_remaining : Math.max(0, tokensTot - tokensUsed);
        const usedPct = (acc.used_percent !== undefined) ? acc.used_percent : Math.min(100, Math.round((tokensUsed / tokensTot) * 100));
        const remPct = 100 - usedPct;
        const resetStr = acc.reset_time_str || 'Còn 6 ngày 9h';
        const resetLabel = acc.reset_label || 'Đặt lại vào 5 tháng 11';
        const resetSec = acc.reset_countdown_seconds || 550000;
        const bonusTokens = acc.bonus_tokens || '1 Tỷ Token (Vĩnh viễn)';"""

if old_metrics in content:
    content = content.replace(old_metrics, new_metrics)
    print("✅ Replaced old_metrics!")
else:
    print("⚠️ old_metrics not found exactly, searching with regex...")
    pattern = r"// Token metrics\s+const tokensTot.*?\n\s+const resetSec = acc\.reset_countdown_seconds \|\| 61200;"
    content = re.sub(pattern, new_metrics, content, flags=re.DOTALL)
    print("✅ Replaced metrics via regex!")

# 3. Update Token columns in the table row
old_cols = """            <td class="py-3.5 px-4">
              <div class="space-y-1 min-w-[130px]">
                <div class="flex items-center justify-between text-[11px]">
                  <span class="font-black text-slate-800">${{tokensRem.toLocaleString()}} / ${{tokensTot.toLocaleString()}}</span>
                  <span class="font-extrabold ${{pct > 50 ? 'text-emerald-600' : pct > 20 ? 'text-amber-600' : 'text-rose-600'}}">${{pct}}%</span>
                </div>
                <div class="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                  <div class="h-full rounded-full transition-all ${{pct > 50 ? 'bg-emerald-500' : pct > 20 ? 'bg-amber-500' : 'bg-rose-500'}}" style="width: ${{pct}}%"></div>
                </div>
                <span class="text-[10px] text-slate-400 block">Đã dùng: ${{tokensUsed}} Tokens</span>
              </div>
            </td>
            <td class="py-3.5 px-4 text-center">
              <div class="inline-flex flex-col items-center">
                <span class="px-2 py-0.5 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 text-[11px] font-mono font-bold flex items-center space-x-1">
                  <i data-lucide="clock" class="w-3 h-3 text-indigo-600"></i>
                  <span class="pool-countdown-timer" data-reset="${{resetSec}}">${{resetStr}}</span>
                </span>
                <span class="text-[9px] text-slate-400 mt-0.5">Reset: 07:00 hàng ngày</span>
              </div>
            </td>"""

new_cols = """            <td class="py-3.5 px-4">
              <div class="space-y-1.5 min-w-[155px]">
                <div class="flex items-center justify-between text-[11px]">
                  <span class="font-bold text-slate-700">Gói miễn phí:</span>
                  <span class="font-black ${{usedPct === 0 ? 'text-emerald-600' : usedPct < 50 ? 'text-blue-600' : 'text-amber-600'}}">Đã dùng ${{usedPct}}%</span>
                </div>
                <div class="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                  <div class="h-full rounded-full transition-all ${{usedPct < 50 ? 'bg-emerald-500' : usedPct < 80 ? 'bg-amber-500' : 'bg-rose-500'}}" style="width: ${{Math.max(4, usedPct)}}%"></div>
                </div>
                <div class="flex items-center justify-between text-[10px] text-slate-500 pt-0.5">
                  <span>Token bổ sung:</span>
                  <span class="font-bold text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-100">còn 1 tỷ token</span>
                </div>
              </div>
            </td>
            <td class="py-3.5 px-4 text-center">
              <div class="inline-flex flex-col items-center">
                <span class="px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 text-[11px] font-mono font-bold flex items-center space-x-1 shadow-sm">
                  <i data-lucide="calendar-clock" class="w-3.5 h-3.5 text-indigo-600"></i>
                  <span class="pool-countdown-timer" data-reset="${{resetSec}}">${{resetStr}}</span>
                </span>
                <span class="text-[9px] text-slate-500 mt-1 font-semibold">${{resetLabel}}</span>
              </div>
            </td>"""

if old_cols in content:
    content = content.replace(old_cols, new_cols)
    print("✅ Replaced old_cols!")
else:
    print("⚠️ old_cols not found exactly, searching with regex...")
    pattern_cols = r"<td class=\"py-3\.5 px-4\">\s+<div class=\"space-y-1 min-w-\[130px\]\">.*?<span class=\"text-\[9px\] text-slate-400 mt-0\.5\">Reset: 07:00 hàng ngày</span>\s+</div>\s+</td>"
    content = re.sub(pattern_cols, new_cols, content, flags=re.DOTALL)
    print("✅ Replaced cols via regex!")

# 4. Update ticker to handle days format
old_ticker = """    // Countdown Ticker mỗi 60 giây
    setInterval(() => {{
      document.querySelectorAll('.pool-countdown-timer').forEach(el => {{
        let sec = parseInt(el.getAttribute('data-reset') || '0', 10);
        if (sec > 60) {{
          sec -= 60;
          el.setAttribute('data-reset', sec);
          const h = Math.floor(sec / 3600);
          const m = Math.floor((sec % 3600) / 60);
          el.textContent = `Reset sau ${{h}}h ${{m}}m`;
        }} else {{
          el.textContent = 'Đang reset...';
        }}
      }});
    }}, 60000);"""

new_ticker = """    // Countdown Ticker mỗi 60 giây (Chu kỳ đặt lại hàng tuần)
    setInterval(() => {{
      document.querySelectorAll('.pool-countdown-timer').forEach(el => {{
        let sec = parseInt(el.getAttribute('data-reset') || '0', 10);
        if (sec > 60) {{
          sec -= 60;
          el.setAttribute('data-reset', sec);
          const d = Math.floor(sec / 86400);
          const h = Math.floor((sec % 86400) / 3600);
          const m = Math.floor((sec % 3600) / 60);
          el.textContent = d > 0 ? `Còn ${{d}} ngày ${{h}}h` : `Còn ${{h}}h ${{m}}m`;
        }} else {{
          el.textContent = 'Đang đặt lại...';
        }}
      }});
    }}, 60000);"""

if old_ticker in content:
    content = content.replace(old_ticker, new_ticker)
    print("✅ Replaced old_ticker!")
else:
    print("⚠️ old_ticker regex replacement...")
    pattern_ticker = r"// Countdown Ticker mỗi 60 giây\s+setInterval\(\(\) => \{\{.*?el\.textContent = `Reset sau \$\{h\}h \$\{m\}m`;.*?\}, 60000\);"
    content = re.sub(pattern_ticker, new_ticker, content, flags=re.DOTALL)
    print("✅ Replaced ticker via regex!")

script_path.write_text(content, encoding="utf-8")
print("✅ Saved build_full_app_fleet.py successfully!")
