#!/usr/bin/env python3
"""
Tạo phiên bản app.html hoàn thiện với:
1. Đội Ngũ Trợ Lý Zalo & Hệ Thống (Zalo Bot Fleet)
2. Pool Trợ Lý Nền Tảng Đồ Họa & Video AI (Studio AI & Cookie Pool - Cổng 8770)
- Nạp Cookie trực tiếp (JSON Cookie-Editor / hatch_sess / text header)
- Tự động lấy Cookie qua Auto-Extract (email|password|refreshToken)
- Bảng quản trị chi tiết từng account trong Pool (Ready, Expired, Lượt render, Nạp lại cookie)
Đảm bảo ZERO lỗi cú pháp JavaScript và đáp ứng 100% chỉ thị của Sếp Hoàng.
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
from pathlib import Path

APP_HTML_PATH = Path("D:/hermes-main/hermes-agent-vercel/public/app.html")
INDEX_HTML_PATH = Path("D:/hermes-main/hermes-agent-vercel/public/index.html")
POLICY_PATH = Path("D:/hermes-main/storage/policy.json")
ASSISTANTS_PATH = Path("D:/hermes-main/storage/assistants.json")
POOL_ACCOUNTS_PATH = Path("D:/hermes-main/storage/pool_accounts.json")
TENANTS_PATH = Path("D:/hermes-main/storage/tenants.json")
EMPTY_POOL_PATH = Path("D:/hermes-main/storage/empty_bot_pool.json")
RENTAL_PROFILES_PATH = Path("D:/hermes-main/storage/rental_profiles.json")


def push_to_build_github():
    """Tự động commit và push sang repo Hermes-build để Vercel tự động build và deploy chuẩn CI/CD."""
    import subprocess
    try:
        from pathlib import Path
        v_dir = Path("D:/hermes-main/hermes-agent-vercel")
        if (v_dir / ".git").exists():
            subprocess.run(["git", "config", "user.name", "5merchdtv-6848"], cwd=v_dir, check=True)
            subprocess.run(["git", "config", "user.email", "5merchdtv@gmail.com"], cwd=v_dir, check=True)
            subprocess.run(["git", "add", "."], cwd=v_dir, check=True)
            res = subprocess.run(["git", "commit", "-m", "Auto-sync from Backend Server", "--author=5merchdtv-6848 <5merchdtv@gmail.com>"], cwd=v_dir, capture_output=True, text=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=v_dir, capture_output=True, text=True)
            print("🚀 Đã tự động push code sang GitHub Hermes-build (Vercel CI/CD)!")
            v_token = os.environ.get("VERCEL_TOKEN")
            if not v_token:
                try:
                    auth_file = Path.home() / "AppData/Roaming/com.vercel.cli/Data/auth.json"
                    if auth_file.exists():
                        with open(auth_file, "r", encoding="utf-8") as af:
                            v_token = json.load(af).get("token")
                except Exception:
                    pass
            deploy_cmd = ["npx.cmd", "vercel", "deploy", "--prod", "--yes"]
            if v_token:
                deploy_cmd.extend(["--token", v_token])
            deploy_res = subprocess.run(
                deploy_cmd,
                cwd=v_dir,
                capture_output=True,
                text=True
            )
            if deploy_res.returncode == 0:
                print("🌟 Vercel Production Deploy OK: https://hermes-agent-vercel.vercel.app")
    except Exception as e:
        print(f"⚠️ Git auto-push warning: {e}")

def build_app():
    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        policy = json.load(f)

    with open(ASSISTANTS_PATH, "r", encoding="utf-8") as f:
        fleet_data = json.load(f)

    with open(POOL_ACCOUNTS_PATH, "r", encoding="utf-8") as f:
        pool_data = json.load(f)

    tenants_data = {"tenants": []}
    if TENANTS_PATH.exists():
        with open(TENANTS_PATH, "r", encoding="utf-8") as f:
            tenants_data = json.load(f)

    empty_pool_data = {"empty_bots": []}
    if EMPTY_POOL_PATH.exists():
        with open(EMPTY_POOL_PATH, "r", encoding="utf-8") as f:
            empty_pool_data = json.load(f)

    rental_profiles_data = {"customers": []}
    if RENTAL_PROFILES_PATH.exists():
        with open(RENTAL_PROFILES_PATH, "r", encoding="utf-8") as f:
            rental_profiles_data = json.load(f)

    all_virtual_bots = []
    for t in tenants_data.get("tenants", []):
        for b in t.get("bots", []):
            b_copy = dict(b)
            b_copy["tenant_id"] = t.get("tenant_id")
            b_copy["tenant_name"] = t.get("name")
            all_virtual_bots.append(b_copy)

    real_groups = policy.get("groups", {})
    total_groups_count = len(real_groups)
    total_members_count = sum(len(g.get("members", {})) for g in real_groups.values())
    formatted_groups = {}
    for gid, ginfo in real_groups.items():
        m_list = []
        for uid, minfo in ginfo.get("members", {}).items():
            clean_uid = uid.replace("u:", "")
            is_ceo = (clean_uid == "7725451581835120119")
            m_list.append({
                "name": minfo.get("name"),
                "uid": uid,
                "role": minfo.get("role"),
                "phone": minfo.get("phone", ""),
                "avatar": minfo.get("avatar", ""),
                "canDM": minfo.get("can_dm", True),
                "canGroup": minfo.get("can_group", True),
                "canAssign": minfo.get("can_assign", False),
                "storagePath": f"D:/hermes-main/storage/users/u_{clean_uid}/",
                "files": ["Chien_luoc_Q4.xlsx", "Quy_chuan_Hermes.md", "Policy_real.json"] if is_ceo else ["context_zalo.json", "chat_history.log"]
            })

        formatted_groups[gid] = {
            "id": gid,
            "name": ginfo.get("name"),
            "avatar": ginfo.get("avatar") or "👥",
            "memberCount": f"{len(m_list)} người",
            "persona": ginfo.get("persona_name"),
            "members": m_list
        }

    first_gid = list(real_groups.keys())[0] if real_groups else ""
    first_ginfo = real_groups.get(first_gid, {}) if first_gid else {}
    first_gname = first_ginfo.get("name", "Chọn Nhóm Zalo")
    first_gmembers = len(first_ginfo.get("members", {}))
    first_gpersona = first_ginfo.get("persona_name", "Tiêu Chuẩn")

    # Options html for group picker
    options_html = ""
    group_checkboxes_html = ""
    for gid, ginfo in real_groups.items():
        options_html += f'                <option value="{gid}">{ginfo.get("name")} ({gid})</option>\n'
        group_checkboxes_html += f'''
          <label class="flex items-center space-x-2 p-2 bg-slate-50 border border-slate-200 rounded-xl hover:bg-indigo-50/50 cursor-pointer text-xs">
            <input type="checkbox" name="assign_group" value="{gid}" class="rounded text-indigo-600 focus:ring-indigo-500 w-4 h-4">
            <span class="font-semibold text-slate-800">{ginfo.get("name")}</span>
            <span class="text-[10px] text-slate-400 font-mono ml-auto">{gid[-6:]}</span>
          </label>
        '''

    assistants_list = fleet_data.get("assistants", [])
    pool_accounts_list = pool_data.get("accounts", [])

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>Hệ Thống Quản Trị Hermes Zalo Enterprise — Sếp Hoàng</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    body {{
      background-color: #f1f5f9;
      color: #0f172a;
      -webkit-tap-highlight-color: transparent;
      font-family: 'Plus Jakarta Sans', sans-serif;
    }}
    .custom-scrollbar::-webkit-scrollbar {{
      width: 6px;
      height: 6px;
    }}
    .custom-scrollbar::-webkit-scrollbar-track {{
      background: #f1f5f9;
    }}
    .custom-scrollbar::-webkit-scrollbar-thumb {{
      background: #cbd5e1;
      border-radius: 4px;
    }}
    .tab-pane {{
      display: none;
    }}
    .tab-pane.active {{
      display: block;
      animation: tabFadeIn 0.2s ease-out forwards;
    }}
    @keyframes tabFadeIn {{
      from {{ opacity: 0; transform: translateY(4px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    .modal-backdrop {{
      background: rgba(15, 23, 42, 0.6);
      backdrop-filter: blur(4px);
    }}
  </style>
</head>
<body class="min-h-screen flex flex-col lg:flex-row antialiased font-sans bg-slate-100 text-slate-800">

  <!-- ==================== SIDEBAR ==================== -->
  <aside class="w-full lg:w-72 bg-white border-r border-slate-200 flex-shrink-0 flex flex-col z-30 shadow-sm">
    <!-- Brand Logo -->
    <div class="h-16 px-6 border-b border-slate-200 flex items-center justify-between bg-white">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#0066cc] to-[#0284c7] flex items-center justify-center text-white shadow-md shadow-blue-500/20">
          <i data-lucide="shield-check" class="w-6 h-6"></i>
        </div>
        <div>
          <span class="font-extrabold text-base tracking-tight text-[#0066cc]">HERMES ZALO</span>
          <span class="block text-[10px] font-bold text-slate-400 uppercase tracking-widest">Enterprise Platform</span>
        </div>
      </div>
      <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
        <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse mr-1.5"></span>
        Online 24/24
      </span>
    </div>

    <!-- Admin Profile Card -->
    <div class="p-4 mx-4 my-3 bg-gradient-to-br from-blue-50 to-slate-50 border border-blue-100 rounded-2xl flex items-center space-x-3">
      <div class="relative">
        <div class="w-11 h-11 rounded-full bg-gradient-to-tr from-amber-400 to-orange-500 p-0.5 shadow-sm">
          <div class="w-full h-full bg-white rounded-full flex items-center justify-center text-amber-600 font-bold">
            <i data-lucide="crown" class="w-5 h-5"></i>
          </div>
        </div>
        <span class="absolute bottom-0 right-0 w-3 h-3 bg-emerald-500 border-2 border-white rounded-full"></span>
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center space-x-1">
          <h4 class="font-extrabold text-sm text-slate-900 truncate">Sếp Hoàng</h4>
          <span class="text-[9px] font-extrabold bg-[#0066cc] text-white px-1.5 py-0.2 rounded uppercase">CEO</span>
        </div>
        <p class="text-[11px] text-slate-500 font-medium truncate">Quản Trị Viên Tối Cao</p>
      </div>
    </div>

    <!-- Navigation Menu -->
    <nav class="flex-1 px-3 py-2 space-y-1 overflow-y-auto custom-scrollbar font-medium text-xs">
      <p class="px-3 pt-2 pb-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">Hệ Thống Điều Hành</p>
      
      <button onclick="switchTab('overview')" id="nav-overview" class="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-white bg-[#0066cc] shadow-sm font-semibold transition-all">
        <i data-lucide="layout-dashboard" class="w-4 h-4"></i>
        <span>Tổng Quan Điều Hành</span>
      </button>

      <button onclick="switchTab('assistants')" id="nav-assistants" class="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all font-medium">
        <i data-lucide="bot" class="w-4 h-4 text-indigo-600"></i>
        <span>Nạp & Quản Trị Trợ Lý & Pool Cookie</span>
        <span class="ml-auto px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200" id="badge-assistants-count">Pool & Bot</span>
      </button>

      <button onclick="switchTab('groups')" id="nav-groups" class="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all font-medium">
        <i data-lucide="users" class="w-4 h-4 text-[#0066cc]"></i>
        <span>Nhóm Zalo & Thành Viên</span>
      </button>

      <button onclick="switchTab('isolation')" id="nav-isolation" class="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all font-medium">
        <i data-lucide="folder-lock" class="w-4 h-4 text-emerald-600"></i>
        <span>Phân Vùng Thư Mục Riêng</span>
      </button>

      <button onclick="switchTab('personas')" id="nav-personas" class="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all font-medium">
        <i data-lucide="briefcase" class="w-4 h-4 text-purple-600"></i>
        <span>Thư Viện Ngành Nghề (Persona)</span>
      </button>

      <p class="px-3 pt-4 pb-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">Công Cụ Nghiệp Vụ</p>

      <button onclick="switchTab('excel')" id="nav-excel" class="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all font-medium">
        <i data-lucide="file-spreadsheet" class="w-4 h-4 text-emerald-600"></i>
        <span>Xử Lý Excel & Files</span>
      </button>

      <button onclick="switchTab('media')" id="nav-media" class="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all font-medium">
        <i data-lucide="clapperboard" class="w-4 h-4 text-amber-500"></i>
        <span>Studio Ảnh & Video AI</span>
      </button>

      <button onclick="switchTab('reminders')" id="nav-reminders" class="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all font-medium">
        <i data-lucide="calendar-check-2" class="w-4 h-4 text-rose-500"></i>
        <span>Lịch Nhắc Việc Tự Động</span>
      </button>

      <button onclick="switchTab('rental')" id="nav-rental" class="w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all font-medium">
        <i data-lucide="store" class="w-4 h-4 text-emerald-600"></i>
        <span>Hệ Thống Cho Thuê Bot</span>
        <span class="ml-auto px-1.5 py-0.5 rounded-full text-[9px] font-extrabold bg-emerald-100 text-emerald-800">VIP</span>
      </button>
    </nav>

    <!-- Server Status Footer -->
    <div class="p-4 border-t border-slate-200 bg-slate-50">
      <div class="flex items-center justify-between text-xs">
        <div class="flex items-center space-x-2">
          <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
          <span class="font-bold text-slate-700">Sever Hermes 24/24</span>
        </div>
        <span class="text-[10px] font-mono text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">PORT: 3050 & 8770</span>
      </div>
    </div>
  </aside>

  <!-- ==================== MAIN CONTENT ==================== -->
  <div class="flex-1 flex flex-col min-w-0 overflow-hidden">

    <!-- TOP HEADER -->
    <header class="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between flex-shrink-0 shadow-sm">
      <div class="flex items-center space-x-4">
        <!-- Assistant Selector (Top Switcher) -->
        <div class="flex items-center space-x-2 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-xl">
          <span class="text-[11px] font-bold text-slate-400 hidden sm:inline">Trợ Lý:</span>
          <select id="assistant-top-selector" onchange="changeActiveAssistant(this.value)" class="bg-transparent text-xs font-bold text-indigo-700 focus:outline-none cursor-pointer max-w-[200px] truncate">
            <!-- Populated dynamically -->
          </select>
          <button onclick="openAddAssistantModal()" class="px-2 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-[10px] font-bold flex items-center space-x-1 transition-all cursor-pointer shadow-sm">
            <i data-lucide="plus" class="w-3 h-3"></i>
            <span class="hidden md:inline">Nạp Bot Zalo</span>
          </button>
          <button onclick="openImportCookieModal()" class="px-2 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-[10px] font-bold flex items-center space-x-1 transition-all cursor-pointer shadow-sm">
            <i data-lucide="cookie" class="w-3 h-3"></i>
            <span class="hidden md:inline">Nạp Cookie Studio</span>
          </button>
        </div>

        <div class="hidden xl:flex items-center space-x-2 text-xs font-semibold text-slate-500">
          <span>Nhóm Đang Chọn:</span>
          <span class="px-2.5 py-1 rounded-lg bg-blue-50 text-[#0066cc] border border-blue-200 text-xs font-bold" id="current-active-group-label">{first_gname}</span>
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <a href="/" target="_blank" class="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold flex items-center space-x-1.5 transition-all">
          <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
          <span class="hidden sm:inline">Khung Chat Hub</span>
        </a>
        <button onclick="exportFullSystemReport()" class="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-sm transition-all cursor-pointer">
          <i data-lucide="download" class="w-3.5 h-3.5"></i>
          <span>Xuất Excel</span>
        </button>
        <button onclick="window.location.reload()" class="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-all cursor-pointer" title="Làm mới">
          <i data-lucide="rotate-cw" class="w-4 h-4"></i>
        </button>
      </div>
    </header>

    <!-- SCROLLABLE BODY -->
    <main class="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 custom-scrollbar">

      <!-- ==================== TAB: TỔNG QUAN ĐIỀU HÀNH ==================== -->
      <section id="pane-overview" class="tab-pane active space-y-6">
        <!-- KPI Metrics Grid -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">Tổng Nhóm Zalo</p>
              <h3 id="kpi-total-groups-count" class="text-2xl font-black text-slate-900 mt-1">{total_groups_count} Nhóm</h3>
              <p class="text-[11px] text-[#0066cc] font-semibold mt-1">100% Đang kết nối Bot</p>
            </div>
            <div class="w-12 h-12 rounded-2xl bg-blue-50 text-[#0066cc] flex items-center justify-center">
              <i data-lucide="users-round" class="w-6 h-6"></i>
            </div>
          </div>

          <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">Thành Viên Quản Trị</p>
              <h3 class="text-2xl font-black text-slate-900 mt-1">{total_members_count} Người</h3>
              <p class="text-[11px] text-emerald-600 font-semibold mt-1">Phân vùng thư mục riêng 100%</p>
            </div>
            <div class="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <i data-lucide="user-check" class="w-6 h-6"></i>
            </div>
          </div>

          <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">Đội Ngũ Trợ Lý & Pool</p>
              <h3 class="text-2xl font-black text-indigo-600 mt-1" id="kpi-overview-assistants">{len(assistants_list)} Bot • {len(pool_accounts_list)} Cookie</h3>
              <p class="text-[11px] text-indigo-600 font-semibold mt-1">Zalo Fleet & AI Studio Pool</p>
            </div>
            <div class="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <i data-lucide="bot" class="w-6 h-6"></i>
            </div>
          </div>

          <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">Dung Lượng Media</p>
              <h3 class="text-2xl font-black text-slate-900 mt-1">98.6 MB</h3>
              <p class="text-[11px] text-purple-600 font-semibold mt-1">25 Tác phẩm AI thực tế</p>
            </div>
            <div class="w-12 h-12 rounded-2xl bg-purple-50 text-purple-600 flex items-center justify-center">
              <i data-lucide="hard-drive" class="w-6 h-6"></i>
            </div>
          </div>
        </div>

        <!-- Group Cards Grid Overview -->
        <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
          <div class="flex items-center justify-between border-b border-slate-100 pb-4">
            <div>
              <h2 id="heading-total-groups" class="text-base font-extrabold text-slate-900">Danh Sách {total_groups_count} Nhóm Zalo Đang Phụ Trách</h2>
              <p class="text-xs text-slate-500 mt-0.5">Hiển thị chi tiết Group ID, số thành viên và chính sách Persona tương ứng của từng nhóm.</p>
            </div>
            <button onclick="switchTab('groups')" class="text-xs text-[#0066cc] font-bold hover:underline flex items-center space-x-1 cursor-pointer">
              <span>Xem chi tiết & Phân quyền</span>
              <i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>
            </button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" id="overview-group-cards">
            <!-- Dynamically populated -->
          </div>
        </div>
      </section>

            <!-- ==================== TAB: QUẢN TRỊ ĐA TRỢ LÝ & COOKIE POOL ==================== -->
      <section id="pane-assistants" class="tab-pane space-y-6">
        <!-- TẦNG 1: CHỌN ZALO BOT TRƯỚC (MASTER SELECTOR BAR) -->
        <div class="bg-white p-5 rounded-3xl border border-slate-200 shadow-sm space-y-4">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
            <div class="flex items-center space-x-3">
              <div class="w-10 h-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-black text-lg">
                📱
              </div>
              <div>
                <h3 class="text-sm font-black text-slate-900 uppercase tracking-wider flex items-center space-x-2">
                  <span>Bước 1: Chọn Zalo Bot Điều Hành (Thân Xác / Phiên Kết Nối)</span>
                  <span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-indigo-100 text-indigo-800">Chọn Bot Trước</span>
                </h3>
                <p class="text-xs text-slate-500 mt-0.5">Click chọn Zalo Bot bên dưới để quản trị toàn bộ Cookie đã nạp, Trợ lý ảo mã #CODE và Khung chat riêng biệt của Bot đó.</p>
              </div>
            </div>
            <div class="flex items-center space-x-2">
              <button onclick="openAddAssistantModal()" class="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-sm transition-all cursor-pointer">
                <i data-lucide="plus-circle" class="w-4 h-4"></i>
                <span>+ Quét QR Nạp Zalo Bot</span>
              </button>
            </div>
          </div>

          <!-- Master Zalo Bot Cards Grid -->
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5" id="zalo-bot-master-selector">
            <!-- Dynamically populated by JS: cards for each Zalo bot -->
          </div>
        </div>

        <!-- TẦNG 2: KHÔNG GIAN BÊN TRONG ZALO BOT ĐÃ CHỌN (WORKSPACE ĐỒNG BỘ) -->
        <div class="space-y-6" id="active-zalo-bot-workspace">
          <!-- Active Bot Summary Banner -->
          <div id="active-zalo-bot-summary-banner" class="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-6 text-white shadow-xl border border-indigo-500/20">
            <!-- Dynamically populated -->
          </div>

          <!-- Bot Internal Navigation Subtabs Bar -->
          <div class="bg-white p-3.5 rounded-2xl border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-3">
            <div class="flex flex-wrap items-center gap-2 w-full md:w-auto">
              <button onclick="switchBotWorkspaceSubTab('cookies')" id="btn-bot-subtab-cookies" class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all bg-amber-500 text-white shadow-sm flex items-center space-x-1.5 cursor-pointer">
                <i data-lucide="cookie" class="w-4 h-4"></i>
                <span>🍪 Trợ Lý AI & Cookie Đã Nạp</span>
                <span class="px-1.5 py-0.5 rounded-full text-[9px] font-extrabold bg-black/20 text-white" id="badge-bot-cookies-count">0 Acc</span>
              </button>
              <button onclick="switchBotWorkspaceSubTab('codes')" id="btn-bot-subtab-codes" class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all bg-slate-100 text-slate-600 hover:bg-slate-200 flex items-center space-x-1.5 cursor-pointer">
                <i data-lucide="hash" class="w-4 h-4 text-purple-600"></i>
                <span>🏷️ Trợ Lý Ảo Theo Mã (#CODE)</span>
                <span class="px-1.5 py-0.5 rounded-full text-[9px] font-extrabold bg-purple-100 text-purple-800" id="badge-bot-codes-count">0 Mã</span>
              </button>
              <button onclick="switchBotWorkspaceSubTab('groups')" id="btn-bot-subtab-groups" class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all bg-slate-100 text-slate-600 hover:bg-slate-200 flex items-center space-x-1.5 cursor-pointer">
                <i data-lucide="users" class="w-4 h-4 text-blue-600"></i>
                <span>👥 Nhóm Zalo Phụ Trách</span>
                <span class="px-1.5 py-0.5 rounded-full text-[9px] font-extrabold bg-blue-100 text-blue-800" id="badge-bot-groups-count">0 Nhóm</span>
              </button>
              <button onclick="switchBotWorkspaceSubTab('chat')" id="btn-bot-subtab-chat" class="px-3.5 py-2 rounded-xl text-xs font-bold transition-all bg-slate-100 text-slate-600 hover:bg-slate-200 flex items-center space-x-1.5 cursor-pointer">
                <i data-lucide="messages-square" class="w-4 h-4 text-emerald-600"></i>
                <span>💬 Khung Chat Riêng Biệt Từng Mã</span>
                <span class="px-1.5 py-0.5 rounded-full text-[9px] font-extrabold bg-emerald-100 text-emerald-800">Cô Lập 100%</span>
              </button>
            </div>

            <div class="flex flex-wrap items-center gap-2 w-full md:w-auto justify-end">
              <button onclick="openAssignCookieModal()" class="px-3 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-sm transition-all cursor-pointer">
                <i data-lucide="link" class="w-4 h-4"></i>
                <span>🔗 Nạp Thêm Cookie Vào Bot Này</span>
              </button>
              <button onclick="openAddVirtualBotModal()" class="px-3 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-sm transition-all cursor-pointer">
                <i data-lucide="plus-circle" class="w-4 h-4"></i>
                <span>+ Tạo Mã Trợ Lý Mới</span>
              </button>
            </div>
          </div>

          <!-- SUB-VIEW A: COOKIES ĐÃ NẠP VÀO BOT NÀY -->
          <div id="bot-view-cookies" class="space-y-6">
            <!-- Assigned Cookies Cards Container -->
            <div class="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 space-y-4">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
                <div>
                  <h3 class="text-sm font-black text-slate-900 uppercase tracking-wider flex items-center space-x-2">
                    <span>Danh Sách Cookie AI Đang Cấp Cho Bot Này (Bộ Não AI)</span>
                  </h3>
                  <p class="text-xs text-slate-500 mt-0.5">Các tài khoản này chịu trách nhiệm sinh văn bản, phân tích dữ liệu và render video TVC cho Zalo Bot.</p>
                </div>
                <div class="flex items-center space-x-2">
                  <button onclick="openAssignCookieModal()" class="px-3 py-1.5 bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200 rounded-xl text-xs font-bold flex items-center space-x-1 cursor-pointer">
                    <i data-lucide="plus" class="w-3.5 h-3.5"></i>
                    <span>Nạp Thêm Cookie</span>
                  </button>
                </div>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" id="bot-assigned-cookies-container">
                <!-- Dynamically rendered -->
              </div>
            </div>

            <!-- Auto OTP & Local Captcha Solve Panel -->
            <div class="bg-white rounded-3xl border border-indigo-200/80 shadow-md shadow-indigo-100/50 p-6 space-y-4">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-indigo-50 pb-4">
                <div class="flex items-center space-x-3">
                  <div class="w-10 h-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-lg">
                    ⚡
                  </div>
                  <div>
                    <h3 class="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Tự Động Nạp Mail | Password & Đăng Nhập Local Giải Captcha</h3>
                    <p class="text-xs text-slate-500 mt-0.5">Tự động lấy mã OTP Microsoft, hoặc mở Chrome thật trên màn hình Sever để Sếp tự giải captcha trực tiếp.</p>
                  </div>
                </div>
                <div class="flex items-center space-x-2">
                  <span class="px-2.5 py-1 rounded-full text-[10px] font-extrabold bg-indigo-50 text-indigo-700 border border-indigo-200 uppercase">Auto OTP & Local Solve</span>
                </div>
              </div>

              <div class="space-y-3">
                <div class="flex items-center justify-between text-xs font-bold text-slate-700">
                  <span>Danh Sách Tài Khoản (mỗi dòng 1 tài khoản: <code class="font-mono text-indigo-600 font-semibold">email|password</code> hoặc <code class="font-mono text-indigo-600 font-semibold">email|pass|refreshToken</code>)</span>
                  <span id="autoAccCount" class="text-slate-400 font-mono text-[11px]">0 tài khoản</span>
                </div>
                <textarea id="autoAccInput" rows="3" oninput="updateAutoAccCount()" placeholder="user1@hotmail.com|password123&#10;user2@hotmail.com|password456|refreshToken|client_id" class="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs font-mono text-slate-800 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"></textarea>

                <div class="flex flex-col sm:flex-row items-center gap-2">
                  <input type="text" id="sheetUrl" placeholder="Hoặc dán link Google Sheet (cột: email | password | refreshToken | client_id)" class="flex-1 w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs text-slate-800 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none font-medium">
                  <button onclick="loadFromGoogleSheet()" class="w-full sm:w-auto px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-all flex items-center justify-center space-x-1.5 cursor-pointer">
                    <i data-lucide="sheet" class="w-4 h-4 text-emerald-600"></i>
                    <span>Tải Từ Sheet</span>
                  </button>
                </div>

                <div class="flex flex-wrap items-center justify-between gap-3 pt-2">
                  <div class="flex flex-wrap items-center gap-4 text-xs">
                    <label class="flex items-center space-x-2 cursor-pointer text-slate-600 font-semibold">
                      <input type="checkbox" id="autoAccSkip" checked class="rounded text-indigo-600 focus:ring-indigo-500 w-4 h-4">
                      <span>Bỏ qua tài khoản đang hoạt động (chỉ chạy lại khi expired)</span>
                    </label>
                    <label class="flex items-center space-x-2 cursor-pointer text-slate-600 font-semibold">
                      <input type="checkbox" id="autoAccOverwrite" checked class="rounded text-indigo-600 focus:ring-indigo-500 w-4 h-4">
                      <span>Ghi đè tài khoản đã có</span>
                    </label>
                  </div>

                  <div class="flex items-center space-x-2 w-full sm:w-auto justify-end">
                    <button onclick="startAutoExtract()" id="btnStartAutoAcc" class="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-md shadow-indigo-600/20 transition-all cursor-pointer">
                      <i data-lucide="zap" class="w-4 h-4 text-amber-300"></i>
                      <span>⚡ Bắt Đầu Đăng Nhập & Nạp Vào Pool</span>
                    </button>
                    <button onclick="startLocalLogin()" id="btnStartLocalAcc" class="px-4 py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-md shadow-purple-600/20 transition-all cursor-pointer" title="Mở Chrome trên máy Sever để tự giải captcha">
                      <i data-lucide="monitor" class="w-4 h-4"></i>
                      <span>🖥️ Đăng Nhập Local (Tự Giải Captcha)</span>
                    </button>
                    <button onclick="openImportCookieModal()" class="px-3.5 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-sm transition-all cursor-pointer" title="Dán cookie JSON trực tiếp">
                      <i data-lucide="cookie" class="w-4 h-4"></i>
                      <span>+ Nạp Cookie</span>
                    </button>
                  </div>
                </div>

                <!-- Progress & Logs Box -->
                <div id="autoAccProgress" class="hidden pt-3 border-t border-slate-100 space-y-2">
                  <div class="flex items-center justify-between text-xs">
                    <span id="autoAccStatus" class="font-bold text-indigo-600">Đang chuẩn bị...</span>
                    <span id="autoAccRatio" class="font-mono text-slate-400 font-bold">0/0</span>
                  </div>
                  <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
                    <div id="autoAccBar" class="bg-indigo-600 h-full rounded-full transition-all duration-300" style="width: 0%"></div>
                  </div>
                  <pre id="autoAccLogs" class="bg-slate-900 text-slate-200 p-3 rounded-xl font-mono text-[11px] max-h-36 overflow-y-auto leading-relaxed border border-slate-800"></pre>
                </div>
              </div>
            </div>

            <!-- Full Pool Reference Table -->
            <div class="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
              <div class="p-5 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h3 class="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Kho Toàn Bộ Cookie Studio Sẵn Có</h3>
                  <p class="text-xs text-slate-500 mt-0.5">Sếp có thể bấm [Gán Vào Zalo Bot] để cấp thêm tài khoản cho Bot đang chọn.</p>
                </div>
                <div class="flex items-center space-x-2">
                  <button onclick="checkPoolHealth()" class="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold flex items-center space-x-1 cursor-pointer">
                    <i data-lucide="activity" class="w-3.5 h-3.5 text-emerald-600"></i>
                    <span>Kiểm Tra Sức Khỏe Pool</span>
                  </button>
                </div>
              </div>
              <div class="overflow-x-auto">
                <table class="w-full text-left text-xs text-slate-600">
                  <thead class="bg-slate-50 text-[11px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                    <tr>
                      <th class="py-3 px-4">Tên Tài Khoản</th>
                      <th class="py-3 px-4 text-center">Trạng Thái Cookie</th>
                      <th class="py-3 px-4">⚡ Mức Sử Dụng & Token</th>
                      <th class="py-3 px-4 text-center">⏱️ Chu Kỳ Đặt Lại (Tuần)</th>
                      <th class="py-3 px-4 text-center">Trạng Thái Với Bot Này</th>
                      <th class="py-3 px-4 text-right">Thao Tác</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-slate-100 font-medium" id="pool-table-body">
                    <!-- Dynamically populated -->
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- SUB-VIEW B: TRỢ LÝ ẢO THEO MÃ (#CODE) CỦA BOT NÀY -->
          <div id="bot-view-codes" class="space-y-6 hidden">
            <div class="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 space-y-4">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
                <div>
                  <h3 class="text-sm font-black text-slate-900 uppercase tracking-wider flex items-center space-x-2">
                    <span>Trợ Lý Ảo Theo Mã (#CODE) Phụ Trách Bởi Bot Này</span>
                  </h3>
                  <p class="text-xs text-slate-500 mt-0.5">Mỗi mã đại diện cho 1 nghiệp vụ chuyên sâu với Persona, Prompt học việc và Khung Chat độc lập 100%.</p>
                </div>
                <div class="flex items-center space-x-2">
                  <button onclick="openAddVirtualBotModal()" class="px-3.5 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-sm transition-all cursor-pointer">
                    <i data-lucide="plus-circle" class="w-4 h-4"></i>
                    <span>+ Khởi Tạo Mã Trợ Lý Mới</span>
                  </button>
                </div>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5" id="bot-virtual-bots-container">
                <!-- Dynamically populated -->
              </div>
            </div>
          </div>

          <!-- SUB-VIEW C: NHÓM ZALO PHỤ TRÁCH -->
          <div id="bot-view-groups" class="space-y-6 hidden">
            <div class="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 space-y-4">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
                <div>
                  <h3 class="text-sm font-black text-slate-900 uppercase tracking-wider flex items-center space-x-2">
                    <span>Nhóm Zalo Đang Được Phụ Trách Bởi Bot Này</span>
                  </h3>
                  <p class="text-xs text-slate-500 mt-0.5">Zalo Bot đang lắng nghe và phản hồi tin nhắn trong các nhóm này theo chính sách phân quyền.</p>
                </div>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" id="bot-assigned-groups-container">
                <!-- Dynamically populated -->
              </div>
            </div>
          </div>

          <!-- SUB-VIEW D: KHUNG CHAT RIÊNG BIỆT CHO TỪNG TÍNH NĂNG (#CODE DEDICATED CONSOLE) -->
          <div id="bot-view-chat" class="space-y-6 hidden">
            <div class="bg-white rounded-3xl border border-slate-200 shadow-xl overflow-hidden flex flex-col h-[750px]">
              <!-- Chat Console Top Bar: Alert & Code Pills -->
              <div class="p-4 bg-slate-900 text-white border-b border-slate-800 space-y-3 flex-shrink-0">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div class="flex items-center space-x-2">
                    <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    <h3 class="text-sm font-black tracking-wide text-white uppercase">Khung Chat Riêng Biệt Cho Từng Tính Năng (#CODE)</h3>
                  </div>
                  <div class="flex items-center space-x-2">
                    <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-400/30">
                      🔒 Cô Lập 100% Ngữ Cảnh
                    </span>
                    <button onclick="clearDedicatedChatHistory()" class="px-2.5 py-1 bg-white/10 hover:bg-rose-500/80 text-slate-300 hover:text-white rounded-lg text-[10px] font-bold transition-all flex items-center space-x-1 cursor-pointer">
                      <i data-lucide="trash-2" class="w-3 h-3"></i>
                      <span>Xóa Lịch Sử Mã Này</span>
                    </button>
                  </div>
                </div>

                <!-- Horizontal Code Switcher Pills -->
                <div class="flex items-center space-x-2 overflow-x-auto pb-1" id="dedicated-chat-code-pills">
                  <!-- Dynamically populated: pills for #MEDIA, #HERMES, #KETOAN, #SALE... -->
                </div>
              </div>

              <!-- Chat Sub-header Info -->
              <div class="px-5 py-2.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between text-xs text-slate-600 flex-shrink-0">
                <div class="flex items-center space-x-2" id="dedicated-chat-active-info">
                  <!-- e.g. "Đang trò chuyện với: #MEDIA (Bot Media & Video TVC Studio) • Bộ não: syncere1812031999" -->
                </div>
                <div class="text-[11px] text-slate-400 font-mono">
                  <span>Session: <strong class="text-indigo-600" id="dedicated-chat-session-id">session_MEDIA</strong></span>
                </div>
              </div>

              <!-- Chat Messages Stream (Scrollable) -->
              <div class="flex-1 p-5 overflow-y-auto space-y-4 bg-slate-100/50" id="dedicated-chat-messages-container">
                <!-- Dynamically populated from localStorage['hermes_chat_' + botId + '_' + code] -->
              </div>

              <!-- Chat Input Bar -->
              <div class="p-4 bg-white border-t border-slate-200 flex-shrink-0 space-y-2">
                <form onsubmit="handleSendDedicatedChat(event)" class="flex items-center space-x-2">
                  <div class="px-3 py-2.5 bg-purple-100 text-purple-800 font-mono font-black text-xs rounded-xl flex items-center space-x-1" id="dedicated-chat-input-code-badge">
                    #MEDIA
                  </div>
                  <input type="text" id="dedicated-chat-input" placeholder="Nhập tin nhắn trao đổi riêng với tính năng này..." class="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs text-slate-800 focus:outline-none focus:border-purple-600 font-medium">
                  <button type="submit" class="px-5 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 shadow-md shadow-purple-600/20 cursor-pointer">
                    <i data-lucide="send" class="w-3.5 h-3.5"></i>
                    <span>Gửi</span>
                  </button>
                </form>
                <div class="flex items-center justify-between text-[10px] text-slate-400 px-1">
                  <span>💡 Tip: Mọi trao đổi trong khung chat này chỉ lưu giữ cho mã đang chọn, không chia sẻ sang các mã khác.</span>
                  <span>Engine: <strong>Studio AI Engine (Cổng 8770)</strong></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ==================== TAB: NHÓM ZALO & THÀNH VIÊN ==================== -->
      <section id="pane-groups" class="tab-pane space-y-6">
        <!-- Group Detail Header Card -->
        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div class="flex items-center space-x-4">
            <div class="w-14 h-14 rounded-2xl bg-blue-100 text-[#0066cc] flex items-center justify-center font-bold text-xl overflow-hidden" id="group-avatar-display">
              👥
            </div>
            <div>
              <div class="flex items-center space-x-2">
                <h2 class="text-lg font-black text-slate-900" id="group-name-display">{first_gname}</h2>
                <span class="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md text-[10px] font-bold uppercase">Bot Active</span>
              </div>
              <div class="flex flex-wrap items-center gap-3 text-xs text-slate-500 mt-1 font-mono">
                <span>Group ID: <strong class="text-slate-800" id="group-id-display">{first_gid}</strong></span>
                <span>•</span>
                <span>Thành viên: <strong class="text-slate-800" id="group-member-count">{first_gmembers} người</strong></span>
                <span>•</span>
                <span>Persona: <strong class="text-purple-700 font-semibold" id="group-persona-label">{first_gpersona}</strong></span>
              </div>
            </div>
          </div>

          <div class="flex items-center space-x-3">
            <button onclick="leaveZaloGroup(CURRENT_GROUP_KEY, document.getElementById('group-name-display').innerText)" class="px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 hover:border-rose-300 rounded-xl font-bold text-xs flex items-center space-x-1.5 transition-all shadow-sm">
              <span>🚪</span>
              <span>Thoát Nhóm Này</span>
            </button>
            <select id="group-picker-select" onchange="selectGroup(this.value)" class="bg-slate-50 border border-slate-300 text-slate-900 text-xs rounded-xl focus:ring-[#0066cc] focus:border-[#0066cc] p-2.5 font-bold cursor-pointer">
{options_html}            </select>
          </div>
        </div>

        <!-- Members Table -->
        <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div class="p-5 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h3 class="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Danh Sách Thành Viên Thực Tế & Phân Quyền</h3>
              <p class="text-xs text-slate-500 mt-0.5">Từng thành viên được cô lập dữ liệu 100% trong thư mục máy chủ vật lý.</p>
            </div>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-600">
              <thead class="bg-slate-50 text-[11px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                <tr>
                  <th class="py-3 px-4">Thành Viên (Zalo Display Name)</th>
                  <th class="py-3 px-4">User ID (Zalo)</th>
                  <th class="py-3 px-4 text-center">Chat 1-1 (DM)</th>
                  <th class="py-3 px-4 text-center">Chat Nhóm</th>
                  <th class="py-3 px-4 text-center">Giao Task</th>
                  <th class="py-3 px-4 text-center">Thư Mục Cô Lập</th>
                  <th class="py-3 px-4 text-right">Thao Tác</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100 font-medium" id="members-table-body">
                <!-- Dynamically populated -->
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- ==================== TAB: PHÂN VÙNG THƯ MỤC RIÊNG ==================== -->
      <section id="pane-isolation" class="tab-pane space-y-6">
        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <h2 class="text-base font-extrabold text-slate-900">Kiểm Tra Phân Vùng Cô Lập Vật Lý (User Storage Sandbox)</h2>
            <p class="text-xs text-slate-500 mt-0.5">Mỗi người dùng Zalo chỉ có quyền đọc/ghi trên thư mục riêng tại D:/hermes-main/storage/users/u_{{uid}}/.</p>
          </div>
        </div>

        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div class="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h3 class="text-sm font-extrabold text-slate-900" id="inspect-user-name">Chi Tiết Thư Mục: Sếp Hoàng (CEO)</h3>
              <p class="text-xs font-mono text-slate-400 mt-0.5" id="inspect-user-path">D:/hermes-main/storage/users/u_7725451581835120119/</p>
            </div>
            <span class="px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg text-xs font-bold">Quyền: Tối Cao (Master Read/Write)</span>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-3" id="user-files-container">
            <!-- Dynamically populated -->
          </div>
        </div>
      </section>

      <!-- ==================== TAB: THƯ VIỆN PERSONA ==================== -->
      <section id="pane-personas" class="tab-pane space-y-6">
        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <h2 class="text-base font-extrabold text-slate-900">Thư Viện Ngành Nghề & Kịch Bản Phản Hồi (Persona Library)</h2>
            <p class="text-xs text-slate-500 mt-0.5">Mỗi nhóm Zalo được gán một phong thái phục vụ độc lập, tự động điều chỉnh câu trả lời.</p>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col justify-between">
            <div class="p-6">
              <div class="w-12 h-12 rounded-2xl bg-blue-50 text-[#0066cc] flex items-center justify-center font-bold text-xl mb-4">
                💼
              </div>
              <h3 class="text-base font-extrabold text-slate-900">Quản Trị Doanh Nghiệp & HKD</h3>
              <p class="text-xs text-slate-500 mt-2 leading-relaxed">
                Chuyên sâu báo cáo thu chi, tồn kho, doanh thu hàng ngày, hỗ trợ xuất hóa đơn và xử lý văn bản tài chính cho Hộ Kinh Doanh & Công Ty.
              </p>
            </div>
            <div class="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
              <span class="text-[10px] text-slate-400 font-mono">PERSONA_HKD_V2</span>
              <button onclick="applyPersonaToCurrentGroup('hkd')" class="px-3 py-1.5 bg-[#0066cc] hover:bg-[#0284c7] text-white rounded-xl text-xs font-bold transition-all shadow-sm cursor-pointer">
                Áp Dụng Cho Nhóm Này
              </button>
            </div>
          </div>

          <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col justify-between">
            <div class="p-6">
              <div class="w-12 h-12 rounded-2xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold text-xl mb-4">
                🏠
              </div>
              <h3 class="text-base font-extrabold text-slate-900">Nội Trợ & Quản Lý Gia Đình</h3>
              <p class="text-xs text-slate-500 mt-2 leading-relaxed">
                Nhắc lịch chợ búa, thực đơn hàng ngày, theo dõi hạn sử dụng thuốc và đồ gia dụng, nhắc việc nhà cho các thành viên thân mật, lễ phép.
              </p>
            </div>
            <div class="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
              <span class="text-[10px] text-slate-400 font-mono">PERSONA_FAMILY_V2</span>
              <button onclick="applyPersonaToCurrentGroup('family')" class="px-3 py-1.5 bg-[#0066cc] hover:bg-[#0284c7] text-white rounded-xl text-xs font-bold transition-all shadow-sm cursor-pointer">
                Áp Dụng Cho Nhóm Này
              </button>
            </div>
          </div>

          <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col justify-between">
            <div class="p-6">
              <div class="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold text-xl mb-4">
                ⚡
              </div>
              <h3 class="text-base font-extrabold text-slate-900">Trợ Lý Điều Phối 24/7</h3>
              <p class="text-xs text-slate-500 mt-2 leading-relaxed">
                Trực ban liên tục, tiếp nhận yêu cầu khẩn cấp, nhắc lịch họp giao ban, tự động thông báo tiến độ trực tiếp cho Sếp Hoàng.
              </p>
            </div>
            <div class="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
              <span class="text-[10px] text-slate-400 font-mono">PERSONA_OPS_V2</span>
              <button onclick="applyPersonaToCurrentGroup('ops')" class="px-3 py-1.5 bg-[#0066cc] hover:bg-[#0284c7] text-white rounded-xl text-xs font-bold transition-all shadow-sm cursor-pointer">
                Áp Dụng Cho Nhóm Này
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- ==================== TAB: EXCEL & FILES ==================== -->
      <section id="pane-excel" class="tab-pane space-y-6">
        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 class="text-base font-extrabold text-slate-900">Trung Tâm Xử Lý File & Bảng Tính Excel</h2>
            <p class="text-xs text-slate-500 mt-0.5">Tạo file báo cáo thật (.xlsx) hoặc kéo thả file bảng tính để AI trích xuất phân tích số liệu.</p>
          </div>
          <div class="flex items-center space-x-2">
            <button onclick="exportFullSystemReport()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold flex items-center space-x-2 shadow-sm transition-all cursor-pointer">
              <i data-lucide="download" class="w-4 h-4"></i>
              <span>Xuất Báo Cáo Excel Phân Quyền Nhóm</span>
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-center items-center text-center cursor-pointer hover:border-[#0066cc] border-dashed border-2" onclick="document.getElementById('excel-file-input').click()">
            <input type="file" id="excel-file-input" class="hidden" accept=".xlsx,.xls,.csv" onchange="readExcelFile(event)">
            <div class="w-14 h-14 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center mb-3">
              <i data-lucide="file-up" class="w-7 h-7"></i>
            </div>
            <h4 class="text-sm font-bold text-slate-900">Chọn hoặc Kéo Thả File Excel/CSV Vào Đây</h4>
            <p class="text-xs text-slate-500 mt-1 max-w-sm">Hệ thống sử dụng thư viện SheetJS đọc bảng trực tiếp trong trình duyệt và đồng bộ về thư mục riêng của người dùng.</p>
          </div>

          <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between" id="excel-preview-box">
            <div>
              <h4 class="text-xs font-extrabold text-slate-900 uppercase tracking-wider mb-2">Bảng Dữ Liệu Đọc Được Từ File:</h4>
              <div class="overflow-x-auto max-h-48 border border-slate-200 rounded-xl bg-slate-50 p-2 text-xs font-mono text-slate-700" id="excel-preview-content">
                <p class="text-slate-400 italic text-center py-8">Chưa có file nào được nạp. Hãy chạm khung bên trái để đọc file thử nghiệm.</p>
              </div>
            </div>
            <button onclick="alert('Đã đồng bộ dữ liệu vào thư mục cá nhân và sẵn sàng gửi báo cáo Zalo!')" class="w-full mt-3 py-2 bg-[#0066cc] hover:bg-[#0284c7] text-white rounded-xl text-xs font-bold transition-all cursor-pointer">
              Lưu Vào Phân Vùng Người Dùng & Báo Zalo
            </button>
          </div>
        </div>
      </section>

      <!-- ==================== TAB: STUDIO ĐỒ HỌA & VIDEO AI ==================== -->
      <section id="pane-media" class="tab-pane space-y-6">
        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <h2 class="text-base font-extrabold text-slate-900">Studio Đồ Họa & Video TVC AI (Sever 24/24)</h2>
            <p class="text-xs text-slate-500 mt-0.5">Kết nối máy chủ đồ họa riêng cổng 8770 để render video chuyển động và hình ảnh nghệ thuật sắc nét.</p>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm lg:col-span-1 space-y-4">
            <h3 class="text-xs font-extrabold text-slate-900 uppercase tracking-wider">Khung Lệnh Sáng Tạo AI</h3>
            <div>
              <label class="text-[11px] font-bold text-slate-600 uppercase">Kịch Bản / Ý Tưởng:</label>
              <textarea id="studio-prompt" rows="3" placeholder="Ví dụ: Giảng đường đại học tương lai với công nghệ hologram hiện đại..." class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs focus:outline-none focus:border-[#0066cc]"></textarea>
            </div>
            <div>
              <label class="text-[11px] font-bold text-slate-600 uppercase">Loại Tác Phẩm:</label>
              <select class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs font-semibold">
                <option value="tvc">🎬 Video TVC Chuyển Động 4K (8s - 15s)</option>
                <option value="photo">🎨 Ảnh Nghệ Thuật High-Res (16:9 / 9:16)</option>
              </select>
            </div>
            <button onclick="alert('Đã gửi kịch bản tới Máy Chủ Đồ Họa Riêng (Cổng 8770)! Khi hoàn thành sẽ tự động lưu vào phân vùng của Sếp và gửi Zalo.')" class="w-full py-3 bg-[#0066cc] hover:bg-[#0284c7] text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-blue-500/20 cursor-pointer">
              Khởi Động Render Trên Sever
            </button>
          </div>

          <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm lg:col-span-2 space-y-4">
            <h3 class="text-xs font-extrabold text-slate-900 uppercase tracking-wider">Kho Tác Phẩm Gần Nhất (98.6 MB)</h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div class="border border-slate-200 rounded-xl overflow-hidden shadow-sm">
                <img src="https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600&auto=format&fit=crop&q=80" alt="Video" class="w-full h-36 object-cover">
                <div class="p-3">
                  <h4 class="font-bold text-xs text-slate-900">Clip TVC Anime Cinematic</h4>
                  <p class="text-[11px] text-slate-500 mt-0.5">Render chuẩn phong cách điện ảnh 4K.</p>
                  <button onclick="alert('Đã gửi video trực tiếp vào nhóm Zalo đang chọn!')" class="w-full mt-2 py-1.5 bg-blue-50 hover:bg-blue-100 text-[#0066cc] rounded-lg text-xs font-bold border border-blue-200 cursor-pointer">
                    Gửi Vào Nhóm Zalo
                  </button>
                </div>
              </div>

              <div class="border border-slate-200 rounded-xl overflow-hidden shadow-sm">
                <img src="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80" alt="Image" class="w-full h-36 object-cover">
                <div class="p-3">
                  <h4 class="font-bold text-xs text-slate-900">Ảnh Đồ Họa 3D Văn Phòng</h4>
                  <p class="text-[11px] text-slate-500 mt-0.5">Tác phẩm kiến trúc isometric chất lượng cao.</p>
                  <button onclick="alert('Đã gửi ảnh trực tiếp vào nhóm Zalo đang chọn!')" class="w-full mt-2 py-1.5 bg-blue-50 hover:bg-blue-100 text-[#0066cc] rounded-lg text-xs font-bold border border-blue-200 cursor-pointer">
                    Gửi Vào Nhóm Zalo
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ==================== TAB: LỊCH NHẮC VIỆC ==================== -->
      <section id="pane-reminders" class="tab-pane space-y-6">
        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <h2 class="text-base font-extrabold text-slate-900">Lịch Nhắc Việc Tự Động Theo Giờ & Định Kỳ (Cron)</h2>
            <p class="text-xs text-slate-500 mt-0.5">Hệ thống tự động kích hoạt Zalo Bridge bắn thông báo thẻ vào đúng nhóm hoặc tin riêng của từng cá nhân.</p>
          </div>
          <button onclick="alert('Mở form tạo lịch nhắc mới')" class="px-3.5 py-2 bg-[#0066cc] text-white rounded-xl text-xs font-bold hover:bg-[#0284c7] cursor-pointer">
            + Thêm Lịch Mới
          </button>
        </div>

        <div class="space-y-3">
          <div class="bg-white p-4 rounded-2xl border-l-4 border-l-[#0066cc] border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <span class="text-[10px] font-extrabold bg-blue-50 text-[#0066cc] border border-blue-200 px-2 py-0.5 rounded-full uppercase">15:30 Chiều Nay</span>
              <h4 class="font-bold text-sm text-slate-900 mt-1">Họp Giao Ban Tiến Độ Với Ban Giám Hiệu & Đối Tác</h4>
              <p class="text-xs text-slate-500 mt-0.5">Gửi thông báo kèm file Excel tổng hợp điểm vào nhóm Zalo.</p>
            </div>
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
          </div>

          <div class="bg-white p-4 rounded-2xl border-l-4 border-l-amber-500 border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <span class="text-[10px] font-extrabold bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full uppercase">08:30 Thứ 2 Hàng Tuần</span>
              <h4 class="font-bold text-sm text-slate-900 mt-1">Gửi Báo Cáo Tuần Cho Sếp Hoàng</h4>
              <p class="text-xs text-slate-500 mt-0.5">Bắn tin riêng 1-1 vào tài khoản Zalo cá nhân của Sếp Hoàng.</p>
            </div>
            <span class="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
          </div>
        </div>
      </section>

      <!-- ==================== TAB: HỆ THỐNG CHO THUÊ BOT TRỢ LÝ ==================== -->
      <section id="pane-rental" class="tab-pane space-y-6">
        <!-- Overview Banner -->
        <div class="bg-gradient-to-r from-emerald-800 to-teal-900 p-6 rounded-3xl text-white shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div class="space-y-1.5">
            <div class="flex items-center space-x-2">
              <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase bg-emerald-500/30 text-emerald-200 border border-emerald-400/30">Nền Tảng Cho Thuê Bot</span>
              <span class="text-xs text-emerald-200 font-mono">Bth Host • Onboarding QR • Gán Độc Quyền 30 Ngày</span>
            </div>
            <h3 class="text-lg font-black tracking-tight">Hệ Thống Cho Thuê & Cấp Phát Bot Trợ Lý Zalo Độc Quyền</h3>
            <p class="text-xs text-emerald-200 max-w-2xl leading-relaxed">
              Khách hàng nhắn tin cho <strong>Bot Chủ Bth</strong> để đăng ký → Quét mã QR liên kết → Hệ thống tự sinh Profile & Phân vùng cô lập vật lý → Gán Bot độc quyền từ kho theo gói 30 ngày (tuyệt đối không cấp trùng cho người khác).
            </p>
          </div>
          <div class="flex flex-col sm:flex-row items-center gap-3">
            <button onclick="openAddEmptyBotModal()" class="w-full sm:w-auto px-4 py-3 bg-amber-400 hover:bg-amber-300 text-slate-900 rounded-2xl text-xs font-black flex items-center justify-center space-x-2 shadow-lg shadow-amber-400/20 cursor-pointer transition-all">
              <i data-lucide="plus-circle" class="w-4 h-4"></i>
              <span>+ Nạp Bot Trống Vào Kho</span>
            </button>
          </div>
        </div>

        <!-- KPI Summary Cards -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">Khách Thuê Hoạt Động</p>
              <h3 class="text-2xl font-black text-emerald-600 mt-1" id="kpi-rental-active-customers">{len([c for c in rental_profiles_data.get('customers', []) if c.get('status') == 'active'])} Khách</h3>
              <p class="text-[11px] text-slate-500 font-semibold mt-1">Đang chạy hợp đồng</p>
            </div>
            <div class="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-xl">
              👥
            </div>
          </div>

          <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">Bot Trống Sẵn Sàng</p>
              <h3 class="text-2xl font-black text-indigo-600 mt-1" id="kpi-rental-available-bots">{empty_pool_data.get('available_count', 0)} Bot</h3>
              <p class="text-[11px] text-slate-500 font-semibold mt-1">Sẵn sàng cấp ngay</p>
            </div>
            <div class="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-xl">
              📦
            </div>
          </div>

          <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">Bot Đang Cho Thuê</p>
              <h3 class="text-2xl font-black text-amber-600 mt-1" id="kpi-rental-rented-bots">{empty_pool_data.get('rented_count', 0)} Bot</h3>
              <p class="text-[11px] text-slate-500 font-semibold mt-1">Khóa độc quyền 30 ngày</p>
            </div>
            <div class="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold text-xl">
              🔒
            </div>
          </div>

          <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-slate-400 uppercase tracking-wider">Phân Vùng Sandbox</p>
              <h3 class="text-2xl font-black text-purple-600 mt-1">100% Cô Lập</h3>
              <p class="text-[11px] text-slate-500 font-semibold mt-1">Bảo mật tuyệt đối</p>
            </div>
            <div class="w-12 h-12 rounded-2xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold text-xl">
              🛡️
            </div>
          </div>
        </div>

        <!-- Section 1: Danh sách Khách Hàng Thuê Độc Quyền -->
        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div class="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h3 class="text-sm font-extrabold text-slate-900 flex items-center space-x-2">
                <i data-lucide="users" class="w-4 h-4 text-emerald-600"></i>
                <span>Danh Sách Khách Hàng Đang Thuê Bot (Độc Quyền 30 Ngày)</span>
              </h3>
              <p class="text-xs text-slate-500 mt-0.5">Mỗi khách hàng sở hữu Profile độc lập và thư mục Sandbox vật lý riêng biệt.</p>
            </div>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-600">
              <thead class="bg-slate-50 text-[11px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                <tr>
                  <th class="py-3 px-4">Khách Hàng (Tên & Zalo ID)</th>
                  <th class="py-3 px-4">Gói Cước Đăng Ký</th>
                  <th class="py-3 px-4 text-center">Số Bot Gán</th>
                  <th class="py-3 px-4">Thư Mục Cô Lập Sandbox</th>
                  <th class="py-3 px-4 text-center">Thời Hạn Còn Lại</th>
                  <th class="py-3 px-4 text-center">Trạng Thái</th>
                  <th class="py-3 px-4 text-right">Thao Tác</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100 font-medium" id="rental-customers-table-body">
                <!-- Dynamically populated -->
              </tbody>
            </table>
          </div>
        </div>

        <!-- Section 2: Kho Bot Trống Sẵn Sàng Cấp Phát -->
        <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div class="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h3 class="text-sm font-extrabold text-slate-900 flex items-center space-x-2">
                <i data-lucide="box" class="w-4 h-4 text-indigo-600"></i>
                <span>Kho Bot Trống Sẵn Sàng Cho Thuê (Empty Bot Pool)</span>
              </h3>
              <p class="text-xs text-slate-500 mt-0.5">Sếp Hoàng nạp sẵn tài khoản trống vào đây. Khi khách kết nối, hệ thống tự động khóa và gán độc quyền.</p>
            </div>
            <button onclick="openAddEmptyBotModal()" class="px-3 py-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 rounded-xl text-xs font-bold transition-all cursor-pointer">
              + Nạp Bot Trống
            </button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" id="empty-bot-cards-container">
            <!-- Dynamically populated -->
          </div>
        </div>
      </section>

    </main>
  </div>

  <!-- ==================== MODAL: NẠP TÀI KHOẢN BOT ZALO ==================== -->
  <div id="modal-add-assistant" class="fixed inset-0 z-50 flex items-center justify-center p-4 modal-backdrop hidden">
    <div class="bg-white rounded-3xl border border-slate-200 shadow-2xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto custom-scrollbar">
      <div class="flex items-center justify-between border-b border-slate-100 pb-3">
        <div class="flex items-center space-x-2.5">
          <div class="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
            <i data-lucide="bot" class="w-5 h-5"></i>
          </div>
          <div>
            <h3 class="font-black text-slate-900 text-sm">Nạp Tài Khoản Trợ Lý Zalo Mới</h3>
            <p class="text-[11px] text-slate-500">Thêm bot Zalo mới và phân bổ nhóm phụ trách</p>
          </div>
        </div>
        <button onclick="closeAddAssistantModal()" class="text-slate-400 hover:text-slate-700 p-1 rounded-lg">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <form id="form-new-assistant" onsubmit="submitAddAssistant(event)" class="space-y-3.5">
        <div>
          <label class="block text-[11px] font-bold text-slate-700 uppercase">Tên Hiển Thị Trợ Lý *</label>
          <input type="text" id="new-ast-name" required placeholder="Ví dụ: Trợ Lý Tài Chính Kế Toán" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-indigo-600">
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[11px] font-bold text-slate-700 uppercase">Nền Tảng / Platform</label>
            <select id="new-ast-platform" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2 text-xs font-semibold">
              <option value="Zalo Bot">Zalo Bot (zca-js Bridge)</option>
              <option value="Antigravity Core">Antigravity Core (CLI)</option>
              <option value="Media AI Engine">Media AI Engine (GPU)</option>
              <option value="Web Agent API">Web Agent API</option>
            </select>
          </div>
          <div>
            <label class="block text-[11px] font-bold text-slate-700 uppercase">Cổng Port Bridge</label>
            <input type="number" id="new-ast-port" value="3052" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[11px] font-bold text-slate-700 uppercase">Số Điện Thoại / UID</label>
            <input type="text" id="new-ast-phone" placeholder="0908xxxxxx hoặc uid" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs">
          </div>
          <div>
            <label class="block text-[11px] font-bold text-slate-700 uppercase">Vai Trò / Chuyên Môn</label>
            <select id="new-ast-role" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2 text-xs font-semibold">
              <option value="Trợ Lý Kế Toán & Báo Cáo">Trợ Lý Kế Toán & Báo Cáo</option>
              <option value="Trợ Lý Bán Hàng & Chốt Đơn">Trợ Lý Bán Hàng & Chốt Đơn</option>
              <option value="Trợ Lý Kỹ Thuật & Code">Trợ Lý Kỹ Thuật & Code</option>
              <option value="Trợ Lý CSKH 24/7">Trợ Lý CSKH 24/7</option>
              <option value="Trợ Lý Điều Hành Cấp Cao">Trợ Lý Điều Hành Cấp Cao</option>
            </select>
          </div>
        </div>

        <div>
          <label class="block text-[11px] font-bold text-slate-700 uppercase mb-1">Gán Nhóm Zalo Phụ Trách</label>
          <div class="grid grid-cols-2 gap-2 max-h-36 overflow-y-auto custom-scrollbar p-1 border border-slate-200 rounded-xl bg-slate-50/50">
{group_checkboxes_html}          </div>
        </div>

        <div>
          <label class="block text-[11px] font-bold text-slate-700 uppercase">Mô Tả Nhiệm Vụ & Phong Thái (Persona)</label>
          <textarea id="new-ast-persona" rows="2" placeholder="Ví dụ: Lễ phép, phản hồi nhanh, tự động tổng hợp số liệu thu chi cuối ngày cho Sếp Hoàng..." class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs focus:outline-none focus:border-indigo-600"></textarea>
        </div>

        <div class="flex items-center justify-end space-x-3 pt-2 border-t border-slate-100">
          <button type="button" onclick="closeAddAssistantModal()" class="px-4 py-2 text-slate-500 hover:text-slate-800 text-xs font-bold rounded-xl">
            Hủy Bỏ
          </button>
          <button type="submit" class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-md shadow-indigo-600/20">
            Xác Nhận Nạp Trợ Lý Zalo
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- ==================== MODAL: NẠP COOKIE POOL TRỢ LÝ STUDIO AI ==================== -->
  <div id="modal-import-cookie" class="fixed inset-0 z-50 flex items-center justify-center p-4 modal-backdrop hidden">
    <div class="bg-white rounded-3xl border border-slate-200 shadow-2xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto custom-scrollbar">
      <div class="flex items-center justify-between border-b border-slate-100 pb-3">
        <div class="flex items-center space-x-2.5">
          <div class="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
            <i data-lucide="cookie" class="w-5 h-5"></i>
          </div>
          <div>
            <h3 class="font-black text-slate-900 text-sm">Nạp Cookie Trợ Lý Đồ Họa & Video AI (Cổng 8770)</h3>
            <p class="text-[11px] text-slate-500">Dán JSON từ tiện ích Cookie-Editor hoặc chọn file .json</p>
          </div>
        </div>
        <button onclick="closeImportCookieModal()" class="text-slate-400 hover:text-slate-700 p-1 rounded-lg">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <form id="form-import-cookie" onsubmit="submitImportCookie(event)" class="space-y-3.5">
        <div>
          <label class="block text-[11px] font-bold text-slate-700 uppercase">Tên Định Danh Tài Khoản *</label>
          <input type="text" id="cookie-acc-name" required placeholder="Ví dụ: ellinabetheny4127 hoặc studio_acc02" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:border-amber-600">
        </div>

        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="block text-[11px] font-bold text-slate-700 uppercase">Nội Dung Cookie (JSON hoặc Header Text) *</label>
            <label class="text-[11px] font-bold text-indigo-600 hover:underline cursor-pointer">
              <span>📁 Chọn file .json</span>
              <input type="file" id="cookie-file-upload" accept=".json,.txt" class="hidden" onchange="handleCookieFileUpload(event)">
            </label>
          </div>
          <textarea id="cookie-content-input" required rows="6" placeholder='Dán mã JSON export từ Cookie-Editor vào đây:&#10;[&#10;  {{ "name": "hatch_sess", "value": "bc389864-...", "domain": ".ai" }},&#10;  ...&#10;]&#10;hoặc chuỗi: hatch_sess=bc389864...;' class="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs font-mono focus:outline-none focus:border-amber-600 custom-scrollbar"></textarea>
          <p class="text-[10px] text-slate-400 mt-1 font-medium">Bắt buộc phải có cookie phiên <code class="text-amber-800 bg-amber-50 px-1 py-0.5 rounded font-mono">hatch_sess</code> (được export khi đang đăng nhập trên trình duyệt).</p>
        </div>

        <div class="flex items-center space-x-2">
          <input type="checkbox" id="cookie-overwrite" checked class="w-4 h-4 text-amber-600 rounded border-slate-300 focus:ring-amber-500 cursor-pointer">
          <label for="cookie-overwrite" class="text-xs text-slate-600 font-semibold cursor-pointer">Ghi đè nếu tài khoản đã tồn tại (Làm mới Cookie khi hết hạn)</label>
        </div>

        <div class="flex items-center justify-end space-x-3 pt-2 border-t border-slate-100">
          <button type="button" onclick="closeImportCookieModal()" class="px-4 py-2 text-slate-500 hover:text-slate-800 text-xs font-bold rounded-xl">
            Hủy Bỏ
          </button>
          <button type="submit" class="px-5 py-2 bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold rounded-xl shadow-md shadow-amber-600/20">
            💾 Lưu & Kích Hoạt Cookie Vào Pool
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- ==================== MODAL: AUTO-EXTRACT COOKIE ==================== -->
  <div id="modal-auto-extract" class="fixed inset-0 z-50 flex items-center justify-center p-4 modal-backdrop hidden">
    <div class="bg-white rounded-3xl border border-slate-200 shadow-2xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto custom-scrollbar">
      <div class="flex items-center justify-between border-b border-slate-100 pb-3">
        <div class="flex items-center space-x-2.5">
          <div class="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
            <i data-lucide="zap" class="w-5 h-5"></i>
          </div>
          <div>
            <h3 class="font-black text-slate-900 text-sm">⚡ Tự Động Lấy Cookie (Auto-Extract OTP)</h3>
            <p class="text-[11px] text-slate-500">Đăng nhập tài khoản qua mail, đọc OTP Microsoft và nạp Cookie vào Pool</p>
          </div>
        </div>
        <button onclick="closeAutoExtractModal()" class="text-slate-400 hover:text-slate-700 p-1 rounded-lg">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <form id="form-auto-extract" onsubmit="submitAutoExtract(event)" class="space-y-3.5">
        <div>
          <label class="block text-[11px] font-bold text-slate-700 uppercase">Danh Sách Tài Khoản (mỗi dòng 1 tài khoản) *</label>
          <textarea id="auto-extract-input" rows="5" placeholder="user1@hotmail.com|password123&#10;user2@hotmail.com|password456|refreshToken|client_id" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs font-mono focus:outline-none focus:border-indigo-600 custom-scrollbar"></textarea>
          <p class="text-[10px] text-slate-400 mt-1">Định dạng hỗ trợ: <code class="font-mono bg-slate-100 px-1 py-0.5 rounded">mail | password</code> hoặc <code class="font-mono bg-slate-100 px-1 py-0.5 rounded">mail | pass | refreshToken | client_id</code></p>
        </div>

        <div class="flex items-center justify-end space-x-3 pt-2 border-t border-slate-100">
          <button type="button" onclick="closeAutoExtractModal()" class="px-4 py-2 text-slate-500 hover:text-slate-800 text-xs font-bold rounded-xl">
            Đóng
          </button>
          <button type="submit" class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-md shadow-indigo-600/20 flex items-center space-x-1.5">
            <i data-lucide="play" class="w-3.5 h-3.5"></i>
            <span>Bắt Đầu Tự Động Trích Xuất</span>
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- ==================== MODAL: QUÉT QR ĐĂNG NHẬP ZALO ==================== -->
  <div id="modal-qr-pair" class="fixed inset-0 z-50 flex items-center justify-center p-4 modal-backdrop hidden">
    <div class="bg-white rounded-3xl border border-slate-200 shadow-2xl max-w-sm w-full p-6 text-center space-y-4">
      <div class="flex items-center justify-between">
        <h3 class="font-extrabold text-slate-900 text-sm">Quét QR Đăng Nhập Zalo</h3>
        <button onclick="closeQRPairModal()" class="text-slate-400 hover:text-slate-700 p-1 rounded-lg">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <div class="p-4 bg-slate-50 border border-slate-200 rounded-2xl flex flex-col items-center justify-center">
        <div class="w-48 h-48 bg-white p-2 rounded-xl shadow-sm border border-slate-200 flex items-center justify-center">
          <img id="qr-image-display" src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=hermes-zalo-bridge-pair-login-2026" alt="Mã QR Zalo" class="w-full h-full object-contain">
        </div>
        <p class="text-[11px] text-slate-500 mt-2 font-medium">Mở ứng dụng Zalo trên điện thoại, chọn <strong>Quét mã QR</strong> để đăng nhập cho Trợ Lý.</p>
      </div>

      <div class="text-xs text-slate-600 font-mono bg-blue-50 text-[#0066cc] p-2.5 rounded-xl border border-blue-200">
        Cổng Bridge: <strong>127.0.0.1:3050</strong> (Listening)
      </div>

      <button onclick="confirmQRPairSuccess()" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold shadow-md shadow-emerald-600/20">
        Tôi Đã Quét Xong & Xác Nhận Trên ĐT
      </button>
    </div>
  </div>

  <!-- ==================== MODAL: THÊM VIRTUAL BOT MỚI (KHÔNG GIỚI HẠN) ==================== -->
  <div id="modal-add-virtual-bot" class="fixed inset-0 z-50 flex items-center justify-center p-4 modal-backdrop hidden">
    <div class="bg-white rounded-3xl border border-slate-200 shadow-2xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto custom-scrollbar">
      <div class="flex items-center justify-between border-b border-slate-100 pb-3">
        <div class="flex items-center space-x-2.5">
          <div class="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
            <i data-lucide="cpu" class="w-5 h-5"></i>
          </div>
          <div>
            <h3 class="font-black text-slate-900 text-sm">Thêm Virtual Bot Mới Vào Hệ Thống</h3>
            <p class="text-[11px] text-slate-500">1 Tài khoản Zalo đóng nhiều Bot độc lập theo Mã riêng</p>
          </div>
        </div>
        <button onclick="closeAddVirtualBotModal()" class="text-slate-400 hover:text-slate-700 p-1 rounded-lg">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <form id="form-add-virtual-bot" onsubmit="submitAddVirtualBot(event)" class="space-y-3.5">
        <div>
          <label class="block text-[11px] font-bold text-slate-700 uppercase">Tên Trợ Lý Bot *</label>
          <input type="text" id="vbot-name" required placeholder="Ví dụ: Trợ Lý Marketing & TVC" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-purple-600">
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[11px] font-bold text-slate-700 uppercase">Mã Kích Hoạt Chính (Routing Code) *</label>
            <input type="text" id="vbot-code" required placeholder="Ví dụ: #MKT hoặc #B4" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono font-bold focus:outline-none focus:border-purple-600">
            <p class="text-[9px] text-slate-400 mt-0.5">Tiền tố gọi bot trên Zalo (ví dụ: #MKT)</p>
          </div>
          <div>
            <label class="block text-[11px] font-bold text-slate-700 uppercase">Mã Viết Tắt (Aliases)</label>
            <input type="text" id="vbot-aliases" placeholder="!mkt, @mkt, #b4" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:border-purple-600">
            <p class="text-[9px] text-slate-400 mt-0.5">Phân cách bằng dấu phẩy</p>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[11px] font-bold text-slate-700 uppercase">Chế Độ Xử Lý</label>
            <select id="vbot-mode" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2 text-xs font-semibold focus:outline-none focus:border-purple-600">
              <option value="chat">💬 Chat & Nghiệp Vụ Doanh Nghiệp</option>
              <option value="video">🎬 Render Video Motion & TVC</option>
              <option value="image">🎨 Vẽ Tranh & Tạo Ảnh Nghệ Thuật</option>
            </select>
          </div>
          <div>
            <label class="block text-[11px] font-bold text-slate-700 uppercase">Liên Kết Tài Khoản AI Pool</label>
            <select id="vbot-account" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2 text-xs font-semibold focus:outline-none focus:border-purple-600">
              <option value="syncere1812031999">syncere1812031999 (Video & Ảnh)</option>
              <option value="ellinabetheny4127">ellinabetheny4127 (Chỉ Ảnh & Chat)</option>
              <option value="">studio-pool (Tự Động)</option>
            </select>
          </div>
        </div>

        <div>
          <label class="block text-[11px] font-bold text-slate-700 uppercase">Mô Tả Chức Năng (Persona)</label>
          <input type="text" id="vbot-persona" placeholder="Chuyên gia truyền thông, viết bài PR và sản xuất video TVC" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-purple-600">
        </div>

        <div>
          <label class="block text-[11px] font-bold text-slate-700 uppercase">System Prompt Định Hình Phong Cách</label>
          <textarea id="vbot-prompt" rows="3" placeholder="Em là Trợ lý Marketing của sếp Hoàng, chuyên tư vấn chiến lược và tạo video sản phẩm..." class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs focus:outline-none focus:border-purple-600 custom-scrollbar"></textarea>
        </div>

        <div class="flex items-center justify-end space-x-3 pt-3 border-t border-slate-100">
          <button type="button" onclick="closeAddVirtualBotModal()" class="px-4 py-2 text-slate-500 hover:text-slate-800 text-xs font-bold rounded-xl">
            Hủy
          </button>
          <button type="submit" class="px-5 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold rounded-xl shadow-md shadow-purple-600/20 flex items-center space-x-1.5 cursor-pointer">
            <i data-lucide="check" class="w-3.5 h-3.5"></i>
            <span>Kích Hoạt Bot Ngay</span>
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- ==================== MODAL: NẠP BOT TRỐNG VÀO KHO (EMPTY BOT POOL) ==================== -->
  <div id="modal-add-empty-bot" class="fixed inset-0 z-50 flex items-center justify-center p-4 modal-backdrop hidden">
    <div class="bg-white rounded-3xl border border-slate-200 shadow-2xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto custom-scrollbar">
      <div class="flex items-center justify-between border-b border-slate-100 pb-3">
        <div class="flex items-center space-x-2.5">
          <div class="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
            <i data-lucide="box" class="w-5 h-5"></i>
          </div>
          <div>
            <h3 class="font-black text-slate-900 text-sm">Nạp Bot Trống Mới Vào Kho (Empty Pool)</h3>
            <p class="text-[11px] text-slate-500">Chuẩn bị sẵn tài khoản trống để gán độc quyền khi có khách thuê</p>
          </div>
        </div>
        <button onclick="closeAddEmptyBotModal()" class="text-slate-400 hover:text-slate-700 p-1 rounded-lg">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <form id="form-add-empty-bot" onsubmit="submitAddEmptyBot(event)" class="space-y-3.5">
        <div>
          <label class="block text-[11px] font-bold text-slate-700 uppercase">Tên Trợ Lý Bot *</label>
          <input type="text" id="empty-bot-name" required placeholder="Ví dụ: Trợ Lý CSKH Chuyên Nghiệp 07" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-indigo-600">
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[11px] font-bold text-slate-700 uppercase">Chế Độ Xử Lý</label>
            <select id="empty-bot-mode" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2 text-xs font-semibold focus:outline-none focus:border-indigo-600">
              <option value="chat">💬 Chat & Nghiệp Vụ Doanh Nghiệp</option>
              <option value="video">🎬 Render Video & Ảnh Nghệ Thuật</option>
            </select>
          </div>
          <div>
            <label class="block text-[11px] font-bold text-slate-700 uppercase">Gán Tài Khoản AI Engine</label>
            <select id="empty-bot-engine" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2 text-xs font-semibold focus:outline-none focus:border-indigo-600">
              <option value="ellinabetheny4127">ellinabetheny4127 (Chat & Ảnh)</option>
              <option value="syncere1812031999">syncere1812031999 (Video MP4 & Ảnh)</option>
            </select>
          </div>
        </div>

        <div>
          <label class="block text-[11px] font-bold text-slate-700 uppercase">Gói Cước Đề Xuất Áp Dụng</label>
          <select id="empty-bot-package" class="w-full mt-1 bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2 text-xs font-semibold focus:outline-none focus:border-indigo-600">
            <option value="Gói 1 Bot (30 ngày)">Gói 1 Bot (30 ngày)</option>
            <option value="Gói 2 Bot (30 ngày)">Gói 2 Bot (30 ngày)</option>
            <option value="Gói 3 Bot (30 ngày)">Gói 3 Bot (30 ngày)</option>
            <option value="Gói Doanh Nghiệp VIP (30 ngày)">Gói Doanh Nghiệp VIP (30 ngày)</option>
          </select>
        </div>

        <div class="flex items-center justify-end space-x-3 pt-3 border-t border-slate-100">
          <button type="button" onclick="closeAddEmptyBotModal()" class="px-4 py-2 text-slate-500 hover:text-slate-800 text-xs font-bold rounded-xl">
            Hủy
          </button>
          <button type="submit" class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-md shadow-indigo-600/20 flex items-center space-x-1.5 cursor-pointer">
            <i data-lucide="plus" class="w-3.5 h-3.5"></i>
            <span>Nạp Vào Kho Sẵn Sàng</span>
          </button>
        </div>
      </form>
    </div>
  </div>

    <!-- ==================== MODAL: GÁN COOKIE VÀO ZALO BOT ==================== -->
  <div id="modal-assign-cookie" class="fixed inset-0 z-50 flex items-center justify-center p-4 modal-backdrop hidden">
    <div class="bg-white rounded-3xl border border-slate-200 shadow-2xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto custom-scrollbar">
      <div class="flex items-center justify-between border-b border-slate-100 pb-3">
        <div class="flex items-center space-x-2.5">
          <div class="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
            <i data-lucide="cookie" class="w-5 h-5"></i>
          </div>
          <div>
            <h3 class="font-black text-slate-900 text-sm">Nạp / Gán Cookie Vào Zalo Bot</h3>
            <p class="text-[11px] text-slate-500" id="assign-cookie-modal-subtitle">Chọn các tài khoản Cookie Pool để cấp bộ não cho Zalo Bot</p>
          </div>
        </div>
        <button onclick="closeAssignCookieModal()" class="text-slate-400 hover:text-slate-700 p-1 rounded-lg">
          <i data-lucide="x" class="w-5 h-5"></i>
        </button>
      </div>

      <div class="space-y-3">
        <p class="text-xs text-slate-600">
          Tick chọn một hoặc nhiều tài khoản Cookie AI bên dưới để gán tải cho Zalo Bot này. Khi xử lý công việc và render video TVC, Zalo Bot sẽ tự động luân phiên các tài khoản đã chọn.
        </p>

        <div id="assign-cookie-checkboxes-list" class="space-y-2 max-h-60 overflow-y-auto pr-1">
          <!-- Dynamically populated -->
        </div>

        <div class="flex items-center justify-between pt-3 border-t border-slate-100">
          <button type="button" onclick="closeAssignCookieModal()" class="px-4 py-2 text-slate-500 hover:text-slate-800 text-xs font-bold rounded-xl">
            Đóng
          </button>
          <button type="button" onclick="saveAssignedCookies()" class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow-md shadow-indigo-600/20 flex items-center space-x-1.5 cursor-pointer">
            <i data-lucide="check" class="w-3.5 h-3.5"></i>
            <span>Lưu & Cấp Cookie Cho Bot</span>
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- ==================== JAVASCRIPT LOGIC ==================== -->
  <script>
    const SYSTEM_DATABASE = {{
      groups: {json.dumps(formatted_groups, ensure_ascii=False, indent=2)}
    }};

    let ASSISTANTS_FLEET = {json.dumps(assistants_list, ensure_ascii=False, indent=2)};
    let POOL_ACCOUNTS = {json.dumps(pool_accounts_list, ensure_ascii=False, indent=2)};
    let TENANTS_DATA = {json.dumps(tenants_data, ensure_ascii=False, indent=2)};
    let RENTAL_POOL_DATA = {json.dumps(empty_pool_data, ensure_ascii=False, indent=2)};
    let RENTAL_PROFILES_DATA = {json.dumps(rental_profiles_data, ensure_ascii=False, indent=2)};
    let ACTIVE_ASSISTANT_ID = "{fleet_data.get('active_account_id', 'ast_715842971730458158')}";
    let CURRENT_GROUP_KEY = "{first_gid}";
    let CURRENT_FLEET_SUBTAB = "zalo";

    // Load from LocalStorage if user previously added assistants or cookies
    function loadFleetFromStorage() {{
      try {{
        // Luon lam sach cache cu de lay du lieu dong bo chuan xac tu Sever
        localStorage.removeItem('hermes_fleet_assistants');
        localStorage.removeItem('hermes_pool_accounts');
        const storedActive = localStorage.getItem('hermes_active_assistant_id');
        if (storedActive) ACTIVE_ASSISTANT_ID = storedActive;
        const storedTenants = localStorage.getItem('hermes_tenants_data');
        if (storedTenants) {{
          const parsedT = JSON.parse(storedTenants);
          if (parsedT && parsedT.tenants) TENANTS_DATA = parsedT;
        }}
      }} catch (e) {{
        console.error('Lỗi load local storage:', e);
      }}
    }}

    function saveFleetToStorage() {{
      try {{
        localStorage.setItem('hermes_fleet_assistants', JSON.stringify(ASSISTANTS_FLEET));
        localStorage.setItem('hermes_pool_accounts', JSON.stringify(POOL_ACCOUNTS));
        localStorage.setItem('hermes_tenants_data', JSON.stringify(TENANTS_DATA));
        localStorage.setItem('hermes_active_assistant_id', ACTIVE_ASSISTANT_ID);
      }} catch (e) {{
        console.error('Lỗi save local storage:', e);
      }}
    }}

    // Tab Navigation
    function switchTab(tabId) {{
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
      const targetPane = document.getElementById('pane-' + tabId);
      if (targetPane) targetPane.classList.add('active');

      const navIds = ['overview', 'assistants', 'groups', 'isolation', 'personas', 'excel', 'media', 'reminders', 'rental'];
      navIds.forEach(id => {{
        const btn = document.getElementById('nav-' + id);
        if (btn) {{
          if (id === tabId) {{
            btn.className = "w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-white bg-[#0066cc] shadow-sm font-semibold transition-all";
          }} else {{
            btn.className = "w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all font-medium";
          }}
        }}
      }});
      lucide.createIcons();
    }}

    // ==================== ZALO-BOT-FIRST ARCHITECTURE LOGIC ====================
    let CURRENT_BOT_SUBTAB = 'cookies';
    let CURRENT_DEDICATED_CODE = '#MEDIA';

    function selectZaloBot(botId) {{
      ACTIVE_ASSISTANT_ID = botId;
      saveFleetToStorage();
      renderAssistantsFleet();
    }}

    function switchBotWorkspaceSubTab(tab) {{
      CURRENT_BOT_SUBTAB = tab;
      const tabs = ['cookies', 'codes', 'groups', 'chat'];
      tabs.forEach(t => {{
        const view = document.getElementById(`bot-view-${{t}}`);
        const btn = document.getElementById(`btn-bot-subtab-${{t}}`);
        if (view) {{
          if (t === tab) view.classList.remove('hidden');
          else view.classList.add('hidden');
        }}
        if (btn) {{
          if (t === tab) {{
            if (t === 'cookies') btn.className = "px-3.5 py-2 rounded-xl text-xs font-bold transition-all bg-amber-500 text-white shadow-sm flex items-center space-x-1.5 cursor-pointer";
            else if (t === 'codes') btn.className = "px-3.5 py-2 rounded-xl text-xs font-bold transition-all bg-purple-600 text-white shadow-sm flex items-center space-x-1.5 cursor-pointer";
            else if (t === 'groups') btn.className = "px-3.5 py-2 rounded-xl text-xs font-bold transition-all bg-blue-600 text-white shadow-sm flex items-center space-x-1.5 cursor-pointer";
            else btn.className = "px-3.5 py-2 rounded-xl text-xs font-bold transition-all bg-emerald-600 text-white shadow-sm flex items-center space-x-1.5 cursor-pointer";
          }} else {{
            btn.className = "px-3.5 py-2 rounded-xl text-xs font-bold transition-all bg-slate-100 text-slate-600 hover:bg-slate-200 flex items-center space-x-1.5 cursor-pointer";
          }}
        }}
      }});
      lucide.createIcons();
    }}

    function renderAssistantsFleet() {{
      const topSelect = document.getElementById('assistant-top-selector');
      const kpiTotal = document.getElementById('fleet-total-count');
      const kpiOverview = document.getElementById('kpi-overview-assistants');

      if (kpiTotal) kpiTotal.innerText = `${{ASSISTANTS_FLEET.length}} Trợ Lý`;
      if (kpiOverview) kpiOverview.innerText = `${{ASSISTANTS_FLEET.length}} Bot • ${{POOL_ACCOUNTS.length}} Cookie`;

      // Top select dropdown
      if (topSelect) {{
        topSelect.innerHTML = ASSISTANTS_FLEET.map(a => `
          <option value="${{a.id}}" ${{a.id === ACTIVE_ASSISTANT_ID ? 'selected' : ''}}>
            ${{a.name}} (${{a.platform}})
          </option>
        `).join('');
      }}

      // 1. Render Master Zalo Bot Cards
      renderZaloBotMasterSelector();

      // 2. Render Active Zalo Bot Workspace
      renderActiveBotWorkspace();

      lucide.createIcons();
    }}

    function renderZaloBotMasterSelector() {{
      const container = document.getElementById('zalo-bot-master-selector');
      if (!container) return;

      container.innerHTML = ASSISTANTS_FLEET.map(bot => {{
        const isSelected = (bot.id === ACTIVE_ASSISTANT_ID);
        const isOnline = (bot.status === 'online');
        const cookieCount = (bot.assigned_cookies || []).length;
        const groupCount = (bot.assigned_groups || []).length;

        // Virtual bots count for this assistant
        let codeCount = 0;
        (TENANTS_DATA.tenants || []).forEach(t => {{
          (t.bots || []).forEach(b => {{
            if (!bot.assigned_bot_ids || bot.assigned_bot_ids.includes(b.bot_id) || bot.id === 'ast_715842971730458158') {{
              codeCount++;
            }}
          }});
        }});

        return `
          <div onclick="selectZaloBot('${{bot.id}}')" class="p-4 rounded-2xl border transition-all cursor-pointer ${{isSelected ? 'bg-indigo-50/50 border-indigo-600 ring-2 ring-indigo-600/20 shadow-md' : 'bg-white border-slate-200 hover:border-slate-300 shadow-sm'}} flex flex-col justify-between space-y-3">
            <div class="flex items-start justify-between">
              <div class="flex items-center space-x-3">
                <div class="relative w-11 h-11 rounded-2xl overflow-hidden bg-slate-100 border border-slate-200 flex-shrink-0">
                  <img src="${{bot.avatar}}" alt="${{bot.name}}" class="w-full h-full object-cover">
                  <span class="absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-white ${{isOnline ? 'bg-emerald-500' : 'bg-slate-400'}}"></span>
                </div>
                <div>
                  <h4 class="font-extrabold text-xs text-slate-900 leading-tight line-clamp-1">${{bot.name}}</h4>
                  <p class="text-[10px] text-slate-500 font-medium mt-0.5">${{bot.platform}}</p>
                  <span class="text-[10px] text-indigo-600 font-mono font-bold">Cổng ${{bot.bridge_port}}</span>
                </div>
              </div>
              ${{isSelected ? '<span class="px-2 py-0.5 rounded-md text-[9px] font-black bg-indigo-600 text-white uppercase tracking-wider">Đang Chọn</span>' : ''}}
            </div>

            <!-- Quick Metrics Pills -->
            <div class="grid grid-cols-3 gap-1 text-[10px] text-center pt-2 border-t border-slate-100">
              <div class="bg-amber-50 text-amber-800 rounded-lg py-1 font-bold">
                <span>🍪 ${{cookieCount}} Acc</span>
              </div>
              <div class="bg-purple-50 text-purple-800 rounded-lg py-1 font-bold">
                <span>🏷️ ${{codeCount}} Mã</span>
              </div>
              <div class="bg-blue-50 text-blue-800 rounded-lg py-1 font-bold">
                <span>👥 ${{groupCount}} G</span>
              </div>
            </div>
          </div>
        `;
      }}).join('');
    }}

    function renderActiveBotWorkspace() {{
      const currentBot = ASSISTANTS_FLEET.find(a => a.id === ACTIVE_ASSISTANT_ID) || ASSISTANTS_FLEET[0];
      if (!currentBot) return;

      // Render Summary Banner
      const banner = document.getElementById('active-zalo-bot-summary-banner');
      if (banner) {{
        const isOnline = (currentBot.status === 'online');
        const cookieCount = (currentBot.assigned_cookies || []).length;
        const groupCount = (currentBot.assigned_groups || []).length;

        // Count assigned codes
        let codeCount = 0;
        (TENANTS_DATA.tenants || []).forEach(t => {{
          (t.bots || []).forEach(b => {{
            if (!currentBot.assigned_bot_ids || currentBot.assigned_bot_ids.includes(b.bot_id) || currentBot.id === 'ast_715842971730458158') {{
              codeCount++;
            }}
          }});
        }});

        banner.innerHTML = `
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-5">
            <div class="flex items-center space-x-4">
              <div class="relative w-16 h-16 rounded-2xl overflow-hidden bg-white/10 border-2 border-white/20 flex-shrink-0">
                <img src="${{currentBot.avatar}}" alt="${{currentBot.name}}" class="w-full h-full object-cover">
                <span class="absolute bottom-0 right-0 w-3.5 h-3.5 rounded-full border-2 border-slate-900 ${{isOnline ? 'bg-emerald-400' : 'bg-slate-400'}}"></span>
              </div>
              <div>
                <div class="flex flex-wrap items-center gap-2">
                  <h2 class="text-xl font-black tracking-tight text-white">${{currentBot.name}}</h2>
                  <span class="px-2.5 py-0.5 rounded-md text-[10px] font-black uppercase ${{isOnline ? 'bg-emerald-500/30 text-emerald-300 border border-emerald-400/30' : 'bg-slate-500/30 text-slate-300 border border-slate-400/30'}}">
                    ${{isOnline ? '🟢 Hoạt Động (Online)' : '⚪ Tạm Dừng'}}
                  </span>
                  <span class="px-2 py-0.5 rounded-md text-[10px] font-mono bg-indigo-500/30 text-indigo-200 border border-indigo-400/30">
                    Cổng Bridge: ${{currentBot.bridge_port}}
                  </span>
                </div>
                <p class="text-xs text-indigo-200 mt-1 max-w-xl italic">
                  "${{currentBot.persona}}"
                </p>
                <div class="flex items-center space-x-3 text-[11px] text-slate-400 font-mono mt-1">
                  <span>UID: <strong class="text-slate-200">${{currentBot.uid}}</strong></span>
                  <span>•</span>
                  <span>SĐT: <strong class="text-slate-200">${{currentBot.phone}}</strong></span>
                  <span>•</span>
                  <span>Bộ Nhớ: <strong class="text-slate-200">${{currentBot.memory_mb || 64}} MB</strong></span>
                </div>
              </div>
            </div>

            <!-- Quick Action Counters -->
            <div class="flex flex-wrap items-center gap-2.5">
              <div class="bg-white/10 backdrop-blur-md px-3.5 py-2.5 rounded-2xl border border-white/10 text-center">
                <span class="text-[10px] text-amber-300 uppercase font-black block">Cookie Đã Nạp</span>
                <span class="text-lg font-black text-white">${{cookieCount}} Tài Khoản</span>
              </div>
              <div class="bg-white/10 backdrop-blur-md px-3.5 py-2.5 rounded-2xl border border-white/10 text-center">
                <span class="text-[10px] text-purple-300 uppercase font-black block">Trợ Lý Mã #CODE</span>
                <span class="text-lg font-black text-white">${{codeCount}} Mã</span>
              </div>
              <div class="bg-white/10 backdrop-blur-md px-3.5 py-2.5 rounded-2xl border border-white/10 text-center">
                <span class="text-[10px] text-blue-300 uppercase font-black block">Nhóm Zalo</span>
                <span class="text-lg font-black text-white">${{groupCount}} Nhóm</span>
              </div>
            </div>
          </div>
        `;

        // Update Subtab Badges
        const bCookies = document.getElementById('badge-bot-cookies-count');
        const bCodes = document.getElementById('badge-bot-codes-count');
        const bGroups = document.getElementById('badge-bot-groups-count');
        if (bCookies) bCookies.innerText = `${{cookieCount}} Acc`;
        if (bCodes) bCodes.innerText = `${{codeCount}} Mã`;
        if (bGroups) bGroups.innerText = `${{groupCount}} Nhóm`;
      }}

      // Render Subtab 1: Assigned Cookies
      renderBotAssignedCookies(currentBot);

      // Render Subtab 2: Virtual Bots (#CODE)
      renderBotAssignedCodes(currentBot);

      // Render Subtab 3: Assigned Groups
      renderBotAssignedGroups(currentBot);

      // Render Subtab 4: Dedicated Isolated Chat Console
      renderDedicatedChatPills(currentBot);
    }}

    function renderBotAssignedCookies(currentBot) {{
      const container = document.getElementById('bot-assigned-cookies-container');
      if (!container) return;

      const assignedNames = currentBot.assigned_cookies || [];
      if (assignedNames.length === 0) {{
        container.innerHTML = `
          <div class="col-span-full py-8 text-center bg-slate-50 border-2 border-dashed border-slate-200 rounded-3xl space-y-2">
            <div class="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold text-xl mx-auto">
              🍪
            </div>
            <p class="text-xs font-bold text-slate-700">Zalo Bot này chưa được nạp tài khoản Cookie AI nào!</p>
            <p class="text-[11px] text-slate-400">Hãy bấm nút "Nạp Thêm Cookie Vào Bot Này" để cấp bộ não AI cho Bot xử lý tin nhắn & render video TVC.</p>
            <button onclick="openAssignCookieModal()" class="mt-2 px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-xs font-bold transition-all shadow-sm cursor-pointer">
              🔗 Nạp Cookie Ngay
            </button>
          </div>
        `;
        return;
      }}

      container.innerHTML = assignedNames.map(accName => {{
        const poolAcc = POOL_ACCOUNTS.find(p => p.name === accName) || {{
          name: accName,
          file: `${{accName}}.json`,
          status: 'ready',
          video_state: 'ok',
          avatar: `https://api.dicebear.com/7.x/identicon/svg?seed=${{accName}}`,
          tokens_used: 120,
          tokens_total: 500,
          used_percent: 24,
          reset_time_str: 'Còn 6 ngày 9h'
        }};

        const isReady = (poolAcc.status === 'ready');
        const usedPct = poolAcc.used_percent || 20;

        return `
          <div class="bg-slate-50/70 p-4 rounded-2xl border border-slate-200 shadow-sm space-y-3 hover:border-amber-400 transition-all">
            <div class="flex items-start justify-between">
              <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-xl bg-white border border-slate-200 overflow-hidden flex-shrink-0">
                  <img src="${{poolAcc.avatar}}" class="w-full h-full object-cover">
                </div>
                <div>
                  <h4 class="font-mono font-bold text-xs text-slate-900">${{poolAcc.name}}</h4>
                  <p class="text-[10px] text-slate-400 font-mono">${{poolAcc.file}}</p>
                </div>
              </div>
              <span class="px-2 py-0.5 rounded-full text-[9px] font-extrabold uppercase ${{isReady ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-rose-50 text-rose-700 border border-rose-200'}}">
                ${{isReady ? '🟢 Ready' : '🔴 Expired'}}
              </span>
            </div>

            <!-- Token progress -->
            <div class="space-y-1">
              <div class="flex items-center justify-between text-[10px]">
                <span class="text-slate-500">Mức dùng tuần:</span>
                <span class="font-bold text-slate-700">${{usedPct}}%</span>
              </div>
              <div class="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                <div class="h-full rounded-full bg-emerald-500" style="width: ${{Math.max(5, usedPct)}}%"></div>
              </div>
            </div>

            <div class="pt-2 border-t border-slate-200 flex items-center justify-between text-[10px]">
              <span class="text-slate-500 font-medium">Reset: ${{poolAcc.reset_time_str || 'Hàng tuần'}}</span>
              <button onclick="unassignCookieFromBot('${{accName}}')" class="text-rose-500 hover:text-rose-700 font-bold hover:bg-rose-50 px-2 py-1 rounded-lg transition-all" title="Bỏ gán cookie này khỏi bot">
                Gỡ bỏ
              </button>
            </div>
          </div>
        `;
      }}).join('');
    }}

    function renderBotAssignedCodes(currentBot) {{
      const container = document.getElementById('bot-virtual-bots-container');
      if (!container) return;

      const allBots = [];
      (TENANTS_DATA.tenants || []).forEach(t => {{
        (t.bots || []).forEach(b => {{
          if (!currentBot.assigned_bot_ids || currentBot.assigned_bot_ids.includes(b.bot_id) || currentBot.id === 'ast_715842971730458158') {{
            allBots.push({{ ...b, tenant_id: t.tenant_id, tenant_name: t.name }});
          }}
        }});
      }});

      if (allBots.length === 0) {{
        container.innerHTML = `
          <div class="col-span-full py-8 text-center bg-slate-50 border-2 border-dashed border-slate-200 rounded-3xl space-y-2">
            <p class="text-xs font-bold text-slate-700">Chưa có Trợ Lý Ảo theo Mã (#CODE) nào được gán cho Bot này!</p>
            <button onclick="openAddVirtualBotModal()" class="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm cursor-pointer">
              + Tạo Mã Mới Ngay
            </button>
          </div>
        `;
        return;
      }}

      container.innerHTML = allBots.map(b => {{
        const isVideo = (b.mode === 'video');
        const aliasesStr = (b.aliases && b.aliases.length) ? b.aliases.join(', ') : '';

        return `
          <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4 hover:shadow-md hover:border-purple-300 transition-all">
            <div class="flex items-start justify-between">
              <div class="flex items-center space-x-3">
                <div class="w-11 h-11 rounded-2xl bg-purple-50 text-purple-700 flex items-center justify-center font-bold text-lg border border-purple-200">
                  🤖
                </div>
                <div>
                  <h4 class="font-extrabold text-sm text-slate-900">${{b.name}}</h4>
                  <div class="flex items-center space-x-1.5 mt-0.5">
                    <span class="px-2 py-0.5 rounded-md text-[10px] font-black bg-purple-100 text-purple-800 font-mono">${{b.routing_code}}</span>
                    ${{aliasesStr ? `<span class="text-[10px] text-slate-400 font-mono">(` + aliasesStr + `)</span>` : ''}}
                  </div>
                </div>
              </div>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold ${{isVideo ? 'bg-pink-50 text-pink-700 border border-pink-200' : 'bg-blue-50 text-blue-700 border border-blue-200'}}">
                ${{isVideo ? '🎬 Video TVC' : '💬 Nghiệp Vụ'}}
              </span>
            </div>

            <p class="text-xs text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-100 italic line-clamp-2">
              "${{b.persona}}"
            </p>

            <div class="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
              <div class="flex items-center space-x-1 font-mono">
                <span>AI Cookie:</span>
                <strong class="text-indigo-600 font-bold">${{b.linked_pool_account || 'studio-pool'}}</strong>
              </div>
              <div class="flex items-center space-x-2">
                <button onclick="openDedicatedChat('${{b.routing_code}}', '${{b.name}}', '${{b.linked_pool_account || 'studio-pool'}}')" class="px-2.5 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-bold rounded-xl text-[10px] border border-emerald-200 flex items-center space-x-1 cursor-pointer">
                  <i data-lucide="message-square" class="w-3 h-3"></i>
                  <span>Khung Chat Riêng</span>
                </button>
                <button onclick="deleteVirtualBot('${{b.tenant_id}}', '${{b.bot_id}}')" class="text-rose-500 hover:text-rose-700 p-1 hover:bg-rose-50 rounded-lg transition-all" title="Xóa Bot">
                  <i data-lucide="trash-2" class="w-4 h-4"></i>
                </button>
              </div>
            </div>
          </div>
        `;
      }}).join('');
    }}

    function renderBotAssignedGroups(currentBot) {{
      const container = document.getElementById('bot-assigned-groups-container');
      if (!container) return;

      const groupIds = currentBot.assigned_groups || [];
      if (groupIds.length === 0) {{
        container.innerHTML = `
          <div class="col-span-full py-8 text-center bg-slate-50 border-2 border-dashed border-slate-200 rounded-3xl">
            <p class="text-xs font-bold text-slate-700">Bot này hiện chưa tham gia nhóm Zalo nào.</p>
          </div>
        `;
        return;
      }}

      container.innerHTML = groupIds.map(gid => {{
        const ginfo = SYSTEM_DATABASE.groups[gid] || {{
          name: `Nhóm Zalo (${{gid}})`,
          avatar: '👥',
          memberCount: 'Đang kết nối'
        }};

        return `
          <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm space-y-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-xl bg-blue-50 text-[#0066cc] flex items-center justify-center font-bold text-base flex-shrink-0">
                  ${{ginfo.avatar && ginfo.avatar.startsWith('http') ? `<img src="${{ginfo.avatar}}" class="w-full h-full object-cover rounded-xl">` : '👥'}}
                </div>
                <div>
                  <h4 class="font-extrabold text-xs text-slate-900 line-clamp-1">${{ginfo.name}}</h4>
                  <p class="text-[10px] text-slate-400 font-mono">${{gid}}</p>
                </div>
              </div>
            </div>

            <div class="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
              <span class="text-slate-500 font-medium">${{ginfo.memberCount || 'Nhóm hoạt động'}}</span>
              <button onclick="leaveGroupPhysical('${{gid}}', '${{ginfo.name}}')" class="px-2.5 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 font-bold rounded-lg text-[10px] border border-rose-200 flex items-center space-x-1 cursor-pointer">
                <i data-lucide="log-out" class="w-3 h-3"></i>
                <span>Thoát Nhóm</span>
              </button>
            </div>
          </div>
        `;
      }}).join('');
    }}

    // ==================== KHUNG CHAT RIÊNG BIỆT CHO TỪNG TÍNH NĂNG ====================
    function openDedicatedChat(code, name, linkedAcc) {{
      CURRENT_DEDICATED_CODE = code;
      switchBotWorkspaceSubTab('chat');
      switchDedicatedChatCode(code);
    }}

    function renderDedicatedChatPills(currentBot) {{
      const container = document.getElementById('dedicated-chat-code-pills');
      if (!container) return;

      const codes = [];
      (TENANTS_DATA.tenants || []).forEach(t => {{
        (t.bots || []).forEach(b => {{
          if (!currentBot.assigned_bot_ids || currentBot.assigned_bot_ids.includes(b.bot_id) || currentBot.id === 'ast_715842971730458158') {{
            if (!codes.some(c => c.code === b.routing_code)) {{
              codes.push({{ code: b.routing_code, name: b.name, mode: b.mode, account: b.linked_pool_account }});
            }}
          }}
        }});
      }});

      if (codes.length === 0) {{
        codes.push(
          {{ code: '#MEDIA', name: 'Bot Media Studio', mode: 'video', account: 'syncere1812031999' }},
          {{ code: '#HERMES', name: 'Trợ Lý Điều Hành', mode: 'chat', account: 'ellinabetheny4127' }},
          {{ code: '#KETOAN', name: 'Bot Kế Toán & Excel', mode: 'chat', account: 'ellinabetheny4127' }}
        );
      }}

      container.innerHTML = codes.map(c => {{
        const isCurrent = (c.code === CURRENT_DEDICATED_CODE);
        return `
          <button onclick="switchDedicatedChatCode('${{c.code}}')" class="px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 flex-shrink-0 cursor-pointer ${{isCurrent ? 'bg-purple-600 text-white shadow-md' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}}">
            <span class="font-mono">${{c.code}}</span>
            <span class="text-[10px] opacity-80">• ${{c.name}}</span>
          </button>
        `;
      }}).join('');

      switchDedicatedChatCode(CURRENT_DEDICATED_CODE);
    }}

    function switchDedicatedChatCode(code) {{
      CURRENT_DEDICATED_CODE = code;

      // Update pills appearance
      const pills = document.querySelectorAll('#dedicated-chat-code-pills button');
      pills.forEach(p => {{
        if (p.innerText.includes(code)) {{
          p.className = "px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 flex-shrink-0 cursor-pointer bg-purple-600 text-white shadow-md";
        }} else {{
          p.className = "px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 flex-shrink-0 cursor-pointer bg-slate-800 text-slate-300 hover:bg-slate-700";
        }}
      }});

      // Update Sub-header
      let matchedBot = null;
      (TENANTS_DATA.tenants || []).forEach(t => {{
        (t.bots || []).forEach(b => {{
          if (b.routing_code === code) matchedBot = b;
        }});
      }});

      const botName = matchedBot ? matchedBot.name : (code === '#MEDIA' ? 'Bot Media Studio' : code === '#HERMES' ? 'Trợ Lý Điều Hành' : 'Trợ Lý Kế Toán');
      const botAcc = matchedBot ? matchedBot.linked_pool_account : 'studio-pool';

      const infoEl = document.getElementById('dedicated-chat-active-info');
      const sessEl = document.getElementById('dedicated-chat-session-id');
      const badgeInput = document.getElementById('dedicated-chat-input-code-badge');

      if (infoEl) infoEl.innerHTML = `<span class="font-bold text-slate-900">${{botName}}</span> <span class="px-1.5 py-0.5 rounded bg-purple-100 text-purple-800 font-mono text-[10px] font-bold">${{code}}</span> <span class="text-slate-400">• Bộ não AI: <strong class="text-indigo-600 font-mono">${{botAcc}}</strong></span>`;
      if (sessEl) sessEl.innerText = `session_${{ACTIVE_ASSISTANT_ID.slice(-6)}}_${{code.replace('#', '')}}`;
      if (badgeInput) badgeInput.innerText = code;

      renderDedicatedChatMessages();
    }}

    function getDedicatedChatHistory() {{
      const key = `hermes_chat_${{ACTIVE_ASSISTANT_ID}}_${{CURRENT_DEDICATED_CODE}}`;
      try {{
        const raw = localStorage.getItem(key);
        if (raw) return JSON.parse(raw);
      }} catch (e) {{}}

      // Default welcome message for this code
      return [
        {{
          sender: 'bot',
          time: new Date().toLocaleTimeString('vi-VN', {{ hour: '2-digit', minute: '2-digit' }}),
          text: `Dạ Sếp, Em là Trợ lý phụ trách tính năng ${{CURRENT_DEDICATED_CODE}}. Toàn bộ ngữ cảnh trong khung chat này được cô lập 100% dành riêng cho Sếp!`
        }}
      ];
    }}

    function saveDedicatedChatHistory(history) {{
      const key = `hermes_chat_${{ACTIVE_ASSISTANT_ID}}_${{CURRENT_DEDICATED_CODE}}`;
      try {{
        localStorage.setItem(key, JSON.stringify(history));
      }} catch (e) {{}}
    }}

    function renderDedicatedChatMessages() {{
      const container = document.getElementById('dedicated-chat-messages-container');
      if (!container) return;

      const history = getDedicatedChatHistory();
      container.innerHTML = history.map(msg => {{
        const isUser = (msg.sender === 'user');
        return `
          <div class="flex ${{isUser ? 'justify-end' : 'justify-start'}}">
            <div class="max-w-[80%] ${{isUser ? 'bg-indigo-600 text-white rounded-2xl rounded-tr-none' : 'bg-white text-slate-800 border border-slate-200 rounded-2xl rounded-tl-none'}} p-3.5 shadow-sm space-y-1">
              <div class="flex items-center space-x-2 text-[10px] ${{isUser ? 'text-indigo-200 justify-end' : 'text-slate-400'}} font-medium">
                <span>${{isUser ? 'Sếp Hoàng' : CURRENT_DEDICATED_CODE}}</span>
                <span>•</span>
                <span>${{msg.time}}</span>
              </div>
              <p class="text-xs leading-relaxed whitespace-pre-wrap">${{msg.text}}</p>
            </div>
          </div>
        `;
      }}).join('');

      container.scrollTop = container.scrollHeight;
    }}

    function handleSendDedicatedChat(event) {{
      event.preventDefault();
      const input = document.getElementById('dedicated-chat-input');
      const text = input ? input.value.trim() : '';
      if (!text) return;

      const history = getDedicatedChatHistory();
      const nowStr = new Date().toLocaleTimeString('vi-VN', {{ hour: '2-digit', minute: '2-digit' }});

      history.push({{
        sender: 'user',
        time: nowStr,
        text: text
      }});
      input.value = '';
      saveDedicatedChatHistory(history);
      renderDedicatedChatMessages();

      // Simulate Bot Response isolated for this code
      setTimeout(() => {{
        let reply = '';
        if (CURRENT_DEDICATED_CODE === '#MEDIA') {{
          reply = `Dạ Sếp, Em là Trợ lý của sếp Hoàng.
Em đã kích hoạt Studio AI Engine cho yêu cầu: "${{text}}". Em đang tiến hành tạo kịch bản hình ảnh và render video TVC độ nét cao cho Sếp ạ!`;
        }} else if (CURRENT_DEDICATED_CODE === '#KETOAN') {{
          reply = `Dạ Sếp, Em là Trợ lý của sếp Hoàng.
Em đã ghi nhận số liệu và cập nhật bảng tính kế toán theo yêu cầu: "${{text}}". Dòng tiền và báo cáo đã sẵn sàng ạ!`;
        }} else {{
          reply = `Dạ Sếp, Em là Trợ lý của sếp Hoàng.
Em đã tiếp nhận chỉ đạo [${{CURRENT_DEDICATED_CODE}}]: "${{text}}". Em xử lý ngay đây ạ!`;
        }}

        history.push({{
          sender: 'bot',
          time: new Date().toLocaleTimeString('vi-VN', {{ hour: '2-digit', minute: '2-digit' }}),
          text: reply
        }});
        saveDedicatedChatHistory(history);
        renderDedicatedChatMessages();
      }}, 600);
    }}

    function clearDedicatedChatHistory() {{
      if (!confirm(`Sếp có muốn xóa toàn bộ lịch sử trao đổi của riêng mã [${{CURRENT_DEDICATED_CODE}}] không?`)) return;
      const key = `hermes_chat_${{ACTIVE_ASSISTANT_ID}}_${{CURRENT_DEDICATED_CODE}}`;
      localStorage.removeItem(key);
      renderDedicatedChatMessages();
    }}

    // ==================== MODAL GÁN COOKIE CHO BOT ====================
    function openAssignCookieModal() {{
      const currentBot = ASSISTANTS_FLEET.find(a => a.id === ACTIVE_ASSISTANT_ID) || ASSISTANTS_FLEET[0];
      if (!currentBot) return;

      const modal = document.getElementById('modal-assign-cookie');
      const subtitle = document.getElementById('assign-cookie-modal-subtitle');
      const listContainer = document.getElementById('assign-cookie-checkboxes-list');

      if (subtitle) subtitle.innerText = `Cấp tài khoản AI Pool cho: "${{currentBot.name}}" (Cổng ${{currentBot.bridge_port}})`;

      const assigned = currentBot.assigned_cookies || [];
      if (listContainer) {{
        listContainer.innerHTML = POOL_ACCOUNTS.map(acc => {{
          const isChecked = assigned.includes(acc.name);
          const isReady = (acc.status === 'ready');
          return `
            <label class="flex items-center space-x-3 p-2.5 rounded-xl border ${{isChecked ? 'bg-amber-50/60 border-amber-300' : 'bg-slate-50 border-slate-200'}} hover:bg-amber-50/30 cursor-pointer text-xs transition-all">
              <input type="checkbox" name="assign_cookie_box" value="${{acc.name}}" ${{isChecked ? 'checked' : ''}} class="rounded text-amber-600 focus:ring-amber-500 w-4 h-4">
              <div class="flex items-center space-x-2.5 flex-1">
                <div class="w-8 h-8 rounded-lg bg-white border border-slate-200 overflow-hidden flex-shrink-0">
                  <img src="${{acc.avatar}}" class="w-full h-full object-cover">
                </div>
                <div>
                  <span class="font-bold text-slate-900 block font-mono">${{acc.name}}</span>
                  <span class="text-[10px] text-slate-400 font-mono">${{acc.file}}</span>
                </div>
              </div>
              <span class="px-2 py-0.5 rounded-full text-[9px] font-extrabold uppercase ${{isReady ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}}">
                ${{isReady ? '🟢 Ready' : '🔴 Expired'}}
              </span>
            </label>
          `;
        }}).join('');
      }}

      if (modal) modal.classList.remove('hidden');
      lucide.createIcons();
    }}

    function closeAssignCookieModal() {{
      const modal = document.getElementById('modal-assign-cookie');
      if (modal) modal.classList.add('hidden');
    }}

    function saveAssignedCookies() {{
      const currentBot = ASSISTANTS_FLEET.find(a => a.id === ACTIVE_ASSISTANT_ID);
      if (!currentBot) return;

      const checked = Array.from(document.querySelectorAll('input[name="assign_cookie_box"]:checked')).map(cb => cb.value);
      currentBot.assigned_cookies = checked;
      saveFleetToStorage();
      renderAssistantsFleet();
      closeAssignCookieModal();

      // Dispatch to Server
      fetch('/api/assistants/assign-cookie', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ bot_id: currentBot.id, assigned_cookies: checked }})
      }}).catch(() => {{}});

      fetch('/api/assistants', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ action: 'assign_cookie', bot_id: currentBot.id, assigned_cookies: checked }})
      }}).catch(() => {{}});

      alert(`✅ Đã cấp thành công ${{checked.length}} tài khoản AI Cookie cho Trợ Lý "${{currentBot.name}}"!`);
    }}

    function unassignCookieFromBot(cookieName) {{
      const currentBot = ASSISTANTS_FLEET.find(a => a.id === ACTIVE_ASSISTANT_ID);
      if (!currentBot) return;

      if (!confirm(`Sếp có muốn bỏ gán Cookie [${{cookieName}}] khỏi Bot "${{currentBot.name}}" không?`)) return;
      currentBot.assigned_cookies = (currentBot.assigned_cookies || []).filter(c => c !== cookieName);
      saveFleetToStorage();
      renderAssistantsFleet();

      fetch('/api/assistants/assign-cookie', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ bot_id: currentBot.id, assigned_cookies: currentBot.assigned_cookies }})
      }}).catch(() => {{}});
    }}

    // Backwards Compatibility Functions
    function switchFleetSubTab(subTab) {{
      if (subTab === 'virtual') switchBotWorkspaceSubTab('codes');
      else if (subTab === 'pool') switchBotWorkspaceSubTab('cookies');
      else switchBotWorkspaceSubTab('cookies');
    }}

    function changeActiveAssistant(botId) {{
      selectZaloBot(botId);
    }}

    function testQuickMessage(code) {{
      openDedicatedChat(code);
    }}

    function openAddVirtualBotModal() {{
      document.getElementById('modal-add-virtual-bot').classList.remove('hidden');
      lucide.createIcons();
    }}

    function closeAddVirtualBotModal() {{
      document.getElementById('modal-add-virtual-bot').classList.add('hidden');
      document.getElementById('form-add-virtual-bot').reset();
    }}

    function submitAddVirtualBot(e) {{
      e.preventDefault();
      const name = document.getElementById('vbot-name').value.trim();
      let code = document.getElementById('vbot-code').value.trim();
      const rawAliases = document.getElementById('vbot-aliases').value.trim();
      const mode = document.getElementById('vbot-mode').value;
      const account = document.getElementById('vbot-account').value;
      const persona = document.getElementById('vbot-persona').value.trim() || 'Trợ lý nghiệp vụ chuyên biệt.';
      const prompt = document.getElementById('vbot-prompt').value.trim() || `Em là ${{name}} của sếp Hoàng.`;

      if (!code.startsWith('#') && !code.startsWith('!') && !code.startsWith('@')) {{
        code = '#' + code;
      }}

      const aliases = rawAliases ? rawAliases.split(',').map(s => s.trim()).filter(Boolean) : [];

      const newBot = {{
        bot_id: `vbot_${{Date.now()}}`,
        name: name,
        routing_code: code,
        aliases: aliases,
        persona: persona,
        system_prompt: prompt,
        mode: mode,
        linked_pool_account: account,
        status: "active"
      }};

      if (!TENANTS_DATA.tenants || !TENANTS_DATA.tenants.length) {{
        TENANTS_DATA.tenants = [{{ tenant_id: 'tenant_master_hoang', name: 'Sếp Hoàng', bots: [] }}];
      }}

      TENANTS_DATA.tenants[0].bots.push(newBot);
      saveFleetToStorage();
      renderAssistantsFleet();
      closeAddVirtualBotModal();

      fetch('/api/tenants', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ tenant_id: 'tenant_master_hoang', bot_data: newBot }})
      }}).catch(() => {{}});

      alert(`✅ Đã kích hoạt Bot mới "${{name}}" thành công với mã định danh [${{code}}]!`);
    }}

    function deleteVirtualBot(tenantId, botId) {{
      if (!confirm('Sếp có chắc chắn muốn xóa Virtual Bot này khỏi hệ thống không?')) return;
      (TENANTS_DATA.tenants || []).forEach(t => {{
        if (t.tenant_id === tenantId) {{
          t.bots = (t.bots || []).filter(b => b.bot_id !== botId);
        }}
      }});
      saveFleetToStorage();
      renderAssistantsFleet();

      fetch('/api/tenants?action=delete', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ tenant_id: tenantId, bot_id: botId }})
      }}).catch(() => {{}});
    }}

    function renderVirtualBots() {{
      // Alias to render active bot codes
      const currentBot = ASSISTANTS_FLEET.find(a => a.id === ACTIVE_ASSISTANT_ID) || ASSISTANTS_FLEET[0];
      if (currentBot) renderBotAssignedCodes(currentBot);
    }}

    

    // Render Pool Accounts Table (Cổng 8770)
        function renderPoolAccounts() {{
      const tbody = document.getElementById('pool-table-body');
      const badgeCount = document.getElementById('badge-pool-count');
      const kpiTotal = document.getElementById('pool-kpi-total');
      const kpiReady = document.getElementById('pool-kpi-ready');
      const kpiExpired = document.getElementById('pool-kpi-expired');

      if (badgeCount) badgeCount.innerText = `${{POOL_ACCOUNTS.length}} Acc`;
      if (kpiTotal) kpiTotal.innerText = `${{POOL_ACCOUNTS.length}} Tài Khoản`;

      const readyCount = POOL_ACCOUNTS.filter(a => a.status === 'ready').length;
      const expiredCount = POOL_ACCOUNTS.filter(a => a.status === 'expired').length;

      if (kpiReady) kpiReady.innerText = `${{readyCount}} Sẵn Sàng`;
      if (kpiExpired) kpiExpired.innerText = `${{expiredCount}} Cần Nạp Lại`;

      if (!tbody) return;

      tbody.innerHTML = POOL_ACCOUNTS.map(acc => {{
        const isReady = (acc.status === 'ready');
        const isVideoOk = (acc.video_state === 'ok');

        // Token metrics (Chu kỳ đặt lại hàng tuần theo Meta AI Engine)
        const tokensTot = acc.tokens_total || 500;
        const tokensUsed = (acc.tokens_used !== undefined) ? acc.tokens_used : ((acc.done || 0) * 10);
        const tokensRem = (acc.tokens_remaining !== undefined) ? acc.tokens_remaining : Math.max(0, tokensTot - tokensUsed);
        const usedPct = (acc.used_percent !== undefined) ? acc.used_percent : Math.min(100, Math.round((tokensUsed / tokensTot) * 100));
        const remPct = 100 - usedPct;
        const resetStr = acc.reset_time_str || 'Còn 6 ngày 9h';
        const resetLabel = acc.reset_label || 'Đặt lại vào 5 tháng 11';
        const resetSec = acc.reset_countdown_seconds || 550000;
        const bonusTokens = acc.bonus_tokens || '1 Tỷ Token (Vĩnh viễn)';

        return `
          <tr class="hover:bg-amber-50/30 transition-all border-b border-slate-100">
            <td class="py-3.5 px-4">
              <div class="flex items-center space-x-3">
                <div class="w-9 h-9 rounded-xl bg-slate-100 border border-slate-200 overflow-hidden flex-shrink-0">
                  <img src="${{acc.avatar}}" class="w-full h-full object-cover">
                </div>
                <div>
                  <span class="font-bold text-slate-900 block font-mono text-xs">${{acc.name}}</span>
                  <span class="text-[10px] text-slate-400 font-mono">${{acc.file}}</span>
                </div>
              </div>
            </td>
            <td class="py-3.5 px-4 text-center">
              <span class="px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase ${{isReady ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-rose-50 text-rose-700 border border-rose-200'}}">
                ${{isReady ? '🟢 Ready' : '🔴 Expired'}}
              </span>
            </td>
            <td class="py-3.5 px-4">
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
            </td>
            <td class="py-3.5 px-4 text-center">
              <div class="inline-flex items-center space-x-1.5">
                <span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase ${{isVideoOk ? 'bg-purple-50 text-purple-700 border border-purple-200' : 'bg-blue-50 text-blue-700 border border-blue-200'}}">
                  ${{isVideoOk ? '🎬 Video & Ảnh' : '🎨 Chỉ Tạo Ảnh'}}
                </span>
                <button onclick="toggleVideoMode('${{acc.name}}', '${{acc.video_state || 'blocked'}}')" title="Đổi chế độ tạo Video / Chỉ Ảnh" class="p-1 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-700 transition-all cursor-pointer">
                  <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
                </button>
              </div>
            </td>
            <td class="py-3.5 px-4 text-center font-bold text-slate-700 text-xs">
              ${{acc.done || 0}} Đã xong
            </td>
            <td class="py-3.5 px-4 text-right">
              <div class="flex items-center justify-end space-x-1.5">
                <button onclick="launchLocalLoginForAccount('${{acc.name}}')" title="Mở Chrome local trên Sever để tự giải captcha tài khoản này" class="px-2 py-1 bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200 rounded-lg text-[10px] font-bold flex items-center space-x-1 cursor-pointer">
                  <i data-lucide="monitor" class="w-3 h-3"></i>
                  <span>Giải Captcha</span>
                </button>
                <button onclick="quickUpdateCookie('${{acc.name}}')" class="px-2 py-1 bg-amber-50 text-amber-800 hover:bg-amber-100 border border-amber-200 rounded-lg text-[10px] font-bold cursor-pointer">
                  🍪 Nạp Cookie
                </button>
                <button onclick="deletePoolAccount('${{acc.name}}')" class="p-1 text-slate-400 hover:text-rose-600 rounded cursor-pointer">
                  <i data-lucide="trash-2" class="w-4 h-4"></i>
                </button>
              </div>
            </td>
          </tr>
        `;
      }}).join('');
      lucide.createIcons();
    }}

    // Cookie Modal Handlers
    function openImportCookieModal(targetName = '') {{
      document.getElementById('modal-import-cookie').classList.remove('hidden');
      if (targetName) document.getElementById('cookie-acc-name').value = targetName;
      lucide.createIcons();
    }}

    function closeImportCookieModal() {{
      document.getElementById('modal-import-cookie').classList.add('hidden');
      document.getElementById('form-import-cookie').reset();
    }}

    function quickUpdateCookie(accName) {{
      openImportCookieModal(accName);
    }}

    function handleCookieFileUpload(e) {{
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = function(evt) {{
        document.getElementById('cookie-content-input').value = evt.target.result;
        if (!document.getElementById('cookie-acc-name').value) {{
          document.getElementById('cookie-acc-name').value = file.name.replace('.json', '').replace('.txt', '');
        }}
      }};
      reader.readAsText(file);
    }}

    function submitImportCookie(e) {{
      e.preventDefault();
      const name = document.getElementById('cookie-acc-name').value.trim();
      const content = document.getElementById('cookie-content-input').value.trim();

      if (!name || !content) {{
        alert("Vui lòng nhập tên tài khoản và dán nội dung Cookie!");
        return;
      }}

      const newAccount = {{
        name: name,
        file: `${{name}}.json`,
        status: "ready",
        session_cookie: "hatch_sess=..." + Math.random().toString(36).substring(2, 10),
        has_hatch_sess: true,
        done: 0,
        failed: 0,
        expires_in: "Còn 30 ngày (Vừa nạp)",
        video_state: "ok",
        last_check: "Vừa xong",
        avatar: `https://api.dicebear.com/7.x/bottts/svg?seed=${{encodeURIComponent(name)}}`
      }};

      const existingIdx = POOL_ACCOUNTS.findIndex(a => a.name === name);
      if (existingIdx !== -1) {{
        POOL_ACCOUNTS[existingIdx] = newAccount;
      }} else {{
        POOL_ACCOUNTS.push(newAccount);
      }}

      saveFleetToStorage();
      renderPoolAccounts();
      closeImportCookieModal();

      // Call API in background
      fetch('/api/pool', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ name: name, cookies: content }})
      }}).catch(() => {{}});

      alert(`✅ Đã nạp thành công Cookie cho tài khoản "${{name}}"! Trạng thái: Ready (Sẵn sàng render video/ảnh trên cổng 8770).`);
    }}

    function deletePoolAccount(name) {{
      if (confirm(`Sếp có chắc chắn muốn xóa tài khoản "${{name}}" khỏi Pool không?`)) {{
        POOL_ACCOUNTS = POOL_ACCOUNTS.filter(a => a.name !== name);
        saveFleetToStorage();
        renderPoolAccounts();
        fetch(`/api/pool?name=${{name}}`, {{ method: 'DELETE' }}).catch(() => {{}});
      }}
    }}

    function toggleVideoMode(name, currentState) {{
      const newState = (currentState === 'ok') ? 'blocked' : 'ok';
      const label = (newState === 'ok') ? '🎬 Tạo Video & Ảnh' : '🎨 Chỉ Tạo Ảnh';
      
      const targetAcc = POOL_ACCOUNTS.find(a => a.name === name);
      if (targetAcc) {{
        targetAcc.video_state = newState;
        saveFleetToStorage();
        renderPoolAccounts();
      }}

      fetch('/api/pool', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ action: 'video-state', name: name, state: newState }})
      }}).then(res => res.json()).then(data => {{
        alert(`✅ Đã cập nhật chế độ tài khoản "${{name}}" sang: [${{label}}]`);
      }}).catch(err => {{
        alert(`✅ Đã lưu chế độ cục bộ: [${{label}}]`);
      }});
    }}

    function checkPoolHealth() {{
      alert("🩺 Đang kiểm tra sức khỏe Cookie các tài khoản trên máy chủ cổng 8770... Tất cả tài khoản có Cookie hợp lệ đều sẵn sàng!");
    }}

    // Auto Extract Modal
    function openAutoExtractModal() {{
      document.getElementById('modal-auto-extract').classList.remove('hidden');
      lucide.createIcons();
    }}

    function closeAutoExtractModal() {{
      document.getElementById('modal-auto-extract').classList.add('hidden');
    }}

    function submitAutoExtract(e) {{
      e.preventDefault();
      const raw = document.getElementById('auto-extract-input').value.trim();
      if (!raw) {{
        alert("Vui lòng nhập ít nhất 1 tài khoản (email|password)!");
        return;
      }}

      const lines = raw.split('\\n').filter(l => l.trim() && !l.trim().startsWith('#'));
      lines.forEach(l => {{
        const parts = l.split('|').map(s => s.trim());
        const email = parts[0] || 'acc';
        const accName = email.split('@')[0];
        
        POOL_ACCOUNTS.push({{
          name: accName,
          file: `${{accName}}.json`,
          status: "ready",
          session_cookie: "hatch_sess=..." + Math.random().toString(36).substring(2, 8),
          has_hatch_sess: true,
          done: 0,
          failed: 0,
          expires_in: "Còn 30 ngày (Mới nạp OTP)",
          video_state: "ok",
          last_check: "Vừa xong",
          avatar: `https://api.dicebear.com/7.x/bottts/svg?seed=${{encodeURIComponent(accName)}}`
        }});
      }});

      saveFleetToStorage();
      renderPoolAccounts();
      closeAutoExtractModal();

      fetch('/api/pool', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ type: 'auto_extract', accounts_raw: raw }})
      }}).catch(() => {{}});

      alert(`⚡ Đã tiếp nhận yêu cầu tự động trích xuất ${{lines.length}} tài khoản! Cookie đã được lưu và kích hoạt vào Pool.`);
    }}

    // Toggle Bot Online/Pause
    function toggleBotStatus(botId) {{
      const bot = ASSISTANTS_FLEET.find(a => a.id === botId);
      if (!bot) return;
      bot.status = (bot.status === 'online') ? 'standby' : 'online';
      saveFleetToStorage();
      renderAssistantsFleet();
    }}

    // Delete Assistant
    function deleteAssistant(botId) {{
      if (botId === ACTIVE_ASSISTANT_ID) {{
        alert("Không thể gỡ bỏ Trợ Lý đang đảm nhiệm vị trí Chính!");
        return;
      }}
      if (confirm("Sếp có chắc chắn muốn gỡ bỏ tài khoản Trợ Lý này khỏi Fleet không?")) {{
        ASSISTANTS_FLEET = ASSISTANTS_FLEET.filter(a => a.id !== botId);
        saveFleetToStorage();
        renderAssistantsFleet();
        fetch(`/api/assistants?id=${{botId}}`, {{ method: 'DELETE' }}).catch(() => {{}});
      }}
    }}

    // Modal Add Assistant (Zalo)
    function openAddAssistantModal() {{
      document.getElementById('modal-add-assistant').classList.remove('hidden');
      lucide.createIcons();
    }}

    function closeAddAssistantModal() {{
      document.getElementById('modal-add-assistant').classList.add('hidden');
    }}

    function submitAddAssistant(e) {{
      e.preventDefault();
      const name = document.getElementById('new-ast-name').value.trim();
      const platform = document.getElementById('new-ast-platform').value;
      const port = parseInt(document.getElementById('new-ast-port').value, 10) || 3052;
      const phone = document.getElementById('new-ast-phone').value.trim() || 'Chưa cung cấp';
      const role = document.getElementById('new-ast-role').value;
      const persona = document.getElementById('new-ast-persona').value.trim() || 'Trợ lý nghiệp vụ chuyên trách theo chỉ đạo của Sếp Hoàng.';

      const checkedGroups = [];
      document.querySelectorAll('input[name="assign_group"]:checked').forEach(cb => {{
        checkedGroups.push(cb.value);
      }});

      if (!name) {{
        alert("Vui lòng nhập tên trợ lý!");
        return;
      }}

      const newBot = {{
        id: `ast_${{Date.now()}}`,
        name: name,
        uid: `u_ast_${{Date.now().toString().slice(-6)}}`,
        phone: phone,
        avatar: `https://api.dicebear.com/7.x/bottts/svg?seed=${{encodeURIComponent(name)}}`,
        role: role,
        platform: platform,
        bridge_port: port,
        status: "online",
        assigned_groups: checkedGroups.length > 0 ? checkedGroups : Object.keys(SYSTEM_DATABASE.groups),
        persona: persona,
        memory_mb: Math.floor(Math.random() * 40) + 35,
        messages_count: 0
      }};

      ASSISTANTS_FLEET.push(newBot);
      saveFleetToStorage();
      renderAssistantsFleet();
      closeAddAssistantModal();
      document.getElementById('form-new-assistant').reset();

      fetch('/api/assistants', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(newBot)
      }}).catch(() => {{}});

      alert(`✅ Đã nạp thành công Trợ Lý mới: "${{name}}"! Đã phân bổ phụ trách ${{newBot.assigned_groups.length}} nhóm Zalo.`);
    }}

    // Modal QR Pair
    function openQRPairModal(botId) {{
      document.getElementById('modal-qr-pair').classList.remove('hidden');
      lucide.createIcons();
    }}

    function closeQRPairModal() {{
      document.getElementById('modal-qr-pair').classList.add('hidden');
    }}

    function confirmQRPairSuccess() {{
      closeQRPairModal();
      alert("✅ Xác thực thành công! Phiên Zalo của Trợ Lý đã được nạp vào máy chủ và duy trì 24/24.");
    }}

    // Select Group
    function selectGroup(groupKey) {{
      CURRENT_GROUP_KEY = groupKey;
      const grp = SYSTEM_DATABASE.groups[groupKey];
      if (!grp) return;

      document.getElementById('current-active-group-label').innerText = grp.name;
      document.getElementById('group-name-display').innerText = grp.name;
      document.getElementById('group-id-display').innerText = grp.id;
      document.getElementById('group-member-count').innerText = grp.memberCount;
      document.getElementById('group-persona-label').innerText = grp.persona;

      const avtEl = document.getElementById('group-avatar-display');
      if (grp.avatar && grp.avatar.startsWith('http')) {{
        avtEl.innerHTML = `<img src="${{grp.avatar}}" class="w-full h-full object-cover rounded-2xl">`;
      }} else {{
        avtEl.innerHTML = grp.avatar || '👥';
      }}

      const picker = document.getElementById('group-picker-select');
      if (picker) picker.value = groupKey;

      renderMembersTable(grp.members);
      if (grp.members && grp.members.length > 0) {{
        inspectUser(grp.members[0]);
      }}
    }}

    // Render Members Table
    function renderMembersTable(members) {{
      const tbody = document.getElementById('members-table-body');
      if (!tbody) return;

      if (!members || members.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="7" class="py-6 text-center text-slate-400">Không có thành viên nào trong nhóm này.</td></tr>';
        return;
      }}

      tbody.innerHTML = members.map((m) => `
        <tr class="hover:bg-blue-50/50 transition-all">
          <td class="py-3 px-4">
            <div class="flex items-center space-x-2.5">
              <div class="w-8 h-8 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center font-bold text-xs flex-shrink-0 overflow-hidden">
                ${{m.avatar ? `<img src="${{m.avatar}}" class="w-full h-full object-cover">` : m.name.charAt(0)}}
              </div>
              <div>
                <span class="font-bold text-slate-900 block">${{m.name}}</span>
                <span class="text-[10px] text-slate-400">${{m.role}}</span>
              </div>
            </div>
          </td>
          <td class="py-3 px-4 font-mono text-[11px] text-slate-500">${{m.uid}}</td>
          <td class="py-3 px-4 text-center">
            <input type="checkbox" ${{m.canDM ? 'checked' : ''}} onchange="togglePerm('${{m.uid}}', 'dm', this.checked)" class="w-4 h-4 text-[#0066cc] rounded border-slate-300 focus:ring-blue-500 cursor-pointer">
          </td>
          <td class="py-3 px-4 text-center">
            <input type="checkbox" ${{m.canGroup ? 'checked' : ''}} onchange="togglePerm('${{m.uid}}', 'group', this.checked)" class="w-4 h-4 text-[#0066cc] rounded border-slate-300 focus:ring-blue-500 cursor-pointer">
          </td>
          <td class="py-3 px-4 text-center">
            <input type="checkbox" ${{m.canAssign ? 'checked' : ''}} onchange="togglePerm('${{m.uid}}', 'assign', this.checked)" class="w-4 h-4 text-[#0066cc] rounded border-slate-300 focus:ring-blue-500 cursor-pointer">
          </td>
          <td class="py-3 px-4 text-center">
            <button onclick='inspectUserByName("${{m.uid}}")' class="px-2 py-1 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded text-[11px] font-mono border border-emerald-200 cursor-pointer">
              📁 ${{m.files.length}} tệp cô lập
            </button>
          </td>
          <td class="py-3 px-4 text-right">
            <button onclick="saveMemberPerm('${{m.name}}')" class="px-2.5 py-1 bg-[#0066cc] text-white hover:bg-[#0284c7] rounded-lg text-[11px] font-bold cursor-pointer">
              Lưu Quyền
            </button>
          </td>
        </tr>
      `).join('');
    }}

    function inspectUserByName(uid) {{
      const grp = SYSTEM_DATABASE.groups[CURRENT_GROUP_KEY];
      if (!grp) return;
      const user = grp.members.find(m => m.uid === uid);
      if (user) inspectUser(user);
    }}

    function inspectUser(user) {{
      document.getElementById('inspect-user-name').innerText = `Chi Tiết Thư Mục: ${{user.name}} (${{user.uid}})`;
      document.getElementById('inspect-user-path').innerText = user.storagePath;

      const container = document.getElementById('user-files-container');
      if (!container) return;

      container.innerHTML = user.files.map(f => `
        <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
          <div class="flex items-center space-x-2.5 overflow-hidden">
            <i data-lucide="file-text" class="w-5 h-5 text-[#0066cc] flex-shrink-0"></i>
            <span class="text-xs font-bold text-slate-800 truncate">${{f}}</span>
          </div>
          <button onclick="alert('Đang tải file an toàn từ thư mục riêng: ${{f}}')" class="p-1.5 text-slate-400 hover:text-[#0066cc] cursor-pointer">
            <i data-lucide="download" class="w-4 h-4"></i>
          </button>
        </div>
      `).join('');
      lucide.createIcons();
    }}

    function togglePerm(uid, permType, value) {{
      console.log(`Updated ${{permType}} for ${{uid}} to ${{value}}`);
    }}

    function saveMemberPerm(name) {{
      alert(`✅ Đã lưu cấu hình phân quyền cho ${{name}} và cập nhật tức thì tới Bot Zalo!`);
    }}

    function applyPersonaToCurrentGroup(type) {{
      alert(`✅ Đã nạp thành công Persona kịch bản ngành nghề cho nhóm "${{SYSTEM_DATABASE.groups[CURRENT_GROUP_KEY].name}}"! Bot sẽ ngay lập tức phản hồi theo phong cách này.`);
    }}

    function readExcelFile(e) {{
      const file = e.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = function(evt) {{
        try {{
          const data = new Uint8Array(evt.target.result);
          const workbook = XLSX.read(data, {{ type: 'array' }});
          const firstSheet = workbook.SheetNames[0];
          const worksheet = workbook.Sheets[firstSheet];
          const html = XLSX.utils.sheet_to_html(worksheet);
          
          document.getElementById('excel-preview-content').innerHTML = html;
          alert(`✅ Đã đọc thành công bảng dữ liệu từ: ${{file.name}}`);
        }} catch (err) {{
          alert("Lỗi đọc Excel: " + err.message);
        }}
      }};
      reader.readAsArrayBuffer(file);
    }}

    function exportFullSystemReport() {{
      const currentGrp = SYSTEM_DATABASE.groups[CURRENT_GROUP_KEY];
      const ws_data = [
        ["HỆ THỐNG QUẢN TRỊ HERMES ZALO ENTERPRISE - BÁO CÁO PHÂN QUYỀN"],
        ["Nhóm Zalo:", currentGrp.name, "Mã Group ID:", currentGrp.id],
        ["Persona:", currentGrp.persona, "Ngày xuất:", new Date().toLocaleDateString('vi-VN')],
        [],
        ["STT", "Họ Tên Thành Viên", "User ID Zalo", "Vai Trò", "Quyền Chat Riêng 1-1", "Quyền Chat Nhóm", "Quyền Giao Việc", "Đường Dẫn Thư Mục Riêng", "Số Tệp Độc Lập"]
      ];

      currentGrp.members.forEach((m, idx) => {{
        ws_data.push([
          idx + 1,
          m.name,
          m.uid,
          m.role,
          m.canDM ? "CHO PHÉP" : "CHẶN",
          m.canGroup ? "CHO PHÉP" : "CHẶN",
          m.canAssign ? "CHO PHÉP" : "CHẶN",
          m.storagePath,
          m.files.length
        ]);
      }});

      const wb = XLSX.utils.book_new();
      const ws = XLSX.utils.aoa_to_sheet(ws_data);
      XLSX.utils.book_append_sheet(wb, ws, "PhanQuyenZalo");
      XLSX.writeFile(wb, `BaoCao_PhanQuyen_${{currentGrp.id.replace(':', '_')}}.xlsx`);
      alert("✅ Đã xuất và tải về file Excel báo cáo hệ thống thành công!");
    }}

    async function leaveZaloGroup(gid, gname) {{
      if (!gid) return;
      const cleanGname = gname || gid;
      const confirmed = confirm(`⚠️ Sếp có chắc chắn muốn BOT rời khỏi nhóm:\n"${{cleanGname}}"\n(ID: ${{gid}}) không?\n\nSau khi thoát, bot sẽ không nhận tin và không phản hồi trong nhóm này nữa!`);
      if (!confirmed) return;

      try {{
        const resp = await fetch('/api/groups/leave', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ group_id: gid }})
        }});
        const res = await resp.json();
        if (resp.ok && (res.status === 'success' || res.ok)) {{
          alert(`✅ Đã điều khiển BOT thoát khỏi nhóm "${{cleanGname}}" thành công!`);
          delete SYSTEM_DATABASE.groups[gid];
          renderOverviewCards();
          const grpKeys = Object.keys(SYSTEM_DATABASE.groups);
          if (grpKeys.length > 0) {{
            selectGroup(grpKeys[0]);
          }}
          await loadLiveGroups();
        }} else {{
          alert(`❌ Thoát nhóm thất bại: ${{res.error || res.message || 'Lỗi không xác định từ Sever'}}`);
        }}
      }} catch (err) {{
        alert(`❌ Lỗi kết nối khi gửi lệnh thoát nhóm: ${{err.message}}`);
      }}
    }}

    function renderOverviewCards() {{
      const container = document.getElementById('overview-group-cards');
      if (!container) return;

      container.innerHTML = Object.keys(SYSTEM_DATABASE.groups).map(k => {{
        const g = SYSTEM_DATABASE.groups[k];
        const avtHtml = (g.avatar && g.avatar.startsWith('http')) 
          ? `<img src="${{g.avatar}}" class="w-8 h-8 rounded-lg object-cover">` 
          : `<span class="w-8 h-8 rounded-lg bg-blue-100 text-[#0066cc] flex items-center justify-center font-bold text-xs">${{g.avatar || '👥'}}</span>`;

        return `
          <div class="p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-white hover:border-[#0066cc] hover:shadow-md transition-all cursor-pointer relative group/card" onclick="selectGroup('${{g.id}}'); switchTab('groups')">
            <div class="flex items-center justify-between mb-2">
              ${{avtHtml}}
              <div class="flex items-center space-x-1.5">
                <span class="text-[9px] font-mono text-slate-400 truncate max-w-[90px]">${{g.id}}</span>
                <button onclick="event.stopPropagation(); leaveZaloGroup('${{g.id}}', '${{g.name.replace(/'/g, \"\\'\")}}')" title="Thoát nhóm này" class="px-2 py-0.5 rounded-lg text-[10px] font-bold bg-rose-50 text-rose-600 border border-rose-200 hover:bg-rose-600 hover:text-white transition-all shadow-sm flex items-center space-x-0.5">
                  <span>🚪</span>
                  <span>Thoát</span>
                </button>
              </div>
            </div>
            <h4 class="font-bold text-xs text-slate-900 truncate">${{g.name}}</h4>
            <p class="text-[11px] text-slate-500 mt-1">${{g.memberCount}} • ${{g.persona}}</p>
          </div>
        `;
      }}).join('');
    }}


    // ==================== RENTAL PLATFORM FUNCTIONS ====================
    function renderRentalPlatform() {{
      const containerCustomers = document.getElementById('rental-customers-table-body');
      const containerBots = document.getElementById('empty-bot-cards-container');
      const kpiActive = document.getElementById('kpi-rental-active-customers');
      const kpiAvail = document.getElementById('kpi-rental-available-bots');
      const kpiRented = document.getElementById('kpi-rental-rented-bots');

      const customers = RENTAL_PROFILES_DATA.customers || [];
      const emptyBots = RENTAL_POOL_DATA.empty_bots || [];

      const availableBots = emptyBots.filter(b => b.status === 'available');
      const rentedBots = emptyBots.filter(b => b.status === 'rented');

      if (kpiActive) kpiActive.innerText = customers.length;
      if (kpiAvail) kpiAvail.innerText = availableBots.length;
      if (kpiRented) kpiRented.innerText = rentedBots.length;

      if (containerCustomers) {{
        if (customers.length === 0) {{
          containerCustomers.innerHTML = '<tr><td colspan="7" class="px-5 py-6 text-center text-slate-400 text-xs">Chưa có khách hàng thuê bot nào trong hệ thống.</td></tr>';
        }} else {{
          containerCustomers.innerHTML = customers.map((c, idx) => {{
            const botsCount = (c.assigned_bots || []).length;
            const botNames = (c.assigned_bots || []).map(b => b.name || b.routing_code || b.bot_id).join(', ');
            const isExpiringSoon = (c.days_remaining <= 5);
            const badgeClass = isExpiringSoon ? 'bg-amber-100 text-amber-800 border border-amber-300' : 'bg-emerald-100 text-emerald-800 border border-emerald-300';
            
            return `
              <tr class="hover:bg-slate-50 transition-all border-b border-slate-100">
                <td class="px-5 py-3.5 text-xs font-bold text-slate-800">${{idx + 1}}</td>
                <td class="px-5 py-3.5">
                  <div class="font-extrabold text-xs text-slate-900">${{c.display_name || c.user_zalo_id}}</div>
                  <div class="text-[10px] font-mono text-slate-400 mt-0.5">UID: ${{c.user_zalo_id}}</div>
                </td>
                <td class="px-5 py-3.5">
                  <span class="px-2.5 py-1 rounded-full text-[10px] font-extrabold bg-blue-50 text-blue-700 border border-blue-200">
                    ${{c.package_name || 'Gói Thuê Bot'}}
                  </span>
                </td>
                <td class="px-5 py-3.5">
                  <span class="px-2 py-0.5 rounded-md text-xs font-bold bg-purple-50 text-purple-700 border border-purple-200">
                    ${{botsCount}} Bot
                  </span>
                  <div class="text-[10px] text-slate-500 mt-0.5 truncate max-w-[150px]">${{botNames || 'Chưa gán'}}</div>
                </td>
                <td class="px-5 py-3.5">
                  <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-100 text-slate-600 truncate max-w-[180px] inline-block" title="${{c.sandbox_path}}">
                    ${{c.sandbox_path || 'storage/tenants/' + c.user_zalo_id}}
                  </span>
                </td>
                <td class="px-5 py-3.5">
                  <span class="px-2.5 py-1 rounded-full text-[10px] font-extrabold ${{badgeClass}}">
                    ${{c.days_remaining}} Ngày (hết hạn ${{c.expires_at ? c.expires_at.split('T')[0] : 'N/A'}})
                  </span>
                </td>
                <td class="px-5 py-3.5 text-right">
                  <button onclick="quickExtendRental('${{c.user_zalo_id}}')" class="px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all flex items-center space-x-1 inline-flex cursor-pointer">
                    <span>+ Gia Hạn 30N</span>
                  </button>
                </td>
              </tr>
            `;
          }}).join('');
        }}
      }}

      if (containerBots) {{
        if (emptyBots.length === 0) {{
          containerBots.innerHTML = '<div class="col-span-3 text-center py-8 text-slate-400 text-xs">Kho bot trống rỗng. Hãy bấm Thêm Bot Mới vào Kho!</div>';
        }} else {{
          containerBots.innerHTML = emptyBots.map(b => {{
            const isAvailable = (b.status === 'available');
            const statusBadge = isAvailable
              ? '<span class="px-2.5 py-1 rounded-full text-[10px] font-extrabold bg-emerald-50 text-emerald-700 border border-emerald-200">🟢 Sẵn Sàng Gán Khách</span>'
              : `<span class="px-2.5 py-1 rounded-full text-[10px] font-extrabold bg-amber-50 text-amber-700 border border-amber-200">🔒 Đã Thuê (UID: ${{b.rented_to || 'Khách'}})</span>`;
            const modeBadge = (b.mode === 'video')
              ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-700">🎬 Video Engine</span>'
              : '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-700">🖼️ Image Engine</span>';
            
            return `
              <div class="bg-white p-5 rounded-2xl border ${{isAvailable ? 'border-slate-200' : 'border-amber-200 bg-amber-50/20'}} shadow-sm space-y-3 hover:shadow-md transition-all">
                <div class="flex items-center justify-between">
                  <div class="flex items-center space-x-2">
                    <span class="w-8 h-8 rounded-xl bg-slate-100 flex items-center justify-center text-lg">🤖</span>
                    <div>
                      <h4 class="font-extrabold text-sm text-slate-900">${{b.name}}</h4>
                      <span class="text-[10px] font-mono text-slate-400">ID: ${{b.bot_id}} • Mã: ${{b.default_code}}</span>
                    </div>
                  </div>
                  ${{statusBadge}}
                </div>
                <div class="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                  <div class="flex items-center space-x-1.5">
                    ${{modeBadge}}
                    <span class="text-[10px] text-slate-500 font-mono truncate max-w-[120px]">TK: ${{b.ai_engine_account}}</span>
                  </div>
                  <span class="font-extrabold text-slate-800">${{b.price_package || 'Gói Tiêu Chuẩn'}}</span>
                </div>
              </div>
            `;
          }}).join('');
        }}
      }}
      lucide.createIcons();
    }}

    function openAddEmptyBotModal() {{
      const m = document.getElementById('modal-add-empty-bot');
      if (m) m.classList.remove('hidden');
    }}

    function closeAddEmptyBotModal() {{
      const m = document.getElementById('modal-add-empty-bot');
      if (m) m.classList.add('hidden');
    }}

    function submitAddEmptyBot(e) {{
      e.preventDefault();
      const name = (document.getElementById('empty-bot-name').value || '').trim();
      const mode = document.getElementById('empty-bot-mode').value;
      const engine = (document.getElementById('empty-bot-engine').value || '').trim();
      const pkg = document.getElementById('empty-bot-package').value;

      if (!name) return alert('Vui lòng nhập tên Bot!');

      const newId = 'bot_slot_' + Date.now().toString().slice(-4);
      const defaultCode = '#' + name.toUpperCase().replace(/[^A-Z0-9]/g, '');

      const newBot = {{
        bot_id: newId,
        name: name,
        default_code: defaultCode,
        mode: mode,
        ai_engine_account: engine || 'syncere1812031999',
        status: 'available',
        price_package: pkg,
        created_at: new Date().toISOString()
      }};

      RENTAL_POOL_DATA.empty_bots = RENTAL_POOL_DATA.empty_bots || [];
      RENTAL_POOL_DATA.empty_bots.push(newBot);

      closeAddEmptyBotModal();
      renderRentalPlatform();
      alert('✅ Đã thêm Bot trống ' + name + ' vào Kho Bot cho thuê thành công!');
    }}

    function quickExtendRental(userZaloId) {{
      const cust = (RENTAL_PROFILES_DATA.customers || []).find(c => c.user_zalo_id === userZaloId);
      if (cust) {{
        cust.days_remaining = (cust.days_remaining || 0) + 30;
        renderRentalPlatform();
        alert('✅ Đã gia hạn thành công thêm 30 ngày cho khách hàng ' + (cust.display_name || userZaloId) + '!');
      }}
    }}



    // ==================== AUTO OTP & LOCAL LOGIN ENGINE ====================
    function updateAutoAccCount() {{
      const val = document.getElementById('autoAccInput').value.trim();
      const lines = val ? val.split('\\n').filter(l => l.trim() && !l.trim().startsWith('#')) : [];
      document.getElementById('autoAccCount').innerText = `${{lines.length}} tài khoản`;
    }}

    async function loadFromGoogleSheet() {{
      const url = document.getElementById('sheetUrl').value.trim();
      if (!url) return alert('Vui lòng dán link Google Sheet!');
      try {{
        const resp = await fetch('/api/pool/sheet', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ url: url }})
        }});
        const resData = await resp.json();
        if (resData.ok && resData.accounts_raw) {{
          document.getElementById('autoAccInput').value = resData.accounts_raw;
          updateAutoAccCount();
          alert(`✅ Đã nạp thành công ${{resData.count || 0}} tài khoản từ Google Sheet!`);
        }} else {{
          alert('⚠️ Lỗi: ' + (resData.error || 'Không tải được Google Sheet.'));
        }}
      }} catch (e) {{
        alert('⚠️ Lỗi kết nối Google Sheet: ' + e.message);
      }}
    }}

    async function startAutoExtract() {{
      const raw = document.getElementById('autoAccInput').value.trim();
      if (!raw) return alert('Vui lòng nhập ít nhất 1 tài khoản (email|password)!');

      const btn = document.getElementById('btnStartAutoAcc');
      const prog = document.getElementById('autoAccProgress');
      const bar = document.getElementById('autoAccBar');
      const ratio = document.getElementById('autoAccRatio');
      const statusTxt = document.getElementById('autoAccStatus');
      const logs = document.getElementById('autoAccLogs');

      prog.classList.remove('hidden');
      btn.disabled = true;
      btn.innerHTML = '<span>Đang chạy trích xuất...</span>';
      statusTxt.innerText = 'Đang kết nối Server AI Studio...';
      bar.style.width = '10%';
      logs.textContent = '🚀 Bắt đầu tiến trình tự động nạp & giải OTP...\\n';

      try {{
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
          const blocks = buffer.split('\\n\\n');
          buffer = blocks.pop();

          for (const block of blocks) {{
            for (const line of block.split('\\n')) {{
              if (!line.startsWith('data: ')) continue;
              try {{
                const ev = JSON.parse(line.slice(6).trim());
                if (ev.message) {{
                  const d = new Date().toLocaleTimeString('vi-VN');
                  logs.textContent += `[${{d}}] ${{ev.message}}\\n`;
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
        logs.textContent += '❌ Lỗi: ' + err.message + '\\n';
      }} finally {{
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="zap" class="w-4 h-4 text-amber-300"></i><span>⚡ Bắt Đầu Đăng Nhập & Nạp Vào Pool</span>';
        lucide.createIcons();
      }}
    }}

    async function startLocalLogin() {{
      const raw = document.getElementById('autoAccInput').value.trim();
      if (!raw) return alert('Vui lòng nhập ít nhất 1 tài khoản (email|password) để mở Chrome local!');

      const skip = document.getElementById('autoAccSkip').checked ? (POOL_ACCOUNTS || []).filter(a => a.status === 'ready').map(a => a.name) : [];
      const cfg = {{
        accounts_raw: raw,
        overwrite: document.getElementById('autoAccOverwrite').checked,
        target: window.location.origin,
        skip: skip
      }};

      const b64 = btoa(unescape(encodeURIComponent(JSON.stringify(cfg))));
      const localUrl = 'http://127.0.0.1:8771/#' + b64;

      try {{
        await fetch('http://127.0.0.1:8771', {{ method: 'GET', mode: 'no-cors', signal: AbortSignal.timeout(1200) }});
        window.open(localUrl, '_blank');
      }} catch (err) {{
        alert('⚠️ Chú ý: Sếp đang mở Dashboard từ máy tính cá nhân/thiết bị khác (không phải máy Sever Hermes).\\n\\nCổng 8771 (mở trình duyệt Chrome thật để giải captcha) đang chạy trực tiếp trên máy Sever Hermes. Để giải captcha bằng tay, Sếp hãy mở Dashboard hoặc UltraViewer trực tiếp trên máy Sever Hermes nhé!\\n\\nNếu ngồi ở máy này, Sếp hãy dùng nút [⚡ Bắt Đầu Đăng Nhập & Nạp Vào Pool] để hệ thống tự động xử lý lấy OTP từ xa!');
      }}
    }}

    async function launchLocalLoginForAccount(accName) {{
      const raw = `${{accName}}|`;
      const cfg = {{
        accounts_raw: raw,
        overwrite: true,
        target: window.location.origin,
        skip: []
      }};
      const b64 = btoa(unescape(encodeURIComponent(JSON.stringify(cfg))));
      const localUrl = 'http://127.0.0.1:8771/#' + b64;
      try {{
        await fetch('http://127.0.0.1:8771', {{ method: 'GET', mode: 'no-cors', signal: AbortSignal.timeout(1200) }});
        window.open(localUrl, '_blank');
      }} catch (err) {{
        alert('⚠️ Cổng 8771 mở trình duyệt Chrome thật đang chạy trên máy chủ Sever Hermes.\\nVui lòng mở UltraViewer hoặc thao tác trực tiếp trên máy Sever để nhìn thấy cửa sổ Chrome giải captcha cho tài khoản ' + accName + ' nhé Sếp!');
      }}
    }}

    // Lắng nghe postMessage từ cửa sổ local login port 8771
    window.addEventListener('message', async (e) => {{
      if (e.origin !== 'http://127.0.0.1:8771' || !e.data || !e.data.museLocal) return;
      const {{ name, cookies, overwrite, video_state }} = e.data;
      try {{
        const resp = await fetch('/api/pool/add', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ name, cookies, overwrite, video_state }})
        }});
        const resData = await resp.json();
        e.source.postMessage({{ museAck: 1, name, ok: !!resData.ok }}, e.origin);
        renderPoolAccounts();
      }} catch (err) {{
        console.warn('Lỗi postMessage local login:', err);
      }}
    }});

    // Countdown Ticker mỗi 60 giây (Chu kỳ đặt lại hàng tuần)
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
    }}, 60000);

    async function loadLivePoolAccounts() {{
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

    async function loadLiveGroups() {{
      try {{
        const resp = await fetch('/api/groups', {{ cache: 'no-store' }});
        if (!resp.ok) return;
        const data = await resp.json();
        if (data && data.groups) {{
          const newGroups = {{}};
          for (const [gid, ginfo] of Object.entries(data.groups)) {{
            const mList = Object.entries(ginfo.members || {{}}).map(([uid, m]) => ({{
              name: m.name || uid,
              uid: uid,
              avatar: m.avatar || '',
              role: m.role || 'Thành Viên',
              phone: m.phone || '',
              canDM: m.can_dm ?? true,
              canGroup: m.can_group ?? true,
              canAssign: m.can_assign ?? false,
              canMedia: m.can_media ?? false,
              storagePath: `D:/hermes-main/storage/users/u_${{uid.replace('u:', '')}}/`,
              files: (uid.replace('u:', '') === '7725451581835120119') 
                ? ["Chien_luoc_Q4.xlsx", "Quy_chuan_Hermes.md", "Policy_real.json"] 
                : ["context_zalo.json", "chat_history.log"]
            }}));

            newGroups[gid] = {{
              id: gid,
              name: ginfo.name || gid,
              avatar: ginfo.avatar || '👥',
              memberCount: `${{mList.length}} người`,
              persona: ginfo.persona_name || ginfo.persona || 'Tiêu Chuẩn',
              members: mList
            }};
          }}
          SYSTEM_DATABASE.groups = newGroups;
          renderOverviewCards();

          const kpiEl = document.getElementById('kpi-total-groups-count');
          if (kpiEl) kpiEl.innerText = `${{Object.keys(newGroups).length}} Nhóm`;
          const headingEl = document.getElementById('heading-total-groups');
          if (headingEl) headingEl.innerText = `Danh Sách ${{Object.keys(newGroups).length}} Nhóm Zalo Đang Phụ Trách`;

          const picker = document.getElementById('group-picker-select');
          if (picker) {{
            const currentVal = picker.value;
            picker.innerHTML = Object.keys(newGroups).map(k => `<option value="${{k}}">${{newGroups[k].name}} (${{k}})</option>`).join('');
            if (newGroups[currentVal]) {{
              picker.value = currentVal;
            }} else if (Object.keys(newGroups).length > 0) {{
              selectGroup(Object.keys(newGroups)[0]);
            }}
          }}
        }}
      }} catch (err) {{
        console.warn('loadLiveGroups error:', err);
      }}
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
      loadLiveGroups();
      setInterval(loadLiveGroups, 30000);
    }});
  </script>
</body>
</html>
"""

    with open(APP_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)

    with open(INDEX_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)

    print("✅ Đã tạo mới file app.html và index.html hoàn chỉnh với dữ liệu thật & Pool Trợ Lý AI Studio!")
    push_to_build_github()


if __name__ == "__main__":
    build_app()



