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
behavior mixin here. Like WeCom/Weixin/Yuanbao/QQBot/WhatsApp, this adapter
owns its access policy directly (``enforces_own_access_policy`` returns
True) instead of delegating identity to the gateway's generic
``ZALO_ALLOWED_USERS``/``ZALO_ALLOW_ALL_USERS`` check: an owner-only DM
baseline plus per-group chats members can be opened into on demand via
in-chat ``!moquyenchat``/``!dongquyenchat`` needs live, per-sender,
per-group, additive semantics a flat platform-wide allowlist can't express.
See ``_is_dm_allowed``, ``_is_group_allowed``, ``_handle_chat_permission_
command``. ``ZALO_ALLOWED_USERS``/``ZALO_ALLOW_ALL_USERS`` remain
registered (see ``register()``) purely as a legacy escape hatch — setting
either forces the gateway back to the flat platform-wide check for every
Zalo chat (gateway/authz_mixin.py:610-618 requires both empty for the
adapter-owned branch below to engage), bypassing everything in this file.
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


def _save_hermes_config_value(key_path: str, value: Any) -> bool:
    """Persist one dotted config.yaml key, preserving comments/ordering/
    quotes (ruamel round-trip). Calls ``utils.atomic_roundtrip_yaml_update``
    directly rather than importing the ~11k-line top-level ``cli.py`` (whose
    ``save_config_value`` wraps the same call) from a platform plugin.

    Single-writer assumption: correct for the live Zalo adapter process
    mutating its own config, and for `hermes zalo` CLI commands run while
    the gateway is stopped. Not safe against a second concurrent writer.
    """
    try:
        from hermes_constants import get_hermes_home
        from utils import atomic_roundtrip_yaml_update

        atomic_roundtrip_yaml_update(get_hermes_home() / "config.yaml", key_path, value)
        return True
    except Exception as e:
        logger.warning("Failed to persist config key %s: %s", key_path, e)
        return False


def save_zalo_extra_value(key: str, value: Any) -> bool:
    return _save_hermes_config_value(f"platforms.zalo.extra.{key}", value)


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
from gateway.platforms.helpers import strip_markdown


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


_ALL_MENTION_RE = re.compile(r"@all\b", re.IGNORECASE)
_CHAT_PERMISSION_COMMAND_RE = re.compile(r"(?:^|\s)!(moquyenchat|dongquyenchat)\b", re.IGNORECASE)
# Bare "!new" shortcut for allowlisted senders (ZALO_NEW_COMMAND_USERS). Exists
# because MessageEvent.is_command() only recognizes a literal leading "/", but
# Zalo mentions are rendered as literal display-name text prepended to the
# message ("@Bth /new"), which never satisfies that check — "/new" typed after
# the mention is silently treated as normal chat instead of the real command.
_NEW_SESSION_COMMAND_RE = re.compile(r"(?:^|\s)!new\b", re.IGNORECASE)

# !promptcapnhat [noi dung] — owner-only durable instruction update. Bang-
# prefixed for the same reason as the two commands above: a group @mention
# is rendered as literal display-name text prepended to the message, which
# breaks MessageEvent.is_command()'s leading-"/" check for a real slash
# command. DOTALL since the update text may be multi-line.
_PROMPT_UPDATE_COMMAND_RE = re.compile(
    r"(?:^|\s)!promptcapnhat\b[ \t]*(.*)", re.IGNORECASE | re.DOTALL
)


def _utf16_len(s: str) -> int:
    """UTF-16 code-unit length of ``s`` — zca-js mention pos/len are JS
    string offsets, which count UTF-16 units, not Python codepoints."""
    return len(s.encode("utf-16-le")) // 2


def _find_all_mention(text: str) -> Optional[Dict[str, Any]]:
    """Detect a literal ``@all`` the agent wrote and build the zca-js
    mention entry that tags everyone in the group (uid "-1" is zca-js's
    sentinel for @all — see scripts/zalo-bridge/node_modules/zca-js/dist/
    apis/sendMessage.js). Only the first occurrence is tagged; harmless
    no-op in DMs since the bridge only honors mentions for group threads.
    """
    match = _ALL_MENTION_RE.search(text)
    if not match:
        return None
    pos = _utf16_len(text[: match.start()])
    length = _utf16_len(match.group(0))
    return {"pos": pos, "uid": "-1", "len": length}


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
        self._owner_id: str = str(config.extra.get("owner_id") or "").strip()
        self._group_allow_from: set = self._coerce_chat_set(config.extra.get("group_allow_from"))
        groups_raw = config.extra.get("groups")
        self._groups: dict = dict(groups_raw) if isinstance(groups_raw, dict) else {}
        # Fixed, non-configurable — Zalo intentionally exposes no
        # open/disabled/pairing dial like WeCom's; the owner-only-DM +
        # additive-per-group-opt-in contract above is the whole policy.
        self._dm_policy = "allowlist"
        self._group_policy = "allowlist"

        disable_dms_raw = config.extra.get("disable_dms")
        if disable_dms_raw is None:
            disable_dms_raw = _zenv("ZALO_DISABLE_DMS", "false")
        self._disable_dms = str(disable_dms_raw).strip().lower() in {"1", "true", "yes", "on"}
        self._warn_if_legacy_access_env_set()

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

    def format_message(self, content: str) -> str:
        """Strip markdown — Zalo renders it as literal characters (no bold/
        headers/tables support), confirmed by observing raw ``**text**``
        asterisks on-device despite the model being instructed not to use
        markdown. Code-level stripping is the reliable guard since prompt
        instructions alone aren't consistently followed by every model."""
        return strip_markdown(content)

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
                payload: Dict[str, Any] = {"chat_id": chat_id, "text": chunk}
                all_mention = _find_all_mention(chunk)
                if all_mention:
                    payload["mentions"] = [all_mention]
                async with self._http_session.post(
                    f"http://127.0.0.1:{self._bridge_port}/send",
                    json=payload,
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

    def _warn_if_legacy_access_env_set(self) -> None:
        """``ZALO_ALLOWED_USERS``/``ZALO_ALLOW_ALL_USERS`` silently disable
        the owner/group policy below at the gateway layer (see module
        docstring). Most operators who still have either set inherited it
        from before this adapter owned its own access policy."""
        stale = [n for n in ("ZALO_ALLOWED_USERS", "ZALO_ALLOW_ALL_USERS") if _zenv(n, "").strip()]
        if stale:
            msg = (
                f"[{self.name}] {', '.join(stale)} is set — this DISABLES the "
                "owner-only DM / per-group !moquyenchat policy for ALL Zalo "
                f"chats. Clear {'/'.join(stale)} in .env and restart to use it."
            )
            logger.warning(msg)
            print(msg)

    @property
    def enforces_own_access_policy(self) -> bool:
        """Zalo gates DM/group access at intake itself — see
        _is_dm_allowed/_is_group_allowed, enforced in _build_message_event
        before any MessageEvent is constructed."""
        return True

    def _sender_is_owner(self, sender_id: str) -> bool:
        sender_id = str(sender_id or "").strip()
        return bool(sender_id) and bool(self._owner_id) and sender_id == self._owner_id

    def _is_dm_allowed(self, sender_id: str) -> bool:
        """Standing baseline: only the configured owner may ever DM the
        bot. Fails closed when no owner is configured (fresh install)."""
        if self._disable_dms:
            return False
        return self._sender_is_owner(sender_id)

    def _resolve_group_cfg(self, chat_id: str) -> Dict[str, Any]:
        """Exact match, then case-insensitive. Deliberately NO '*' wildcard
        group-key fallback (unlike WeCom's equivalent) — an unconfigured
        group must never inherit another entry's permissiveness; only a
        chat_id explicitly opened via !moquyenchat is ever 'open'."""
        cfg = self._groups.get(chat_id)
        if isinstance(cfg, dict):
            return cfg
        lowered = chat_id.lower()
        for key, value in self._groups.items():
            if isinstance(key, str) and key.lower() == lowered and isinstance(value, dict):
                return value
        return {}

    def _is_group_opened(self, chat_id: str) -> bool:
        allow_from = self._resolve_group_cfg(chat_id).get("allow_from")
        if isinstance(allow_from, str):
            return allow_from.strip() == "*"
        if isinstance(allow_from, (list, tuple, set)):
            return "*" in {str(v).strip() for v in allow_from}
        return False

    def _is_group_allowed(self, chat_id: str, sender_id: str) -> bool:
        """Owner is always allowed; else additive per-group opt-in
        (!moquyenchat) or the flat regular allowlist. Never defaults to
        open for a chat_id that was never explicitly opened."""
        sender_id = str(sender_id or "").strip()
        if self._sender_is_owner(sender_id):
            return True
        if self._is_group_opened(chat_id):
            return True
        return bool(sender_id) and ("*" in self._group_allow_from or sender_id in self._group_allow_from)

    def _is_message_access_allowed(self, data: Dict[str, Any]) -> bool:
        """Real identity gate — must run before a MessageEvent is built."""
        sender_id = str(data.get("sender_id") or "").strip()
        if not sender_id:
            return False
        if data.get("is_group"):
            return self._is_group_allowed(str(data.get("chat_id") or ""), sender_id)
        return self._is_dm_allowed(sender_id)

    def _should_respond(self, data: Dict[str, Any]) -> bool:
        """Mention-gating for GROUP chats only — access control is decided
        separately by ``_is_message_access_allowed()``. DMs always proceed
        once access-allowed (no mention needed)."""
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

    def _sender_can_manage_chat_permissions(self, data: Dict[str, Any]) -> bool:
        """Only the configured owner may open/close group chat permissions.
        Deliberately does NOT consult ZALO_ALLOW_ALL_USERS/ZALO_ALLOWED_USERS
        — that was a self-widening privilege-escalation bug (once
        !moquyenchat ran once, ALLOW_ALL_USERS became true, which this same
        check then treated as authorization to run it again for anyone)."""
        return self._sender_is_owner(str(data.get("sender_id") or ""))

    async def _handle_chat_permission_command(self, data: Dict[str, Any]) -> bool:
        text = str(data.get("text") or "").strip()
        match = _CHAT_PERMISSION_COMMAND_RE.search(text)
        if not match:
            return False

        chat_id = str(data.get("chat_id") or "").strip()
        if not data.get("is_group") or not chat_id.startswith("g:"):
            if chat_id:
                await self.send(chat_id, "Lenh nay chi dung trong group Zalo.")
            return True

        if not self._sender_can_manage_chat_permissions(data):
            await self.send(chat_id, "Ban chua co quyen mo/dong quyen chat bot.")
            return True

        command = match.group(1).lower()
        if command == "moquyenchat":
            ok = self._open_group(chat_id)
            msg = "Da mo quyen: moi nguoi trong group nay co the goi bot."
        else:
            ok = self._close_group(chat_id)
            msg = "Da dong quyen chat group nay. Cac group khac da mo van khong doi."
        if not ok:
            msg += " (Canh bao: khong luu duoc vao config.yaml — se mat sau khi restart.)"
        await self.send(chat_id, msg)
        return True

    def _open_group(self, chat_id: str) -> bool:
        """Additive: adds chat_id, never touches any other group's entry."""
        groups = dict(self._groups)
        groups[chat_id] = {"allow_from": ["*"]}
        self._groups = groups
        return save_zalo_extra_value("groups", groups)

    def _close_group(self, chat_id: str) -> bool:
        """Removes only chat_id; every other opened group is untouched."""
        groups = dict(self._groups)
        lowered = chat_id.lower()
        for key in [k for k in groups if isinstance(k, str) and k.lower() == lowered]:
            groups.pop(key, None)
        self._groups = groups
        return save_zalo_extra_value("groups", groups)

    async def _handle_prompt_update_command(self, data: Dict[str, Any]) -> bool:
        """Owner-only ``!promptcapnhat [noi dung]`` — durably appends to
        ``agent.system_prompt`` (config.yaml), or with no text, echoes the
        current value back. Requires a gateway restart to take effect,
        since ``agent.system_prompt`` is frozen at GatewayRunner startup."""
        text = str(data.get("text") or "")
        match = _PROMPT_UPDATE_COMMAND_RE.search(text)
        if not match:
            return False

        chat_id = str(data.get("chat_id") or "").strip()
        if not chat_id:
            return True

        if not self._sender_is_owner(str(data.get("sender_id") or "")):
            await self.send(chat_id, "Ban khong co quyen dung lenh nay.")
            return True

        from hermes_cli.config import load_config

        current_prompt = str((load_config().get("agent") or {}).get("system_prompt") or "").strip()
        new_text = match.group(1).strip()

        if not new_text:
            if not current_prompt:
                await self.send(chat_id, "Chua co noi dung system prompt tuy chinh nao.")
            else:
                preview = current_prompt[:3500]
                suffix = "\n... (con nua)" if len(current_prompt) > 3500 else ""
                await self.send(chat_id, f"System prompt hien tai:\n\n{preview}{suffix}")
            return True

        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        updated_prompt = (
            f"{current_prompt}\n\n---\n\n# CAP NHAT ({today})\n\n{new_text}"
            if current_prompt else new_text
        )
        ok = _save_hermes_config_value("agent.system_prompt", updated_prompt)
        await self.send(
            chat_id,
            "Da luu. Can gateway khoi dong lai moi ap dung — nhan /restart "
            "(nhan tin rieng cho bot) de ap dung ngay."
            if ok else "Luu that bai, thu lai sau.",
        )
        return True

    def _sender_can_use_new_command(self, data: Dict[str, Any]) -> bool:
        """Restrict the bare "!new" shortcut to a specific allowlist.

        Deliberately separate from ``ZALO_ALLOWED_USERS``/``ZALO_ALLOW_ALL_USERS``
        (identity gating for talking to the bot at all) — a group opened via
        ``!moquyenchat`` sets ``ZALO_ALLOW_ALL_USERS=true`` for everyone, but
        resetting someone else's session is a more sensitive action that
        should stay opt-in per user via ``ZALO_NEW_COMMAND_USERS``.
        """
        allowed = self._coerce_chat_set(_zenv("ZALO_NEW_COMMAND_USERS", ""))
        sender_id = str(data.get("sender_id") or "").strip()
        return bool(sender_id and ("*" in allowed or sender_id in allowed))

    def _rewrite_new_session_command(self, data: Dict[str, Any]) -> bool:
        """Rewrite a bare "!new" from an allowlisted sender into a real "/new".

        Returns True when the rewrite happened, so the caller can skip the
        normal @mention gate for this one message — the sender is already
        independently authorized via ``ZALO_NEW_COMMAND_USERS``, so no
        confirmation step and no mention are required. Mutates ``data``
        in place so the MessageEvent built downstream carries plain "/new",
        which MessageEvent.is_command() recognizes.
        """
        text = str(data.get("text") or "")
        if not _NEW_SESSION_COMMAND_RE.search(text):
            return False
        if not self._sender_can_use_new_command(data):
            return False
        data["text"] = "/new"
        return True

    async def _build_message_event(self, data: Dict[str, Any]) -> Optional[MessageEvent]:
        """Build a MessageEvent from a bridge message event.

        The bridge has no inbound-media forwarding in v1 for most content
        types (``messageToEvent`` only surfaces plain-string text plus a
        ``content_type`` label) — those become a short descriptive
        placeholder rather than a downloadable attachment. ``chat.photo`` is
        the one exception: the bridge forwards zca-js's attachment URL and
        this downloads it so the agent can actually view the image.
        """
        try:
            # Defense in depth: the bridge already suppresses its own
            # outbound-message echo (`if (message.isSelf) return;`).
            if data.get("is_self"):
                return None
            if await self._handle_chat_permission_command(data):
                return None
            if await self._handle_prompt_update_command(data):
                return None
            is_new_session_cmd = self._rewrite_new_session_command(data)
            if not is_new_session_cmd and not (
                self._is_message_access_allowed(data) and self._should_respond(data)
            ):
                return None

            chat_id = str(data.get("chat_id") or "")
            is_group = bool(data.get("is_group"))
            chat_type = "group" if is_group else "dm"
            sender_name = data.get("sender_name")
            if not is_group and sender_name:
                self._chat_names[chat_id] = sender_name

            text = str(data.get("text") or "")
            content_type = str(data.get("content_type") or "").strip()
            media_urls: list[str] = []
            media_types: list[str] = []
            attachment_url = data.get("attachment_url")
            if content_type == "chat.photo" and attachment_url:
                try:
                    local_path = await cache_image_from_url(str(attachment_url))
                    media_urls.append(local_path)
                    # Must be a real MIME type: gateway/run.py's
                    # _event_media_is_image() only recognizes attachments whose
                    # media_type starts with "image/" — a bare "image" string
                    # falls through and the photo never reaches the model as
                    # actual vision content (silently degrades to a text note).
                    media_types.append("image/jpeg")
                    if not text:
                        text = "[Sent a photo]"
                except Exception as e:
                    logger.warning("[%s] Failed to download inbound photo: %s", self.name, e)
                    if not text:
                        text = "[Received a photo message — download failed]"
            elif not text and content_type:
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
                message_type=MessageType.PHOTO if media_urls else MessageType.TEXT,
                source=source,
                raw_message=data,
                message_id=data.get("message_id"),
                media_urls=media_urls,
                media_types=media_types,
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
    if "disable_dms" in zalo_cfg and not os.getenv("ZALO_DISABLE_DMS"):
        os.environ["ZALO_DISABLE_DMS"] = str(zalo_cfg["disable_dms"]).lower()
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
            "come from a chat explicitly configured to always respond. Direct "
            "messages may be disabled by the operator; when they are enabled, "
            "they don't need a mention. "
            "You can send media files natively: include "
            "MEDIA:/absolute/path/to/file in your response; images and other "
            "files are delivered as native Zalo attachments. A photo the user "
            "sends IS downloaded and given to you to actually view. Other "
            "inbound media (video/file/voice/gif/sticker) still arrives only "
            "as a description, not a file — you cannot view those. In a GROUP chat, you can "
            "tag everyone by writing the literal text '@all' in your response "
            "(e.g. '@all Chào cả nhà...') — it renders as a real tappable "
            "@all mention, not a link. Only use it when actually addressing "
            "the whole group (e.g. a self-introduction), not in every reply."
        ),
    )

    ctx.register_cli_command(
        name="zalo",
        help="Set up and manage the Zalo integration (QR pairing via a Node.js bridge)",
        setup_fn=_cli.register_cli,
        handler_fn=_cli.dispatch,
    )

    from . import group_memory as _group_memory

    ctx.register_hook("pre_gateway_dispatch", _group_memory.on_pre_gateway_dispatch)
    ctx.register_system_prompt_section(
        "zalo-group-memory", _group_memory.zalo_group_summary_section, max_chars=4000,
    )
