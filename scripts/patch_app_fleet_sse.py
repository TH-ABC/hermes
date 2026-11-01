import sys
from pathlib import Path

p = Path(r"D:\hermes-main\hermes-main\scripts\build_full_app_fleet.py")
content = p.read_text(encoding="utf-8")

old_code = """      try {{
        const resp = await fetch('/api/pool/auto-extract', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            accounts_raw: raw,
            skip_ready: document.getElementById('autoAccSkip').checked,
            overwrite: document.getElementById('autoAccOverwrite').checked
          }})
        }});

        const resData = await resp.json();
        if (resData.ok) {{
          bar.style.width = '100%';
          statusTxt.innerText = '✅ Hoàn thành trích xuất!';
          logs.textContent += '✅ ' + (resData.message || 'Đã nạp cookie thành công vào Pool!') + '\\\\n';
          alert('✅ Đã nạp thành công tài khoản vào Pool AI!');
          window.location.reload();
        }} else {{
          statusTxt.innerText = '⚠️ Lỗi: ' + (resData.error || 'Thất bại');
          logs.textContent += '❌ Lỗi: ' + (resData.error || 'Không rõ lỗi') + '\\\\n';
        }}
      }} catch (err) {{
        statusTxt.innerText = 'Lỗi kết nối';
        logs.textContent += '❌ Lỗi mạng: ' + err.message + '\\\\n';
      }} finally {{"""

new_code = """      try {{
        const resp = await fetch('/api/pool/auto-extract', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            accounts_raw: raw,
            skip_ready: document.getElementById('autoAccSkip').checked,
            overwrite: document.getElementById('autoAccOverwrite').checked
          }})
        }});

        if (!resp.ok) {{
          const errData = await resp.json().catch(() => ({{}}));
          throw new Error(errData.error || ('HTTP ' + resp.status));
        }}

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {{
          const {{ done, value }} = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, {{ stream: true }});
          const blocks = buffer.split('\\\\n\\\\n');
          buffer = blocks.pop();

          for (const block of blocks) {{
            for (const line of block.split('\\\\n')) {{
              if (!line.startsWith('data: ')) continue;
              try {{
                const ev = JSON.parse(line.slice(6).trim());
                if (ev.message) {{
                  const d = new Date().toLocaleTimeString('vi-VN');
                  logs.textContent += `[${{d}}] ${{ev.message}}\\\\n`;
                  logs.scrollTop = logs.scrollHeight;
                }}
                if (ev.progress) {{
                  const cur = ev.progress.current || 0, tot = ev.progress.total || 1;
                  ratio.textContent = `${{cur}}/${{tot}}`;
                  bar.style.width = Math.round((cur / tot) * 100) + '%';
                  statusTxt.innerText = `Đang xử lý: ${{ev.progress.email || ''}}`;
                }}
                if (ev.status === 'ALL_DONE') {{
                  statusTxt.innerText = '✅ Hoàn thành trích xuất!';
                  bar.style.width = '100%';
                  setTimeout(() => {{ renderPoolAccounts(); }}, 1200);
                }}
              }} catch (e) {{}}
            }}
          }}
        }}
      }} catch (err) {{
        statusTxt.innerText = 'Lỗi: ' + err.message;
        logs.textContent += '❌ Lỗi: ' + err.message + '\\\\n';
      }} finally {{"""

norm_content = content.replace("\r\n", "\n")
norm_old = old_code.replace("\r\n", "\n")
norm_new = new_code.replace("\r\n", "\n")

if norm_old in norm_content:
    norm_content = norm_content.replace(norm_old, norm_new)
    p.write_text(norm_content, encoding="utf-8")
    print("SUCCESS: Patched build_full_app_fleet.py with streaming SSE!")
else:
    print("ERROR: old_code not found in build_full_app_fleet.py")
