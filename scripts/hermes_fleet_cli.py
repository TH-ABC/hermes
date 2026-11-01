#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
========================================================================================
HERMES ENTERPRISE FLEET MANAGER & TERMINAL SUPERVISOR (CLI)
========================================================================================
Quản lý, điều phối và giám sát toàn diện 6 tiến trình lõi Sever Hermes:
  1. [POOL-8770]   Studio AI Engine Pool (Cổng 8770)
  2. [LOGIN-8771]  Local Login & Captcha Server (Cổng 8771)
  3. [ZALO-3050]   Hermes Gateway & Zalo Bridge (Cổng 3050)
  4. [HERMES-8999] Sever Hermes Central Receiver (Cổng 8999)
  5. [AUTO-SYNC]   Auto-Sync Enterprise Daemon (Đồng bộ ngầm 24/7)
  6. [ATG-WAKEUP]  @ATG Zalo Wakeup Listener (Bộ đánh thức Kỹ Sư Trưởng)

Chế độ vận hành Terminal CLI:
  - Bất kỳ Terminal nào (PowerShell, CMD, Windows Terminal) chạy lệnh này đều có thể:
    + Tự động kết nối (Connect/Attach) vào hệ thống đang chạy ngầm.
    + Kiểm tra ma trận trạng thái (PID, Port, RAM, CPU, Uptime, Health).
    + Theo sát (Tail/Follow) luồng Log hợp nhất thời gian thực có gắn mã màu riêng.
    + Điều khiển trực tiếp: start / stop / restart từng tiến trình hoặc toàn bộ hệ thống.
    + Thoát bằng Ctrl+C hoặc phím Q mà KHÔNG làm gián đoạn các dịch vụ đang chạy.
========================================================================================
"""

import sys
import os
import time
import signal
import argparse
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

import psutil
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.prompt import Prompt

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()

# Đường dẫn thư mục chuẩn
BASE_DIR = Path("D:/hermes-main")
ROOT_DIR = BASE_DIR / "hermes-main"
STORAGE_DIR = BASE_DIR / "storage"
LOGS_DIR = STORAGE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PYTHON_EXE = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)

# Cấu hình file log nền fallback
BRAIN_TASKS_DIR = Path(r"C:\Users\ADMIN\.gemini\antigravity\brain\512a16ff-3a83-46b9-afa0-fa1116dbe759\.system_generated\tasks")
FALLBACK_TASK_MAP = {
    "pool": "task-6528.log",
    "login": "task-4399.log",
    "gateway": "task-6399.log",
    "sever": "task-5248.log",
    "sync": "task-5740.log",
    "atg": "task-6560.log"
}

SERVICES = {
    "pool": {
        "id": "pool",
        "num": "1",
        "name": "Studio AI Engine Pool",
        "tag": "POOL-8770",
        "color": "magenta",
        "port": 8770,
        "cwd": str(ROOT_DIR / "museai"),
        "cmd": [str(PYTHON_EXE), "-u", "bridge/pool.py", "--port", "8770", "--cookies-dir", "cookies"],
        "match_pattern": "bridge/pool.py",
        "log_file": LOGS_DIR / "pool.log",
        "desc": "Cụm tài khoản suy luận AI, thị giác ảnh & render video"
    },
    "login": {
        "id": "login",
        "num": "2",
        "name": "Local Login & Captcha Server",
        "tag": "LOGIN-8771",
        "color": "cyan",
        "port": 8771,
        "cwd": str(ROOT_DIR / "museai"),
        "cmd": [str(PYTHON_EXE), "-u", "tools/local_login_server.py", "--port", "8771"],
        "match_pattern": "local_login_server.py",
        "log_file": LOGS_DIR / "login.log",
        "desc": "Cổng nạp cookie, giải captcha và cấp tài khoản mới"
    },
    "gateway": {
        "id": "gateway",
        "num": "3",
        "name": "Hermes Gateway & Zalo Bridge",
        "tag": "ZALO-3050",
        "color": "blue",
        "port": 3050,
        "cwd": str(ROOT_DIR),
        "cmd": [str(PYTHON_EXE), "-u", "hermes_cli/main.py", "gateway", "run"],
        "match_pattern": "hermes_cli/main.py",
        "log_file": LOGS_DIR / "gateway.log",
        "desc": "Trục kết nối Zalo Bot Bth điều hành tổng"
    },
    "sever": {
        "id": "sever",
        "num": "4",
        "name": "Sever Hermes Central Receiver",
        "tag": "HERMES-8999",
        "color": "green",
        "port": 8999,
        "cwd": str(ROOT_DIR),
        "cmd": [str(PYTHON_EXE), "-u", "scripts/sever_hermes_receiver.py"],
        "match_pattern": "sever_hermes_receiver.py",
        "log_file": LOGS_DIR / "sever.log",
        "desc": "Bộ não trung tâm điều phối và quản lý Assistants API"
    },
    "sync": {
        "id": "sync",
        "num": "5",
        "name": "Auto-Sync Enterprise Daemon",
        "tag": "AUTO-SYNC",
        "color": "yellow",
        "port": None,
        "cwd": str(ROOT_DIR),
        "cmd": [str(PYTHON_EXE), "-u", "scripts/auto_sync_enterprise_daemon.py"],
        "match_pattern": "auto_sync_enterprise_daemon.py",
        "log_file": LOGS_DIR / "sync.log",
        "desc": "Tự động quét nhóm, cookie, hạn ngạch & đồng bộ dashboard"
    },
    "atg": {
        "id": "atg",
        "num": "6",
        "name": "@ATG Zalo Wakeup Listener",
        "tag": "ATG-WAKEUP",
        "color": "red",
        "port": None,
        "cwd": str(ROOT_DIR),
        "cmd": [str(PYTHON_EXE), "-u", "scripts/atg_zalo_listener.py", "--listen", "--wait", "86400"],
        "match_pattern": "atg_zalo_listener.py",
        "log_file": LOGS_DIR / "atg.log",
        "desc": "Cảm biến đánh thức Kỹ Sư Trưởng ATG khi nhận tag @ATG"
    }
}


def find_active_log_file(svc_key: str) -> Path:
    """Xác định file log đang hoạt động (ưu tiên storage/logs, fallback sang task log hiện hữu)."""
    custom_log = SERVICES[svc_key]["log_file"]
    if custom_log.exists() and custom_log.stat().st_size > 0:
        return custom_log

    fb_name = FALLBACK_TASK_MAP.get(svc_key)
    if fb_name and BRAIN_TASKS_DIR.exists():
        fb_path = BRAIN_TASKS_DIR / fb_name
        if fb_path.exists():
            return fb_path

    if not custom_log.exists():
        try:
            custom_log.touch()
        except Exception:
            pass
    return custom_log


def find_process_for_service(svc_key: str) -> Optional[psutil.Process]:
    """Tìm tiến trình đang chạy tương ứng với dịch vụ (theo Port hoặc Cmdline)."""
    cfg = SERVICES[svc_key]
    port = cfg.get("port")
    match_pattern = cfg.get("match_pattern")

    # 1. Kiểm tra theo Listening Port
    if port:
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                    if conn.pid:
                        try:
                            p = psutil.Process(conn.pid)
                            if p.is_running():
                                return p
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
        except Exception:
            pass

    # 2. Kiểm tra theo Cmdline
    if match_pattern:
        try:
            for p in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmd = " ".join(p.info["cmdline"] or [])
                    if "hermes_fleet_cli.py" in cmd:
                        continue
                    if match_pattern in cmd:
                        return p
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

    return None


def get_service_status(svc_key: str) -> Dict[str, Any]:
    """Lấy thông tin trạng thái chi tiết của 1 dịch vụ."""
    cfg = SERVICES[svc_key]
    proc = find_process_for_service(svc_key)
    if proc and proc.is_running():
        try:
            with proc.oneshot():
                pid = proc.pid
                cpu = proc.cpu_percent(interval=None)
                mem = proc.memory_info().rss / (1024 * 1024)  # MB
                create_t = datetime.fromtimestamp(proc.create_time())
                uptime = str(datetime.now() - create_t).split(".")[0]
                status_str = "ONLINE (Active)"
                return {
                    "key": svc_key,
                    "num": cfg["num"],
                    "name": cfg["name"],
                    "tag": cfg["tag"],
                    "color": cfg["color"],
                    "port": cfg["port"],
                    "desc": cfg["desc"],
                    "is_running": True,
                    "pid": pid,
                    "cpu": f"{cpu:.1f}%",
                    "mem": f"{mem:.1f} MB",
                    "uptime": uptime,
                    "status": status_str,
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return {
        "key": svc_key,
        "num": cfg["num"],
        "name": cfg["name"],
        "tag": cfg["tag"],
        "color": cfg["color"],
        "port": cfg["port"],
        "desc": cfg["desc"],
        "is_running": False,
        "pid": "-",
        "cpu": "-",
        "mem": "-",
        "uptime": "-",
        "status": "STOPPED",
    }


def render_status_table() -> Table:
    """Tạo bảng ma trận hiển thị trạng thái 6 dịch vụ."""
    table = Table(title="🚀 SEVER HERMES FLEET - MA TRẬN 6 TIẾN TRÌNH LÕI", title_style="bold cyan", border_style="bright_black")
    table.add_column("STT", justify="center", style="bold white")
    table.add_column("Mã Tiến Trình", style="bold", justify="left")
    table.add_column("Cổng", justify="center")
    table.add_column("Trạng Thái", justify="center")
    table.add_column("PID", justify="right")
    table.add_column("RAM", justify="right")
    table.add_column("CPU", justify="right")
    table.add_column("Thời Gian Chạy", justify="center")
    table.add_column("Nhiệm Vụ Chính", style="dim", justify="left")

    for key in SERVICES:
        st = get_service_status(key)
        color = st["color"]
        num_str = f"[{color}][{st['num']}][/{color}]"
        tag_str = f"[{color}]{st['tag']}[/{color}]"
        port_str = f"[bold white]{st['port']}[/bold white]" if st["port"] else "[dim]-[/dim]"
        status_str = f"[bold green]● {st['status']}[/bold green]" if st["is_running"] else f"[bold red]○ {st['status']}[/bold red]"
        
        table.add_row(
            num_str,
            tag_str,
            port_str,
            status_str,
            str(st["pid"]),
            str(st["mem"]),
            str(st["cpu"]),
            str(st["uptime"]),
            st["desc"]
        )

    return table


def start_service(svc_key: str) -> bool:
    """Khởi động một dịch vụ cụ thể dưới dạng Background Subprocess."""
    cfg = SERVICES[svc_key]
    existing = find_process_for_service(svc_key)
    if existing:
        console.print(f"[yellow]⚠️ Dịch vụ [{cfg['tag']}] đã đang chạy với PID {existing.pid}![/yellow]")
        return True

    log_path = cfg["log_file"]
    console.print(f"[cyan]🚀 Đang khởi chạy [{cfg['tag']}]...[/cyan]")
    try:
        log_f = open(log_path, "a", encoding="utf-8", errors="replace")
        log_f.write(f"\n\n=== KHỞI CHẠY BỞI HERMES FLEET CLI LÚC {datetime.now().isoformat()} ===\n")
        log_f.flush()
        log_f.close()

        if sys.platform == "win32":
            # Khởi chạy qua WMI Win32_Process để tách hoàn toàn khỏi Job Object của IDE
            cmd_joined = " ".join([f'"{c}"' if " " in str(c) else str(c) for c in cfg["cmd"]])
            wmi_cmd = f'cmd.exe /c cd /d "{cfg["cwd"]}" && {cmd_joined} >> "{log_path}" 2>&1'
            ps_script = f'$arg = @{{CommandLine = \'{wmi_cmd}\'}}; (Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments $arg).ProcessId'
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
            time.sleep(2.0)
            new_p = find_process_for_service(svc_key)
            if new_p:
                console.print(f"[bold green]✔ [{cfg['tag']}] đã chạy độc lập (PID {new_p.pid})! Ghi log tại: {log_path.name}[/bold green]")
                return True
            else:
                console.print(f"[bold red]❌ [{cfg['tag']}] khởi chạy thất bại![/bold red]")
                return False
        else:
            proc = subprocess.Popen(
                cfg["cmd"],
                cwd=cfg["cwd"],
                stdout=open(log_path, "a", encoding="utf-8", errors="replace"),
                stderr=subprocess.STDOUT,
                close_fds=True
            )
            time.sleep(1.0)
            if proc.poll() is None:
                console.print(f"[bold green]✔ [{cfg['tag']}] đã chạy thành công (PID {proc.pid})! Ghi log tại: {log_path.name}[/bold green]")
                return True
            else:
                console.print(f"[bold red]❌ [{cfg['tag']}] khởi chạy thất bại (mã thoát: {proc.returncode})![/bold red]")
                return False
    except Exception as e:
        console.print(f"[bold red]❌ Lỗi khi khởi chạy [{cfg['tag']}]: {e}[/bold red]")
        return False


def stop_service(svc_key: str) -> bool:
    """Dừng an toàn một dịch vụ."""
    cfg = SERVICES[svc_key]
    proc = find_process_for_service(svc_key)
    if not proc:
        console.print(f"[dim]ℹ Dịch vụ [{cfg['tag']}] không chạy.[/dim]")
        return True

    console.print(f"[yellow]🛑 Đang dừng [{cfg['tag']}] (PID {proc.pid})...[/yellow]")
    try:
        try:
            for child in proc.children(recursive=True):
                child.terminate()
        except Exception:
            pass

        proc.terminate()
        try:
            proc.wait(timeout=4)
        except psutil.TimeoutExpired:
            proc.kill()
        console.print(f"[bold green]✔ Đã dừng [{cfg['tag']}] thành công![/bold green]")
        return True
    except Exception as e:
        console.print(f"[bold red]❌ Lỗi khi dừng [{cfg['tag']}]: {e}[/bold red]")
        return False


def restart_service(svc_key: str):
    """Khởi động lại một dịch vụ."""
    stop_service(svc_key)
    time.sleep(1.0)
    start_service(svc_key)


def start_all():
    """Khởi động toàn bộ các dịch vụ chưa chạy."""
    console.print(Panel("[bold cyan]🚀 KHỞI ĐỘNG HỆ THỐNG TOÀN DIỆN (6 TIẾN TRÌNH)[/bold cyan]", border_style="cyan"))
    for key in SERVICES:
        start_service(key)
    time.sleep(1.0)
    console.print("\n")
    console.print(render_status_table())


def stop_all():
    """Dừng toàn bộ 6 dịch vụ."""
    console.print(Panel("[bold yellow]🛑 DỪNG TOÀN BỘ 6 TIẾN TRÌNH SEVER HERMES[/bold yellow]", border_style="yellow"))
    for key in reversed(list(SERVICES.keys())):
        stop_service(key)


def restart_all():
    """Khởi động lại toàn bộ 6 dịch vụ."""
    stop_all()
    time.sleep(1.5)
    start_all()


def tail_logs(follow: bool = True, filter_key: Optional[str] = None):
    """Theo sát luồng Log hợp nhất thời gian thực của các tiến trình."""
    console.print(Panel(
        f"[bold green]📡 KẾT NỐI VÀ THEO SÁT LOG THỜI GIAN THỰC (Nhấn Ctrl+C để thoát theo dõi)[/bold green]\n"
        f"Lọc dịch vụ: [cyan]{filter_key.upper() if filter_key else 'TOÀN BỘ (TẤT CẢ 6 DỊCH VỤ)'}[/cyan]\n"
        f"[dim]Lưu ý: Thoát Terminal này không ảnh hưởng đến các tiến trình đang chạy ngầm.[/dim]",
        border_style="green"
    ))

    file_handles = {}
    service_keys = [filter_key] if filter_key and filter_key in SERVICES else list(SERVICES.keys())

    for k in service_keys:
        log_p = find_active_log_file(k)
        try:
            f = open(log_p, "r", encoding="utf-8", errors="replace")
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 3072), os.SEEK_SET)
            file_handles[k] = f
        except Exception as e:
            console.print(f"[dim yellow]Không thể mở log cho {k}: {e}[/dim yellow]")

    try:
        while True:
            had_data = False
            for k, f in list(file_handles.items()):
                lines = f.readlines()
                if lines:
                    had_data = True
                    cfg = SERVICES[k]
                    color = cfg["color"]
                    tag = cfg["tag"]
                    for line in lines:
                        clean_line = line.strip()
                        if clean_line:
                            now_str = datetime.now().strftime("%H:%M:%S")
                            console.print(f"[dim]{now_str}[/dim] [{color} bold][{tag}][/] {clean_line}")

            if not follow:
                break
            if not had_data:
                time.sleep(0.3)
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Đã dừng theo sát log. Các tiến trình vẫn tiếp tục chạy ngầm an toàn![/yellow]")
    finally:
        for f in file_handles.values():
            try:
                f.close()
            except Exception:
                pass


def live_dashboard():
    """Bảng điều khiển Live Dashboard tương tác thời gian thực."""
    console.clear()
    with Live(render_status_table(), refresh_per_second=1, screen=True) as live:
        try:
            while True:
                live.update(render_status_table())
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass


def interactive_menu():
    """Menu CLI tương tác trực tiếp khi người dùng mở terminal và gõ hermes-fleet."""
    while True:
        console.clear()
        console.print(Panel(
            "[bold cyan]🚀 SEVER HERMES ENTERPRISE - BỘ ĐIỀU PHỐI FLEET CLI[/bold cyan]\n"
            "[dim]Mọi Terminal kết nối vào đều có thể kiểm soát và theo sát toàn bộ hệ thống.[/dim]",
            border_style="cyan"
        ))
        console.print(render_status_table())
        console.print("\n[bold yellow]👉 LỰA CHỌN THAO TÁC / THEO SÁT HỆ THỐNG:[/bold yellow]")
        console.print("  [bold green][A][/bold green] Theo sát Log hợp nhất [bold cyan]TOÀN BỘ 6 TIẾN TRÌNH[/bold cyan] (Live Stream)")
        console.print("  [bold magenta][1][/bold magenta] Theo sát Log: Studio AI Engine Pool (8770)")
        console.print("  [bold cyan][2][/bold cyan] Theo sát Log: Local Login & Captcha Server (8771)")
        console.print("  [bold blue][3][/bold blue] Theo sát Log: Hermes Gateway Zalo Bot (3050)")
        console.print("  [bold green][4][/bold green] Theo sát Log: Sever Hermes Central Receiver (8999)")
        console.print("  [bold yellow][5][/bold yellow] Theo sát Log: Auto-Sync Enterprise Daemon")
        console.print("  [bold red][6][/bold red] Theo sát Log: @ATG Zalo Wakeup Listener")
        console.print("  [bold white][D][/bold white] Mở Bảng Đo Sức Khỏe Trực Tiếp (Live Refresh Dashboard)")
        console.print("  [bold white][S][/bold white] Khởi động các tiến trình đang tắt (Start Missing)")
        console.print("  [bold white][R][/bold white] Khởi động lại toàn bộ (Restart All)")
        console.print("  [bold white][Q][/bold white] Thoát Terminal (Tiến trình vẫn chạy ngầm 24/7)")

        choice = Prompt.ask("\nNhập lựa chọn của Sếp", default="A").strip().lower()

        if choice in ("a", "all"):
            tail_logs(follow=True, filter_key=None)
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "1":
            tail_logs(follow=True, filter_key="pool")
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "2":
            tail_logs(follow=True, filter_key="login")
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "3":
            tail_logs(follow=True, filter_key="gateway")
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "4":
            tail_logs(follow=True, filter_key="sever")
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "5":
            tail_logs(follow=True, filter_key="sync")
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice == "6":
            tail_logs(follow=True, filter_key="atg")
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice in ("d", "dashboard", "live"):
            live_dashboard()
        elif choice in ("s", "start"):
            start_all()
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice in ("r", "restart"):
            restart_all()
            Prompt.ask("\nNhấn Enter để quay lại menu...")
        elif choice in ("q", "quit", "exit"):
            console.print("[green]👋 Đã thoát Terminal Supervisor. Hệ thống Sever Hermes vẫn đang chạy ngầm 24/7![/green]")
            break
        else:
            console.print("[red]Lựa chọn không hợp lệ, vui lòng thử lại![/red]")
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(
        description="Hermes Enterprise Fleet CLI Supervisor - Quản trị 6 tiến trình lõi Sever Hermes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  .\\hermes-fleet                   # Mở Menu CLI tương tác trực tiếp
  .\\hermes-fleet status            # Xem nhanh bảng trạng thái 6 tiến trình
  .\\hermes-fleet start             # Khởi động toàn bộ các tiến trình chưa chạy
  .\\hermes-fleet stop              # Dừng toàn bộ 6 tiến trình
  .\\hermes-fleet restart           # Khởi động lại toàn bộ
  .\\hermes-fleet logs -f           # Theo sát log hợp nhất thời gian thực
  .\\hermes-fleet logs -f pool      # Theo sát log riêng của Studio Pool
  .\\hermes-fleet live              # Mở màn hình Live Dashboard thời gian thực
        """
    )
    parser.add_argument("command", nargs="?", default=None, choices=[None, "menu", "status", "start", "stop", "restart", "logs", "live", "watch", "attach"], help="Lệnh thực thi")
    parser.add_argument("service", nargs="?", default=None, help="Tên dịch vụ cụ thể: pool, login, gateway, sever, sync, atg")
    parser.add_argument("-f", "--follow", action="store_true", default=True, help="Theo sát log liên tục (dùng cho logs)")

    args = parser.parse_args()

    # Nếu không truyền lệnh và stdout là TTY -> mở Interactive Menu
    if args.command is None or args.command in ("menu", "attach"):
        if sys.stdin.isatty():
            interactive_menu()
            return
        else:
            args.command = "status"

    if args.command == "status":
        console.print(render_status_table())
        console.print("\n[dim]Gợi ý: Dùng lệnh '.\\hermes-fleet logs -f' để theo sát log trực tiếp, hoặc '.\\hermes-fleet menu' để mở menu tương tác.[/dim]")

    elif args.command == "start":
        if args.service:
            if args.service in SERVICES:
                start_service(args.service)
            else:
                console.print(f"[red]❌ Dịch vụ không hợp lệ. Chọn một trong: {list(SERVICES.keys())}[/red]")
        else:
            start_all()

    elif args.command == "stop":
        if args.service:
            if args.service in SERVICES:
                stop_service(args.service)
            else:
                console.print(f"[red]❌ Dịch vụ không hợp lệ. Chọn một trong: {list(SERVICES.keys())}[/red]")
        else:
            stop_all()

    elif args.command == "restart":
        if args.service:
            if args.service in SERVICES:
                restart_service(args.service)
            else:
                console.print(f"[red]❌ Dịch vụ không hợp lệ. Chọn một trong: {list(SERVICES.keys())}[/red]")
        else:
            restart_all()

    elif args.command in ("logs", "watch"):
        tail_logs(follow=args.follow, filter_key=args.service)

    elif args.command == "live":
        live_dashboard()


if __name__ == "__main__":
    main()
