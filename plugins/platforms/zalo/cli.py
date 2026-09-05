"""
`hermes zalo` CLI — QR pairing, status, and logout for the Zalo bridge.

Modeled on plugins/platforms/photon/cli.py's subparser + dispatch pattern.
Unlike Photon (which authenticates against a hosted API), pairing here means
launching the local Node.js bridge in ``--mode pair`` and watching its
stdout for the marker lines it prints while zca-js does a QR-code Zalo Web
login (see scripts/zalo-bridge/bridge.js).
"""

import argparse
import json
import os
import queue
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from hermes_cli.cli_output import (
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
    prompt,
    prompt_yes_no,
)
from hermes_cli.config import save_env_value, write_platform_config_field
from hermes_constants import find_node_executable, get_hermes_dir, with_hermes_node_path

from .adapter import (
    _kill_port_process,
    _kill_stale_bridge_by_pidfile,
    check_zalo_requirements,
    resolve_zalo_bridge_dir,
)

_PAIR_TIMEOUT_SECONDS = 120


def _session_path() -> Path:
    return Path(get_hermes_dir("platforms/zalo/session", "zalo/session"))


def _bridge_port() -> int:
    return int(os.getenv("ZALO_BRIDGE_PORT") or "3050")


def _print_risk_warnings() -> None:
    """Printed on every `setup` run — pairing risk isn't a one-time disclosure."""
    print_warning(
        "Zalo has no official bot API for personal accounts that can join a "
        "group as a normal member. This bridge drives your real Zalo account "
        "through zca-js, an unofficial, reverse-engineered client. Automating "
        "a personal account this way can get it temporarily locked or banned "
        "by Zalo — use a secondary/dedicated account if you have one, not "
        "your primary."
    )
    print_warning(
        "Zalo allows only ONE active web-listener session per account at a "
        "time. Opening Zalo Web or Zalo Desktop with the same account will "
        "silently kick this bridge offline (and vice versa) — don't run both."
    )


def _ensure_bridge_deps(bridge_dir: Path) -> bool:
    node_modules = bridge_dir / "node_modules"
    if node_modules.exists():
        return True
    npm_bin = find_node_executable("npm") or "npm"
    print_info("Installing Zalo bridge dependencies (first run)...")
    try:
        result = subprocess.run(
            [npm_bin, "install", "--silent"],
            cwd=str(bridge_dir),
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=300,
            env=with_hermes_node_path(),
        )
    except Exception as e:
        print_error(f"npm install failed to run: {e}")
        return False
    if result.returncode != 0:
        print_error(f"npm install failed:\n{result.stderr}")
        return False
    print_success("Dependencies installed.")
    return True


def _open_path_best_effort(path: str) -> None:
    """Best-effort OS-native "open" of the QR image — never fatal if it fails."""
    try:
        import platform as _platform

        system = _platform.system()
        if system == "Darwin":
            subprocess.run(["open", path], check=False, timeout=5)
        elif system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", path], check=False, timeout=5)
    except Exception:
        pass


def _run_pairing(bridge_path: Path, session_path: Path, port: int) -> Optional[str]:
    """Spawn the bridge in --mode pair and watch stdout for marker lines.

    Returns the paired-account uid on success, or None on failure/timeout.
    """
    node_bin = find_node_executable("node") or "node"
    proc = subprocess.Popen(
        [
            node_bin, str(bridge_path),
            "--port", str(port),
            "--session", str(session_path),
            "--mode", "pair",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=with_hermes_node_path(),
    )

    lines: "queue.Queue[Optional[str]]" = queue.Queue()

    def _reader() -> None:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                lines.put(line.rstrip("\n"))
        finally:
            lines.put(None)  # sentinel: process stdout closed

    threading.Thread(target=_reader, daemon=True).start()

    deadline = time.monotonic() + _PAIR_TIMEOUT_SECONDS
    own_uid: Optional[str] = None
    qr_shown = False
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                print_error("Timed out waiting for QR pairing.")
                return None
            try:
                line = lines.get(timeout=remaining)
            except queue.Empty:
                print_error("Timed out waiting for QR pairing.")
                return None

            if line is None:
                # Bridge stdout closed without a PAIRED/PAIR_FAILED marker.
                if own_uid:
                    return own_uid
                print_error("Zalo bridge exited before pairing completed.")
                return None

            if not line.strip():
                continue

            if line.startswith("QR_CODE_PATH:"):
                qr_path = line.split(":", 1)[1].strip()
                qr_shown = True
                print_info(f"Scan this QR code with the Zalo app on your phone: {qr_path}")
                _open_path_best_effort(qr_path)
            elif line.startswith("QR_CODE_SCANNED:"):
                display_name = line.split(":", 1)[1].strip()
                print_success(f"QR scanned as {display_name!r} — confirm the login on your phone...")
            elif line == "QR_CODE_EXPIRED":
                print_error("QR code expired before it was scanned. Run `hermes zalo setup` again.")
                return None
            elif line == "QR_CODE_DECLINED":
                print_error("Login was declined on the phone.")
                return None
            elif line.startswith("PAIRED:"):
                own_uid = line.split(":", 1)[1].strip()
                print_success("Paired successfully!")
                # Contract: bridge.js exits 0 ~500ms after printing PAIRED.
                # Drain remaining output briefly, then stop waiting on it.
                deadline = min(deadline, time.monotonic() + 3)
            elif line.startswith("PAIR_FAILED:"):
                message = line.split(":", 1)[1].strip()
                print_error(f"Pairing failed: {message}")
                return None
            elif line == "ZALO_PAIR_MODE_STARTED":
                if not qr_shown:
                    print_info("Waiting for QR code...")
            else:
                print_info(f"[bridge] {line}")
    finally:
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


def _cmd_setup(args) -> int:
    print_header("Zalo Setup")
    _print_risk_warnings()

    if not check_zalo_requirements():
        print_error("Node.js is required for the Zalo bridge but was not found. Install Node.js and try again.")
        return 1

    bridge_dir = resolve_zalo_bridge_dir()
    bridge_path = bridge_dir / "bridge.js"
    if not bridge_path.exists():
        print_error(f"Zalo bridge script not found at {bridge_path}.")
        return 1

    if not _ensure_bridge_deps(bridge_dir):
        return 1

    session_path = _session_path()
    session_path.mkdir(parents=True, exist_ok=True)
    port = _bridge_port()

    if not prompt_yes_no(
        "This will (re)pair a Zalo account for this bot and will disconnect any "
        "Zalo bridge currently running for this session. Continue?",
        default=True,
    ):
        print_info("Cancelled.")
        return 1

    _kill_stale_bridge_by_pidfile(session_path)
    _kill_port_process(port)
    time.sleep(1)

    print_info("Starting pairing — a QR code will be generated shortly...")
    own_uid = _run_pairing(bridge_path, session_path, port)
    if not own_uid:
        return 1

    try:
        (session_path / "own_id.txt").write_text(own_uid, encoding="utf-8")
    except OSError as e:
        print_warning(f"Paired, but failed to persist own_id.txt ({e}); group @mention "
                       "gating will fall back to name matching only.")

    print_header("Configuration")
    allowed_users = prompt(
        "Zalo user IDs allowed to use the bot (comma-separated, blank = configure later)",
        default="",
    )
    home_channel = prompt(
        "Default chat ID for reminders/cron delivery (e.g. u:123... or g:456..., blank = skip)",
        default="",
    )
    require_mention = prompt_yes_no(
        "Require @mention before the bot responds in group chats? (DMs always respond)",
        default=True,
    )

    if allowed_users.strip():
        save_env_value("ZALO_ALLOWED_USERS", allowed_users.strip())
    if home_channel.strip():
        save_env_value("ZALO_HOME_CHANNEL", home_channel.strip())
    save_env_value("ZALO_REQUIRE_MENTION", "true" if require_mention else "false")
    save_env_value("ZALO_ENABLED", "true")
    try:
        write_platform_config_field("zalo", "enabled", True, raw=True)
    except Exception:
        pass  # config.yaml is optional — env vars alone are sufficient to enable

    print_success("Zalo is paired and enabled.")
    print_info("Start (or restart) the gateway to bring the bot online: `hermes gateway`")
    return 0


def _bridge_health(port: int) -> Optional[dict]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None


def _cmd_status(args) -> int:
    print_header("Zalo Status")

    node_ok = check_zalo_requirements()
    print_success("Node.js found") if node_ok else print_error("Node.js not found")

    session_path = _session_path()
    creds_path = session_path / "zalo_creds.json"
    paired = creds_path.exists()
    print_success(f"Paired (credentials at {creds_path})") if paired else print_warning("Not paired — run `hermes zalo setup`")

    own_id_path = session_path / "own_id.txt"
    if paired:
        if own_id_path.exists():
            print_info(f"Bot uid on file: {own_id_path.read_text(encoding='utf-8').strip()}")
        else:
            print_warning("No own_id.txt on file — @mention gating will use name matching only.")

    port = _bridge_port()
    health = _bridge_health(port)
    if health is None:
        print_warning(f"Bridge not reachable on port {port} (not running)")
    else:
        status = health.get("status", "unknown")
        if status == "connected":
            print_success(f"Bridge running on port {port} — status: connected")
        else:
            print_warning(f"Bridge running on port {port} — status: {status}")
        print_info(f"Queue length: {health.get('queueLength', '?')}, uptime: {health.get('uptime', '?')}s")

    enabled = (os.getenv("ZALO_ENABLED") or "").strip().lower() in {"true", "1", "yes"}
    print_success("ZALO_ENABLED=true") if enabled else print_warning("ZALO_ENABLED is not set to true")
    return 0


def _cmd_logout(args) -> int:
    print_header("Zalo Logout")
    if not prompt_yes_no(
        "This will disconnect the bridge and permanently delete the stored Zalo "
        "session (you'll need to scan a new QR code to reconnect). Continue?",
        default=False,
    ):
        print_info("Cancelled.")
        return 1

    session_path = _session_path()
    port = _bridge_port()

    _kill_stale_bridge_by_pidfile(session_path)
    _kill_port_process(port)

    for name in ("zalo_creds.json", "own_id.txt"):
        try:
            (session_path / name).unlink(missing_ok=True)
        except OSError:
            pass

    save_env_value("ZALO_ENABLED", "false")
    print_success("Zalo session removed and disabled. Run `hermes zalo setup` to pair again.")
    return 0


def register_cli(parser: argparse.ArgumentParser) -> None:
    """Wire up `hermes zalo <command>` subcommands."""
    parser.set_defaults(func=dispatch)
    sub = parser.add_subparsers(dest="zalo_command")
    sub.add_parser("setup", help="Pair a Zalo account via QR code and configure the bot")
    sub.add_parser("status", help="Show Zalo pairing and bridge status")
    sub.add_parser("logout", help="Unpair the Zalo account and remove stored credentials")


def dispatch(args) -> int:
    command = getattr(args, "zalo_command", None) or "setup"
    if command == "setup":
        return _cmd_setup(args)
    if command == "status":
        return _cmd_status(args)
    if command == "logout":
        return _cmd_logout(args)
    print_error(f"Unknown zalo command: {command}")
    return 1


def gateway_setup() -> None:
    """Thin wrapper used as PlatformEntry.setup_fn for `hermes gateway setup`."""
    _cmd_setup(argparse.Namespace(zalo_command="setup"))
