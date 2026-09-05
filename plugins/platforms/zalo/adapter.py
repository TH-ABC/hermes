"""
Zalo platform adapter.

Zalo has no official bot API for personal accounts that can join a group as a
normal member (Zalo OA, the official business API, cannot be added to a group
this way). This adapter therefore talks to a local Node.js bridge
(``scripts/zalo-bridge/``) built on ``zca-js``, an unofficial reverse-engineered
Zalo Web client — architecturally identical in spirit to how WhatsApp is
bridged via Baileys in ``plugins/platforms/whatsapp/adapter.py``, which is the
direct template for everything in this file.

Unlike WhatsApp, Zalo has exactly one transport mode, so there is no shared
behavior mixin here — this adapter owns its own (much smaller) gating logic
directly. It also relies on the gateway's central identity authorization
(``ZALO_ALLOWED_USERS`` / ``ZALO_ALLOW_ALL_USERS``, enforced by the gateway
itself since ``enforces_own_access_policy`` is left at its default False)
rather than re-implementing WhatsApp's local ``dm_policy``/``group_policy``
surface. The only bespoke filtering this adapter does is group *mention*
gating, which is a message-shaping concern the gateway's identity check
doesn't cover.
"""

import asyncio
import logging
import os
import platform
import re
import signal
import subprocess

_IS_WINDOWS = platform.system() == "Windows"
from pathlib import Path
from typing import Any, Dict, Optional

from hermes_cli._subprocess_compat import windows_detach_popen_kwargs
from hermes_constants import (
    find_node_executable,
    get_hermes_dir,
    with_hermes_node_path,
)


def _zenv(name: str, default: str = "") -> str:
    """Read a ZALO_* env var through the profile secret scope.

    Under multiplexing, ``os.getenv`` bypasses the per-profile ``.env`` and
    returns the process-global value (often unset). ``get_secret`` honors the
    active ``_profile_runtime_scope`` so secondary profiles see their own
    configuration. Mirrors WhatsApp's ``_wenv`` (#59739 pattern).
    """
    from agent.secret_scope import UnscopedSecretError, get_secret
    try:
        val = get_secret(name)
    except UnscopedSecretError:
        val = os.getenv(name)
    return val if val is not None else default


logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Bridge process-supervision helpers — ported near-verbatim from
# plugins/platforms/whatsapp/adapter.py (lines 65-281). Kept self-contained
# here rather than extracted to a shared module: that extraction only pays
# off once a third bridge-based platform shows up, and this is a copy-adapt
# job either way since each guard defends a real, previously-hit bug class
# (e.g. a recycled PID once killed a user's browser tab).
# ──────────────────────────────────────────────────────────────────────────


def _listener_pids_on_port(port: int) -> list:
    """PIDs of processes *listening* on ``port`` (POSIX) — never clients.

    Must match only LISTEN sockets, never a client whose connection merely
    involves that port number (e.g. a browser tab on a local dev server
    sharing the port) — see whatsapp/adapter.py for the incident this guards.
    """
    pids: list = []
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5,
        )
        for line in result.stdout.strip().splitlines():
            try:
                pids.append(int(line))
            except ValueError:
                pass
        if pids:
            return pids
    except FileNotFoundError:
        pass  # lsof not installed — fall through to ss
    try:
        result = subprocess.run(
            ["ss", "-ltnHp", f"sport = :{port}"],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5,
        )
        for m in re.finditer(r"pid=(\d+)", result.stdout):
            pids.append(int(m.group(1)))
    except FileNotFoundError:
        pass
    return pids


def _kill_port_process(port: int) -> None:
    """Kill any process *listening* on the given TCP port (a stale bridge)."""
    try:
        if _IS_WINDOWS:
            from hermes_cli._subprocess_compat import windows_hide_flags

            result = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5,
                creationflags=windows_hide_flags(),
            )
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[3] == "LISTENING":
                    local_addr = parts[1]
                    if local_addr.endswith(f":{port}"):
                        try:
                            subprocess.run(
                                ["taskkill", "/PID", parts[4], "/F"],
                                capture_output=True, timeout=5,
                                creationflags=windows_hide_flags(),
                            )
                        except subprocess.SubprocessError:
                            pass
        else:
            for pid in _listener_pids_on_port(port):
                try:
                    os.kill(pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
    except Exception:
        pass


def _bridge_pid_is_ours(pid: int, session_path: Path, expected_start) -> bool:
    """True only if ``pid`` is alive AND still our node bridge for this session.

    A recycled PID (different kernel start time / different cmdline) is never
    treated as ours — see whatsapp/adapter.py for the full rationale.
    """
    from gateway.status import _pid_exists
    if not _pid_exists(pid):
        return False
    if expected_start is not None:
        from gateway.status import get_process_start_time
        return get_process_start_time(pid) == expected_start
    from gateway.status import _read_process_cmdline
    cmdline = _read_process_cmdline(pid)
    if not cmdline:
        return False
    return ("node" in cmdline) and (str(session_path) in cmdline)


def _kill_stale_bridge_by_pidfile(session_path: Path) -> None:
    """Kill a bridge process recorded in a PID file from a previous run.

    The recorded PID is re-validated against the live process
    (:func:`_bridge_pid_is_ours`) before any signal, so a recycled PID that
    now names an unrelated process is never killed.
    """
    pid_file = session_path / "bridge.pid"
    if not pid_file.exists():
        return
    pid = None
    recorded_start = None
    try:
        lines = pid_file.read_text(encoding="utf-8").split("\n")
        pid = int(lines[0].strip())
        if len(lines) > 1 and lines[1].strip():
            recorded_start = int(lines[1].strip())
    except (ValueError, OSError, TypeError, IndexError):
        try:
            pid_file.unlink()
        except OSError:
            pass
        return
    if _bridge_pid_is_ours(pid, session_path, recorded_start):
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("[zalo] Killed stale bridge PID %d from pidfile", pid)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    else:
        from gateway.status import _pid_exists
        if _pid_exists(pid):
            logger.warning(
                "[zalo] Not killing pidfile PID %d: it is no longer the "
                "bridge (recycled onto an unrelated process); skipping to avoid "
                "killing a stranger.", pid,
            )
    try:
        pid_file.unlink()
    except OSError:
        pass


def _write_bridge_pidfile(session_path: Path, pid: int) -> None:
    """Write the bridge PID (and its kernel start time) for later cleanup."""
    try:
        from gateway.status import get_process_start_time
        start = get_process_start_time(pid)
        text = str(pid) if start is None else "{}\n{}".format(pid, start)
        (session_path / "bridge.pid").write_text(text, encoding="utf-8")
    except OSError:
        pass


def _terminate_bridge_process(proc, *, force: bool = False) -> None:
    """Terminate the bridge process using process-tree semantics where possible."""
    if _IS_WINDOWS:
        cmd = ["taskkill", "/PID", str(proc.pid), "/T"]
        if force:
            cmd.append("/F")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True, encoding='utf-8', errors='replace',
                timeout=10,
            )
        except FileNotFoundError:
            if force:
                proc.kill()
            else:
                proc.terminate()
            return

        if result.returncode != 0:
            details = (result.stderr or result.stdout or "").strip()
            raise OSError(details or f"taskkill failed for PID {proc.pid}")
        return

    import psutil
    try:
        parent = psutil.Process(proc.pid)
        children = parent.children(recursive=True)
        if force:
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            parent.kill()
        else:
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            parent.terminate()
    except psutil.NoSuchProcess:
        return


import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
    cache_image_from_url,
)


def _file_content_hash(path: Path) -> str:
    """SHA-256 (first 16 hex chars) of ``path``'s contents, for the bridge
    staleness handshake — mirrors whatsapp/adapter.py's ``_file_content_hash``.
    """
    import hashlib
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def resolve_zalo_bridge_dir() -> Path:
    """Resolve the Zalo bridge directory, mirroring to HERMES_HOME if needed.

    Adapted from ``resolve_whatsapp_bridge_dir`` (gateway/platforms/whatsapp_common.py)
    for the sibling bridge under ``scripts/zalo-bridge/``. When the install
    tree is read-only (e.g. Docker /opt/hermes), mirrors the bridge source to
    a writable HERMES_HOME location so ``npm install`` works.
    """
    import shutil
    from hermes_constants import get_hermes_home

    install_bridge = Path(__file__).resolve().parents[3] / "scripts" / "zalo-bridge"
    hermes_home = get_hermes_home()
    hermes_home_bridge = hermes_home / "scripts" / "zalo-bridge"

    try:
        test_file = install_bridge / ".write_test"
        test_file.touch()
        test_file.unlink()
        install_writable = True
    except (OSError, PermissionError):
        install_writable = False

    if install_writable:
        return install_bridge

    if hermes_home_bridge.exists():
        return hermes_home_bridge

    try:
        hermes_home_bridge.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(install_bridge, hermes_home_bridge, dirs_exist_ok=False)
        return hermes_home_bridge
    except Exception:
        return install_bridge


def check_zalo_requirements() -> bool:
    """Check if Node.js (required by the Zalo bridge) is available."""
    _node = find_node_executable("node")
    if not _node:
        return False
    try:
        result = subprocess.run(
            [_node, "--version"],
            capture_output=True,
            text=True, encoding='utf-8', errors='replace',
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


class ZaloAdapter(BasePlatformAdapter):
    """
    Zalo adapter, backed by the ``scripts/zalo-bridge/`` Node.js process
    (Express server wrapping ``zca-js``).

    Chat IDs use the bridge's ``"u:<threadId>"`` / ``"g:<threadId>"``
    convention uniformly across ``MessageEvent.source.chat_id``, outbound
    send targets, and cron/send-message targets — there is no separate
    normalization step (unlike WhatsApp's JIDs).

    The bridge exposes no inbound-media, chat-info-lookup, message-edit, or
    read-receipt endpoints in v1 — this adapter does not assume any of those
    exist.
    """

    _DEFAULT_BRIDGE_DIR: Optional[Path] = None
    MAX_MESSAGE_LENGTH = 2000
    splits_long_messages = True  # send() chunks via truncate_message()

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform("zalo"))
        if ZaloAdapter._DEFAULT_BRIDGE_DIR is None:
            ZaloAdapter._DEFAULT_BRIDGE_DIR = resolve_zalo_bridge_dir()
        self._bridge_process: Optional[subprocess.Popen] = None
        self._bridge_port: int = int(
            config.extra.get("bridge_port") or _zenv("ZALO_BRIDGE_PORT", "3050") or 3050
        )
        self._bridge_script: str = config.extra.get(
            "bridge_script",
            str(self._DEFAULT_BRIDGE_DIR / "bridge.js"),
        )
        self._session_path: Path = Path(config.extra.get(
            "session_path",
            get_hermes_dir("platforms/zalo/session", "zalo/session"),
        ))
        # The bridge only ever reveals the bot's own Zalo uid transiently,
        # via a `PAIRED:<uid>` stdout line during `hermes zalo setup` (pair
        # mode) — it is never persisted by bridge.js itself, nor exposed via
        # any endpoint in resume mode. cli.py's setup flow captures that line
        # and persists it here so connect() can load it for mention gating.
        self._own_id_path: Path = self._session_path / "own_id.txt"
        self._own_uid: Optional[str] = None

        require_mention_raw = config.extra.get("require_mention")
        if require_mention_raw is None:
            require_mention_raw = _zenv("ZALO_REQUIRE_MENTION", "true")
        self._require_mention = str(require_mention_raw).strip().lower() in {"1", "true", "yes", "on"}
        self._mention_name = str(
            config.extra.get("mention_name") or _zenv("ZALO_MENTION_NAME", "")
        ).strip()
        self._free_response_chats = self._coerce_chat_set(
            config.extra.get("free_response_chats") or _zenv("ZALO_FREE_RESPONSE_CHATS")
        )

        # Best-effort chat display-name cache, populated from inbound events.
        # The bridge has no GET /chat/:id lookup in v1, so get_chat_info()
        # can only report what's already been observed.
        self._chat_names: Dict[str, str] = {}

        self._bridge_log_fh = None
        self._bridge_log: Optional[Path] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._http_session: Optional["aiohttp.ClientSession"] = None
        # Set True by disconnect() before SIGTERMing our child bridge so
        # _check_managed_bridge_exit() can distinguish an intentional
        # shutdown-time exit from a real crash (mirrors WhatsApp).
        self._shutting_down: bool = False

    @staticmethod
    def _coerce_chat_set(raw) -> set:
        if not raw:
            return set()
        if isinstance(raw, (list, tuple, set)):
            return {str(v).strip() for v in raw if str(v).strip()}
        return {v.strip() for v in str(raw).split(",") if v.strip()}

    def _load_own_uid(self) -> Optional[str]:
        try:
            text = self._own_id_path.read_text(encoding="utf-8").strip()
            return text or None
        except OSError:
            return None

    def _adopt_own_uid_from_health(self, data: Dict[str, Any]) -> None:
        """Fall back to a connected bridge's ``/health.ownId`` when
        ``own_id.txt`` is missing (e.g. lost after pairing) so @mention
        gating can recover without a full re-pair. Best-effort: persists the
        recovered uid back to disk for the next connect()."""
        if self._own_uid:
            return
        own_id = data.get("ownId")
        if not own_id:
            return
        self._own_uid = str(own_id)
        logger.info("[%s] Recovered own uid from bridge /health (own_id.txt was missing)", self.name)
        try:
            self._own_id_path.write_text(self._own_uid, encoding="utf-8")
        except OSError:
            pass

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        """Start the Zalo bridge (resume mode) and begin polling for messages."""
        if not check_zalo_requirements():
            logger.warning("[%s] Node.js not found. Zalo requires Node.js.", self.name)
            self._set_fatal_error(
                "zalo_node_missing",
                "Node.js is not installed — install Node.js and re-run `hermes gateway`.",
                retryable=False,
            )
            return False

        bridge_path = Path(self._bridge_script)
        if not bridge_path.exists():
            logger.warning("[%s] Bridge script not found: %s", self.name, bridge_path)
            self._set_fatal_error(
                "zalo_bridge_missing",
                f"Zalo bridge script missing at {bridge_path}.",
                retryable=False,
            )
            return False

        # Pre-flight: skip the bridge bootstrap entirely if the user never
        # finished pairing. Resume mode hard-fails (no QR fallback, by
        # design) without zalo_creds.json, so there is nothing to gain from
        # spawning node here — and Zalo allows only one web-listener session
        # per account, so a doomed spawn could fight a legitimately-paired
        # session for that slot.
        creds_path = self._session_path / "zalo_creds.json"
        if not creds_path.exists():
            logger.warning(
                "[%s] Zalo is enabled but not paired (no zalo_creds.json at %s). "
                "Pair by running `hermes zalo setup`; remove ZALO_ENABLED from "
                "your .env to disable.",
                self.name, creds_path,
            )
            self._set_fatal_error(
                "zalo_not_paired",
                "Zalo enabled but not paired — run `hermes zalo setup`.",
                retryable=False,
            )
            return False

        self._own_uid = self._load_own_uid()
        if not self._own_uid:
            logger.warning(
                "[%s] No own_id.txt in session dir — group @mention gating will "
                "fall back to ZALO_MENTION_NAME text matching only.", self.name,
            )

        logger.info("[%s] Bridge found at %s", self.name, bridge_path)

        lock_acquired = False
        try:
            if not self._acquire_platform_lock('zalo-session', str(self._session_path), 'Zalo session'):
                return False
            lock_acquired = True
        except Exception as e:
            logger.warning("[%s] Could not acquire session lock (non-fatal): %s", self.name, e)

        try:
            # Auto-install npm dependencies when node_modules is missing OR
            # package.json changed since the last install (mirrors WhatsApp's
            # stamp-file approach).
            bridge_dir = bridge_path.parent
            _pkg_json = bridge_dir / "package.json"
            _dep_stamp = bridge_dir / "node_modules" / ".hermes-pkg-hash"
            _pkg_hash = _file_content_hash(_pkg_json)
            _deps_fresh = False
            if (bridge_dir / "node_modules").exists():
                try:
                    _deps_fresh = (
                        _dep_stamp.read_text(encoding="utf-8").strip() == _pkg_hash
                    ) and bool(_pkg_hash)
                except OSError:
                    _deps_fresh = False
            if not _deps_fresh:
                print(f"[{self.name}] Installing Zalo bridge dependencies...")
                _npm_bin = find_node_executable("npm") or "npm"
                try:
                    from utils import env_int
                    npm_install_timeout = env_int("ZALO_NPM_INSTALL_TIMEOUT", 300)
                    install_result = subprocess.run(
                        [_npm_bin, "install", "--silent"],
                        cwd=str(bridge_dir),
                        capture_output=True,
                        text=True, encoding='utf-8', errors='replace',
                        timeout=npm_install_timeout,
                        env=with_hermes_node_path(),
                    )
                    if install_result.returncode != 0:
                        print(f"[{self.name}] npm install failed: {install_result.stderr}")
                        self._set_fatal_error(
                            "zalo_npm_install_failed",
                            f"Zalo bridge npm install failed. Run `cd {bridge_dir} && {_npm_bin} install` manually, then restart `hermes gateway`.",
                            retryable=False,
                        )
                        return False
                    print(f"[{self.name}] Dependencies installed")
                    if _pkg_hash:
                        try:
                            _dep_stamp.write_text(_pkg_hash, encoding="utf-8")
                        except OSError:
                            pass
                except Exception as e:
                    print(f"[{self.name}] Failed to install dependencies: {e}")
                    self._set_fatal_error(
                        "zalo_npm_install_failed",
                        f"Zalo bridge npm install failed ({e}). Run `cd {bridge_dir} && {_npm_bin} install` manually, then restart `hermes gateway`.",
                        retryable=False,
                    )
                    return False

            self._session_path.mkdir(parents=True, exist_ok=True)

            # Check if a bridge is already running and connected. Reuse it
            # only when serving the same bridge.js currently on disk — a
            # long-lived bridge surviving `hermes update` would otherwise
            # keep serving pre-update code forever.
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://127.0.0.1:{self._bridge_port}/health",
                        timeout=aiohttp.ClientTimeout(total=2)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            bridge_status = data.get("status", "unknown")
                            if bridge_status == "connected":
                                running_hash = data.get("scriptHash", "")
                                disk_hash = _file_content_hash(bridge_path)
                                if running_hash and disk_hash and running_hash == disk_hash:
                                    print(f"[{self.name}] Using existing bridge (status: {bridge_status})")
                                    self._adopt_own_uid_from_health(data)
                                    self._mark_connected()
                                    self._bridge_process = None  # not managed by us
                                    self._http_session = aiohttp.ClientSession()
                                    self._poll_task = asyncio.create_task(self._poll_messages())
                                    return True
                                print(
                                    f"[{self.name}] Running bridge is stale "
                                    f"(running={running_hash or 'unversioned'}, disk={disk_hash}), restarting"
                                )
                            else:
                                print(f"[{self.name}] Bridge found but not connected (status: {bridge_status}), restarting")
            except Exception:
                pass  # Bridge not running, start a new one

            # Kill any orphaned bridge from a previous gateway run. This is
            # more than tidiness here: Zalo allows only one web-listener
            # session per account, so a stray zombie bridge would fight the
            # new one for that single slot.
            _kill_stale_bridge_by_pidfile(self._session_path)
            _kill_port_process(self._bridge_port)
            await asyncio.sleep(1)

            self._bridge_log = self._session_path.parent / "bridge.log"
            bridge_log_fh = open(self._bridge_log, "a", encoding="utf-8")
            self._bridge_log_fh = bridge_log_fh

            bridge_env = with_hermes_node_path()

            self._bridge_process = subprocess.Popen(
                [
                    find_node_executable("node") or "node",
                    str(bridge_path),
                    "--port", str(self._bridge_port),
                    "--session", str(self._session_path),
                    "--mode", "resume",
                ],
                stdout=bridge_log_fh,
                stderr=bridge_log_fh,
                env=bridge_env,
                **windows_detach_popen_kwargs(),
            )
            _write_bridge_pidfile(self._session_path, self._bridge_process.pid)

            # Phase 1: wait for the HTTP server to come up (up to 15s).
            # Phase 2: wait for status: connected (up to 15s more).
            http_ready = False
            data = {}
            for _attempt in range(15):
                await asyncio.sleep(1)
                if self._bridge_process.poll() is not None:
                    print(f"[{self.name}] Bridge process died (exit code {self._bridge_process.returncode})")
                    print(f"[{self.name}] Check log: {self._bridge_log}")
                    self._close_bridge_log()
                    return False
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"http://127.0.0.1:{self._bridge_port}/health",
                            timeout=aiohttp.ClientTimeout(total=2)
                        ) as resp:
                            if resp.status == 200:
                                http_ready = True
                                data = await resp.json()
                                if data.get("status") == "connected":
                                    print(f"[{self.name}] Bridge ready (status: connected)")
                                    break
                except Exception:
                    continue

            if not http_ready:
                print(f"[{self.name}] Bridge HTTP server did not start in 15s")
                print(f"[{self.name}] Check log: {self._bridge_log}")
                self._close_bridge_log()
                return False

            if data.get("status") != "connected":
                print(f"[{self.name}] Bridge HTTP ready, waiting for Zalo connection...")
                for _attempt in range(15):
                    await asyncio.sleep(1)
                    if self._bridge_process.poll() is not None:
                        print(f"[{self.name}] Bridge process died during connection")
                        print(f"[{self.name}] Check log: {self._bridge_log}")
                        self._close_bridge_log()
                        return False
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                f"http://127.0.0.1:{self._bridge_port}/health",
                                timeout=aiohttp.ClientTimeout(total=2)
                            ) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    if data.get("status") == "connected":
                                        print(f"[{self.name}] Bridge ready (status: connected)")
                                        break
                    except Exception:
                        continue
                else:
                    print(f"[{self.name}] ⚠ Zalo not connected after 30s")
                    print(f"[{self.name}]   Bridge log: {self._bridge_log}")
                    print(f"[{self.name}]   If the session expired, re-pair: hermes zalo setup")

            self._adopt_own_uid_from_health(data)
            self._http_session = aiohttp.ClientSession()
            self._poll_task = asyncio.create_task(self._poll_messages())

            self._mark_connected()
            print(f"[{self.name}] Bridge started on port {self._bridge_port}")
            return True

        except Exception as e:
            logger.error("[%s] Failed to start bridge: %s", self.name, e, exc_info=True)
            return False
        finally:
            if not self._running:
                if lock_acquired:
                    self._release_platform_lock()
                self._close_bridge_log()

    def _close_bridge_log(self) -> None:
        if self._bridge_log_fh:
            try:
                self._bridge_log_fh.close()
            except Exception:
                pass
            self._bridge_log_fh = None

    async def _check_managed_bridge_exit(self) -> Optional[str]:
        """Return a fatal error message if the managed bridge child exited."""
        if self._bridge_process is None:
            return None

        returncode = self._bridge_process.poll()
        if returncode is None:
            return None

        if getattr(self, "_shutting_down", False) and returncode in {0, -2, -15}:
            logger.info("[%s] Bridge exited during shutdown (code %d).", self.name, returncode)
            return None

        message = f"Zalo bridge process exited unexpectedly (code {returncode})."
        if not self.has_fatal_error:
            logger.error("[%s] %s", self.name, message)
            self._set_fatal_error("zalo_bridge_exited", message, retryable=True)
            self._close_bridge_log()
            await self._notify_fatal_error()
        return self.fatal_error_message or message

    async def disconnect(self) -> None:
        """Stop the Zalo bridge and clean up any orphaned processes."""
        self._shutting_down = True
        if self._bridge_process:
            try:
                try:
                    _terminate_bridge_process(self._bridge_process, force=False)
                except (ProcessLookupError, PermissionError):
                    self._bridge_process.terminate()
                await asyncio.sleep(1)
                if self._bridge_process.poll() is None:
                    try:
                        _terminate_bridge_process(self._bridge_process, force=True)
                    except (ProcessLookupError, PermissionError):
                        self._bridge_process.kill()
            except Exception as e:
                print(f"[{self.name}] Error stopping bridge: {e}")
        else:
            print(f"[{self.name}] Disconnecting (external bridge left running)")

        try:
            (self._session_path / "bridge.pid").unlink(missing_ok=True)
        except OSError:
            pass

        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except (asyncio.CancelledError, Exception):
                pass
        self._poll_task = None

        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        self._http_session = None

        self._release_platform_lock()

        self._mark_disconnected()
        self._bridge_process = None
        self._close_bridge_log()
        print(f"[{self.name}] Disconnected")

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Send a message via the Zalo bridge.

        The bridge's ``POST /send`` only accepts ``{chat_id, text}`` — there
        is no reply-to / quote support in v1, so ``reply_to`` is accepted for
        contract compatibility but not forwarded.
        """
        if not self._running or not self._http_session:
            return SendResult(success=False, error="Not connected")
        bridge_exit = await self._check_managed_bridge_exit()
        if bridge_exit:
            return SendResult(success=False, error=bridge_exit)

        if not content or not content.strip():
            return SendResult(success=True, message_id=None)

        try:
            import aiohttp

            formatted = self.format_message(content)
            chunks = self.truncate_message(formatted, self.max_message_length_for_chat(chat_id))

            sent_message_ids: list[str] = []
            last_message_id = None
            for chunk in chunks:
                async with self._http_session.post(
                    f"http://127.0.0.1:{self._bridge_port}/send",
                    json={"chat_id": chat_id, "text": chunk},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        last_message_id = data.get("message_id")
                        if last_message_id:
                            sent_message_ids.append(str(last_message_id))
                    else:
                        error = await resp.text()
                        return SendResult(success=False, error=error)

                if len(chunks) > 1:
                    await asyncio.sleep(0.3)

            return SendResult(
                success=True,
                message_id=last_message_id,
                continuation_message_ids=tuple(sent_message_ids[:-1]),
                raw_response={"message_ids": sent_message_ids},
            )
        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def _send_media_to_bridge(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str] = None,
    ) -> SendResult:
        """Send any media file via the bridge's single generic ``/send-media``
        endpoint (zca-js auto-detects the attachment type — no per-type field)."""
        if not self._running or not self._http_session:
            return SendResult(success=False, error="Not connected")
        bridge_exit = await self._check_managed_bridge_exit()
        if bridge_exit:
            return SendResult(success=False, error=bridge_exit)
        try:
            import aiohttp

            if not os.path.exists(file_path):
                return SendResult(success=False, error=f"File not found: {file_path}")

            payload: Dict[str, Any] = {"chat_id": chat_id, "file_path": file_path}
            if caption:
                payload["caption"] = caption

            async with self._http_session.post(
                f"http://127.0.0.1:{self._bridge_port}/send-media",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return SendResult(
                        success=True,
                        message_id=data.get("message_id"),
                        raw_response=data,
                    )
                error = await resp.text()
                return SendResult(success=False, error=error)
        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Download image URL to cache, send natively via bridge."""
        try:
            local_path = await cache_image_from_url(image_url)
            return await self._send_media_to_bridge(chat_id, local_path, caption)
        except Exception:
            return await super().send_image(chat_id, image_url, caption, reply_to, metadata)

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        return await self._send_media_to_bridge(chat_id, image_path, caption)

    async def send_video(
        self,
        chat_id: str,
        video_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        return await self._send_media_to_bridge(chat_id, video_path, caption)

    async def send_voice(
        self,
        chat_id: str,
        audio_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        return await self._send_media_to_bridge(chat_id, audio_path, caption)

    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        # The bridge has no file-rename field — zca-js sends the file as-is.
        return await self._send_media_to_bridge(chat_id, file_path, caption)

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        if not self._running or not self._http_session:
            return
        if await self._check_managed_bridge_exit():
            return
        try:
            import aiohttp

            async with self._http_session.post(
                f"http://127.0.0.1:{self._bridge_port}/typing",
                json={"chat_id": chat_id},
                timeout=aiohttp.ClientTimeout(total=5),
            ):
                pass
        except Exception:
            pass  # Ignore typing indicator failures

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """Derive chat info purely from the ``"g:"``/``"u:"`` chat_id prefix.

        The bridge has no ``GET /chat/:id`` lookup in v1; the name (if any)
        comes from whatever this adapter has already observed via inbound
        events.
        """
        chat_type = "group" if chat_id.startswith("g:") else "dm"
        return {"name": self._chat_names.get(chat_id, chat_id), "type": chat_type}

    async def _poll_messages(self) -> None:
        """Poll the bridge for incoming messages."""
        import aiohttp

        while self._running:
            if not self._http_session:
                break
            bridge_exit = await self._check_managed_bridge_exit()
            if bridge_exit:
                print(f"[{self.name}] {bridge_exit}")
                break
            try:
                async with self._http_session.get(
                    f"http://127.0.0.1:{self._bridge_port}/messages",
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        messages = await resp.json()
                        for msg_data in messages:
                            event = await self._build_message_event(msg_data)
                            if event:
                                await self.handle_message(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                bridge_exit = await self._check_managed_bridge_exit()
                if bridge_exit:
                    print(f"[{self.name}] {bridge_exit}")
                    break
                print(f"[{self.name}] Poll error: {e}")
                await asyncio.sleep(5)

            await asyncio.sleep(1)  # Poll interval

    def _should_respond(self, data: Dict[str, Any]) -> bool:
        """DMs always respond. Groups respond when mention-gating is off,
        the chat is in the free-response allowlist, or the bot was
        @-mentioned (structured ``mentions[].uid`` match against the
        persisted own uid, with a text-substring fallback for when that
        uid isn't available)."""
        if not data.get("is_group"):
            return True
        if not self._require_mention:
            return True
        if data.get("chat_id", "") in self._free_response_chats:
            return True
        if self._own_uid:
            for m in (data.get("mentions") or []):
                if str(m.get("uid")) == self._own_uid:
                    return True
        if self._mention_name:
            if self._mention_name.lower() in str(data.get("text") or "").lower():
                return True
        return False

    async def _build_message_event(self, data: Dict[str, Any]) -> Optional[MessageEvent]:
        """Build a MessageEvent from a bridge message event.

        The bridge has no inbound-media forwarding in v1 (``messageToEvent``
        only surfaces plain-string text plus a ``content_type`` label for
        media messages) — a media message becomes a short descriptive
        placeholder rather than a downloadable attachment.
        """
        try:
            # Defense in depth: the bridge already suppresses its own
            # outbound-message echo (`if (message.isSelf) return;`).
            if data.get("is_self"):
                return None
            if not self._should_respond(data):
                return None

            chat_id = str(data.get("chat_id") or "")
            is_group = bool(data.get("is_group"))
            chat_type = "group" if is_group else "dm"
            sender_name = data.get("sender_name")
            if not is_group and sender_name:
                self._chat_names[chat_id] = sender_name

            text = str(data.get("text") or "")
            content_type = str(data.get("content_type") or "").strip()
            if not text and content_type:
                text = f"[Received a {content_type} message — media forwarding is not supported yet]"

            source = self.build_source(
                chat_id=chat_id,
                chat_name=self._chat_names.get(chat_id),
                chat_type=chat_type,
                user_id=data.get("sender_id"),
                user_name=sender_name,
            )

            return MessageEvent(
                text=text,
                message_type=MessageType.TEXT,
                source=source,
                raw_message=data,
                message_id=data.get("message_id"),
            )
        except Exception as e:
            print(f"[{self.name}] Error building event: {e}")
            return None


# ──────────────────────────────────────────────────────────────────────────
# Plugin registration glue
# ──────────────────────────────────────────────────────────────────────────


async def _standalone_send(
    pconfig,
    chat_id,
    message,
    *,
    thread_id=None,
    media_files=None,
    force_document=False,
    caption=None,
):
    """Out-of-process Zalo delivery via the local bridge HTTP API.

    Implements the standalone_sender_fn contract so ``deliver=zalo`` cron
    jobs succeed when cron runs separately from the gateway.
    """
    extra = getattr(pconfig, "extra", {}) or {}
    try:
        import aiohttp
    except ImportError:
        return {"error": "aiohttp not installed. Run: pip install aiohttp"}
    try:
        bridge_port = extra.get("bridge_port", 3050)
        media = media_files or []
        text = message or ""
        media_caption = caption if (caption and len(media) == 1) else None
        last_message_id = None
        async with aiohttp.ClientSession() as session:
            if text.strip() and not media_caption:
                async with session.post(
                    f"http://localhost:{bridge_port}/send",
                    json={"chat_id": chat_id, "text": text},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        return {"error": f"Zalo bridge error ({resp.status}): {body}"}
                    data = await resp.json()
                    last_message_id = data.get("message_id")

            for media_path, _is_voice in media:
                if not os.path.exists(media_path):
                    if media_caption:
                        try:
                            async with session.post(
                                f"http://localhost:{bridge_port}/send",
                                json={"chat_id": chat_id, "text": media_caption},
                                timeout=aiohttp.ClientTimeout(total=30),
                            ) as resp:
                                if resp.status == 200:
                                    last_message_id = (await resp.json()).get("message_id")
                        except Exception:
                            logger.warning("Zalo caption-fallback send failed for missing media")
                    return {"error": f"Zalo media file not found: {media_path}"}
                payload: Dict[str, Any] = {"chat_id": chat_id, "file_path": media_path}
                if media_caption:
                    payload["caption"] = media_caption
                async with session.post(
                    f"http://localhost:{bridge_port}/send-media",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        return {"error": f"Zalo media error ({resp.status}): {body}"}
                    data = await resp.json()
                    last_message_id = data.get("message_id") or last_message_id

        return {
            "success": True,
            "platform": "zalo",
            "chat_id": chat_id,
            "message_id": last_message_id,
        }
    except Exception as e:
        return {"error": f"Zalo send failed: {e}"}


def _apply_yaml_config(yaml_cfg: dict, zalo_cfg: dict) -> dict | None:
    """Translate config.yaml ``zalo:`` keys into ZALO_* env vars.

    Implements the apply_yaml_config_fn contract (#24849). Env vars take
    precedence over YAML. Returns None — everything flows through env.
    """
    if "require_mention" in zalo_cfg and not os.getenv("ZALO_REQUIRE_MENTION"):
        os.environ["ZALO_REQUIRE_MENTION"] = str(zalo_cfg["require_mention"]).lower()
    if "mention_name" in zalo_cfg and not os.getenv("ZALO_MENTION_NAME"):
        os.environ["ZALO_MENTION_NAME"] = str(zalo_cfg["mention_name"])
    frc = zalo_cfg.get("free_response_chats")
    if frc is not None and not os.getenv("ZALO_FREE_RESPONSE_CHATS"):
        if isinstance(frc, list):
            frc = ",".join(str(v) for v in frc)
        os.environ["ZALO_FREE_RESPONSE_CHATS"] = str(frc)
    if "bridge_port" in zalo_cfg and not os.getenv("ZALO_BRIDGE_PORT"):
        os.environ["ZALO_BRIDGE_PORT"] = str(zalo_cfg["bridge_port"])
    return None


def _is_connected(config) -> bool:
    """Zalo is considered connected when the user has explicitly enabled it
    via ``ZALO_ENABLED`` (mirrors WhatsApp's ``_is_connected``, #41112).

    Auth itself is handled by the external Node.js bridge — the opt-in flag
    is the connection signal shown by ``hermes setup`` / ``hermes gateway status``.
    """
    extra = getattr(config, "extra", {}) or {}
    if config is not None and getattr(config, "enabled", False) and extra:
        return True
    import hermes_cli.gateway as gateway_mod
    val = (gateway_mod.get_env_value("ZALO_ENABLED") or "").strip().lower()
    return val in {"true", "1", "yes"}


def _build_adapter(config):
    """Factory wrapper that constructs ZaloAdapter from a PlatformConfig."""
    return ZaloAdapter(config)


def register(ctx) -> None:
    """Plugin entry point — called by the Hermes plugin system."""
    from . import cli as _cli

    ctx.register_platform(
        name="zalo",
        label="Zalo",
        adapter_factory=_build_adapter,
        check_fn=check_zalo_requirements,
        is_connected=_is_connected,
        required_env=["ZALO_ENABLED"],
        install_hint=(
            "Zalo requires a Node.js bridge — run `hermes zalo setup` to pair "
            "(QR login) and install it."
        ),
        setup_fn=_cli.gateway_setup,
        apply_yaml_config_fn=_apply_yaml_config,
        allowed_users_env="ZALO_ALLOWED_USERS",
        allow_all_env="ZALO_ALLOW_ALL_USERS",
        cron_deliver_env_var="ZALO_HOME_CHANNEL",
        standalone_sender_fn=_standalone_send,
        max_message_length=2000,
        emoji="💬",
        allow_update_command=True,
        platform_hint=(
            "You are communicating via Zalo, a Vietnamese chat app. Rendering "
            "support is unverified, so use plain text only — no markdown (no "
            "bold, headers, or tables); for lists, use line breaks and '-' "
            "bullets. Default to Vietnamese when the user writes in Vietnamese. "
            "In group chats you only see messages that @mention you, or that "
            "come from a chat explicitly configured to always respond — direct "
            "messages always reach you, and you don't need a mention there. "
            "You can send media files natively: include "
            "MEDIA:/absolute/path/to/file in your response; images and other "
            "files are delivered as native Zalo attachments. Inbound media from "
            "the user arrives only as a description, not a file — you cannot "
            "read or view attachments the user sends."
        ),
    )

    ctx.register_cli_command(
        name="zalo",
        help="Set up and manage the Zalo integration (QR pairing via a Node.js bridge)",
        setup_fn=_cli.register_cli,
        handler_fn=_cli.dispatch,
    )
