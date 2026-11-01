import sys
from pathlib import Path

p = Path(r"D:\hermes-main\hermes-main\scripts\build_full_app_fleet.py")
content = p.read_text(encoding="utf-8")

old_storage = """        const storedPool = localStorage.getItem('hermes_pool_accounts');
        if (storedPool) {{
          const parsedP = JSON.parse(storedPool);
          if (Array.isArray(parsedP) && parsedP.length > 0) POOL_ACCOUNTS = parsedP;
        }}"""

new_storage = """        // Xóa cache cũ để luôn dùng dữ liệu chu kỳ đặt lại chuẩn xác từ Sever
        localStorage.removeItem('hermes_pool_accounts');"""

old_init = """    // Init
    window.addEventListener('DOMContentLoaded', () => {{
      loadFleetFromStorage();
      renderAssistantsFleet();
      renderVirtualBots();
      renderPoolAccounts();
      selectGroup('{first_gid}');
      renderOverviewCards();
      renderRentalPlatform();
      lucide.createIcons();
    }});"""

new_init = """    async function loadLivePoolAccounts() {{
      try {{
        const resp = await fetch('/api/pool');
        if (resp.ok) {{
          const data = await resp.json();
          if (data && Array.isArray(data.accounts) && data.accounts.length > 0) {{
            POOL_ACCOUNTS = data.accounts;
            renderPoolAccounts();
          }}
        }}
      }} catch (e) {{}}
    }}

    // Init
    window.addEventListener('DOMContentLoaded', () => {{
      loadFleetFromStorage();
      renderAssistantsFleet();
      renderVirtualBots();
      renderPoolAccounts();
      selectGroup('{first_gid}');
      renderOverviewCards();
      renderRentalPlatform();
      lucide.createIcons();
      loadLivePoolAccounts();
      setInterval(loadLivePoolAccounts, 30000);
    }});"""

norm_content = content.replace("\r\n", "\n")
norm_old_storage = old_storage.replace("\r\n", "\n")
norm_new_storage = new_storage.replace("\r\n", "\n")
norm_old_init = old_init.replace("\r\n", "\n")
norm_new_init = new_init.replace("\r\n", "\n")

if norm_old_storage in norm_content and norm_old_init in norm_content:
    norm_content = norm_content.replace(norm_old_storage, norm_new_storage)
    norm_content = norm_content.replace(norm_old_init, norm_new_init)
    p.write_text(norm_content, encoding="utf-8")
    print("SUCCESS: Updated build_full_app_fleet.py for live pool sync!")
else:
    print("ERROR: text not found in build_full_app_fleet.py")
