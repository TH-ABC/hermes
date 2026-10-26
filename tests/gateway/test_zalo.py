"""Tests for the Zalo platform plugin (bridge-backed, zca-js).

All bridge HTTP calls are mocked (aiohttp) — no real Node process is ever
spawned. Real ``subprocess.Popen``/``npm`` calls are patched out in every
test that exercises ``connect()``.
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from gateway.config import Platform, PlatformConfig


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
ZALO_PLUGIN_DIR = REPO_ROOT / "plugins" / "platforms" / "zalo"


class _AsyncCM:
    """Minimal async context manager returning a fixed value."""

    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *exc):
        return False


def _mock_health(json_data, status=200):
    """Mock aiohttp.ClientSession whose GET returns *status* + *json_data*."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_data)
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=_AsyncCM(mock_resp))
    mock_session.close = AsyncMock()
    return MagicMock(return_value=_AsyncCM(mock_session))


def _make_adapter(bridge_script="/tmp/test-zalo-bridge.js", session_path=None,
                   require_mention=True, mention_name="", free_response_chats=None,
                   own_uid=None, disable_dms=False, owner_id="", group_allow_from=None,
                   groups=None):
    """Create a ZaloAdapter with test attributes (bypass __init__)."""
    from plugins.platforms.zalo.adapter import ZaloAdapter

    adapter = ZaloAdapter.__new__(ZaloAdapter)
    adapter.platform = Platform("zalo")
    adapter.config = MagicMock()
    adapter._bridge_port = 19850
    adapter._bridge_script = bridge_script
    adapter._session_path = session_path or Path("/tmp/test-zalo-session")
    adapter._own_id_path = adapter._session_path / "own_id.txt"
    adapter._own_uid = own_uid
    adapter._require_mention = require_mention
    adapter._mention_name = mention_name
    adapter._free_response_chats = free_response_chats or set()
    adapter._disable_dms = disable_dms
    adapter._owner_id = owner_id
    adapter._group_allow_from = group_allow_from or set()
    adapter._groups = groups or {}
    adapter._dm_policy = "allowlist"
    adapter._group_policy = "allowlist"
    adapter._chat_names = {}
    adapter._bridge_log_fh = None
    adapter._bridge_log = None
    adapter._bridge_process = None
    adapter._poll_task = None
    adapter._http_session = None
    adapter._running = False
    adapter._fatal_error_code = None
    adapter._fatal_error_message = None
    adapter._fatal_error_retryable = True
    adapter._fatal_error_handler = None
    adapter._shutting_down = False
    return adapter


def _setup_bridge_dir(tmp_path: Path) -> Path:
    """Create a real bridge dir with bridge.js + package.json + creds."""
    bridge_dir = tmp_path / "zalo-bridge"
    bridge_dir.mkdir()
    (bridge_dir / "bridge.js").write_text("// current bridge code\n")
    (bridge_dir / "package.json").write_text('{"name": "zalo-bridge"}\n')
    session_path = tmp_path / "session"
    session_path.mkdir()
    (session_path / "zalo_creds.json").write_text("{}")
    return bridge_dir


def _fresh_node_modules(bridge_dir: Path) -> None:
    from plugins.platforms.zalo.adapter import _file_content_hash

    nm = bridge_dir / "node_modules"
    nm.mkdir()
    (nm / ".hermes-pkg-hash").write_text(
        _file_content_hash(bridge_dir / "package.json")
    )


# ---------------------------------------------------------------------------
# Platform registration
# ---------------------------------------------------------------------------


class TestPlatformRegistration:
    def test_platform_zalo_registers_as_platform_zalo(self):
        assert Platform("zalo") is Platform.ZALO
        assert Platform("zalo").value == "zalo"

    def test_register_ctx_wiring_via_real_plugin_discovery(self):
        """Drive through the real plugin loader end-to-end (no mocking of
        register()/PlatformEntry) to catch any kwarg mismatch that would
        raise TypeError from the PlatformEntry dataclass constructor."""
        import hermes_cli.plugins as plugins_mod
        from gateway.platform_registry import platform_registry

        plugins_mod.discover_plugins(force=True)
        entry = platform_registry.get("zalo")
        assert entry is not None
        assert entry.label == "Zalo"
        assert entry.emoji == "💬"
        assert entry.max_message_length == 2000
        assert entry.allow_update_command is True
        assert entry.required_env == ["ZALO_ENABLED"]
        assert entry.allowed_users_env == "ZALO_ALLOWED_USERS"
        assert entry.allow_all_env == "ZALO_ALLOW_ALL_USERS"
        assert entry.cron_deliver_env_var == "ZALO_HOME_CHANNEL"
        assert entry.source == "plugin"
        assert callable(entry.adapter_factory)
        assert callable(entry.check_fn)
        assert callable(entry.is_connected)
        assert callable(entry.setup_fn)
        assert callable(entry.apply_yaml_config_fn)
        assert callable(entry.standalone_sender_fn)
        assert "Zalo" in entry.platform_hint
        assert "Vietnamese" in entry.platform_hint

        manager = plugins_mod.get_plugin_manager()
        cli_entry = manager._cli_commands.get("zalo")
        assert cli_entry is not None
        assert callable(cli_entry["setup_fn"])
        assert callable(cli_entry["handler_fn"])


class TestPluginYamlManifest:
    def test_plugin_yaml_structure(self):
        data = yaml.safe_load((ZALO_PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8"))
        assert data["kind"] == "platform"
        required_names = {e["name"] for e in data["requires_env"]}
        assert required_names == {"ZALO_ENABLED"}
        optional_names = {e["name"] for e in data["optional_env"]}
        assert optional_names == {
            "ZALO_ALLOWED_USERS",
            "ZALO_ALLOW_ALL_USERS",
            "ZALO_HOME_CHANNEL",
            "ZALO_DISABLE_DMS",
            "ZALO_REQUIRE_MENTION",
            "ZALO_MENTION_NAME",
            "ZALO_FREE_RESPONSE_CHATS",
            "ZALO_BRIDGE_PORT",
        }


# ---------------------------------------------------------------------------
# Config parsing / defaults
# ---------------------------------------------------------------------------


class TestConfigDefaults:
    def _build(self, extra=None, monkeypatch=None):
        from plugins.platforms.zalo.adapter import ZaloAdapter

        if monkeypatch is not None:
            for var in (
                "ZALO_BRIDGE_PORT", "ZALO_REQUIRE_MENTION", "ZALO_MENTION_NAME",
                "ZALO_FREE_RESPONSE_CHATS", "ZALO_DISABLE_DMS",
            ):
                monkeypatch.delenv(var, raising=False)
        config = PlatformConfig(enabled=True, extra=extra or {})
        return ZaloAdapter(config)

    def test_default_bridge_port_is_3050(self, monkeypatch):
        adapter = self._build(monkeypatch=monkeypatch)
        assert adapter._bridge_port == 3050

    def test_bridge_port_override_via_extra(self, monkeypatch):
        adapter = self._build(extra={"bridge_port": 4444}, monkeypatch=monkeypatch)
        assert adapter._bridge_port == 4444

    def test_bridge_port_override_via_env(self, monkeypatch):
        monkeypatch.setenv("ZALO_BRIDGE_PORT", "5555")
        adapter = self._build(monkeypatch=None)
        assert adapter._bridge_port == 5555

    def test_require_mention_defaults_true(self, monkeypatch):
        adapter = self._build(monkeypatch=monkeypatch)
        assert adapter._require_mention is True

    def test_require_mention_false_via_extra(self, monkeypatch):
        adapter = self._build(extra={"require_mention": "false"}, monkeypatch=monkeypatch)
        assert adapter._require_mention is False

    def test_mention_name_string_form(self, monkeypatch):
        adapter = self._build(extra={"mention_name": "Hermes"}, monkeypatch=monkeypatch)
        assert adapter._mention_name == "Hermes"

    def test_free_response_chats_string_form(self, monkeypatch):
        adapter = self._build(
            extra={"free_response_chats": "g:1, g:2 ,g:3"}, monkeypatch=monkeypatch
        )
        assert adapter._free_response_chats == {"g:1", "g:2", "g:3"}

    def test_free_response_chats_list_form(self, monkeypatch):
        adapter = self._build(
            extra={"free_response_chats": ["g:1", "g:2"]}, monkeypatch=monkeypatch
        )
        assert adapter._free_response_chats == {"g:1", "g:2"}

    def test_free_response_chats_empty_by_default(self, monkeypatch):
        adapter = self._build(monkeypatch=monkeypatch)
        assert adapter._free_response_chats == set()

    def test_owner_id_empty_by_default(self, monkeypatch):
        adapter = self._build(monkeypatch=monkeypatch)
        assert adapter._owner_id == ""

    def test_owner_id_from_extra(self, monkeypatch):
        adapter = self._build(extra={"owner_id": "u:1"}, monkeypatch=monkeypatch)
        assert adapter._owner_id == "u:1"

    def test_group_allow_from_string_form(self, monkeypatch):
        adapter = self._build(
            extra={"group_allow_from": "u:1, u:2 ,u:3"}, monkeypatch=monkeypatch
        )
        assert adapter._group_allow_from == {"u:1", "u:2", "u:3"}

    def test_group_allow_from_list_form(self, monkeypatch):
        adapter = self._build(
            extra={"group_allow_from": ["u:1", "u:2"]}, monkeypatch=monkeypatch
        )
        assert adapter._group_allow_from == {"u:1", "u:2"}

    def test_group_allow_from_empty_by_default(self, monkeypatch):
        adapter = self._build(monkeypatch=monkeypatch)
        assert adapter._group_allow_from == set()

    def test_groups_empty_dict_by_default(self, monkeypatch):
        adapter = self._build(monkeypatch=monkeypatch)
        assert adapter._groups == {}

    def test_groups_dict_from_extra(self, monkeypatch):
        adapter = self._build(
            extra={"groups": {"g:1": {"allow_from": ["*"]}}}, monkeypatch=monkeypatch
        )
        assert adapter._groups == {"g:1": {"allow_from": ["*"]}}

    def test_enforces_own_access_policy_is_true(self, monkeypatch):
        adapter = self._build(monkeypatch=monkeypatch)
        assert adapter.enforces_own_access_policy is True

    def test_disable_dms_false_by_default(self, monkeypatch):
        adapter = self._build(monkeypatch=monkeypatch)
        assert adapter._disable_dms is False

    def test_disable_dms_true_via_extra(self, monkeypatch):
        adapter = self._build(extra={"disable_dms": "true"}, monkeypatch=monkeypatch)
        assert adapter._disable_dms is True


# ---------------------------------------------------------------------------
# _should_respond() gating matrix
# ---------------------------------------------------------------------------


class TestShouldRespond:
    def test_dm_always_true(self):
        adapter = _make_adapter(require_mention=True)
        assert adapter._should_respond({"is_group": False}) is True

    def test_group_no_mention_required_true(self):
        adapter = _make_adapter(require_mention=False)
        assert adapter._should_respond({"is_group": True, "text": "anything"}) is True

    def test_group_free_response_chat_true(self):
        adapter = _make_adapter(require_mention=True, free_response_chats={"g:123"})
        assert adapter._should_respond({"is_group": True, "chat_id": "g:123", "text": "hi"}) is True

    def test_group_structured_mention_uid_match_true(self):
        adapter = _make_adapter(require_mention=True, own_uid="999")
        data = {
            "is_group": True,
            "chat_id": "g:1",
            "text": "hey",
            "mentions": [{"uid": "999"}],
        }
        assert adapter._should_respond(data) is True

    def test_group_mention_name_substring_fallback_true(self):
        adapter = _make_adapter(require_mention=True, mention_name="Hermes")
        data = {"is_group": True, "chat_id": "g:1", "text": "hey hermes can you help"}
        assert adapter._should_respond(data) is True

    def test_group_none_of_above_false(self):
        adapter = _make_adapter(require_mention=True, own_uid="999", mention_name="Hermes")
        data = {
            "is_group": True,
            "chat_id": "g:1",
            "text": "just chatting",
            "mentions": [{"uid": "111"}],
        }
        assert adapter._should_respond(data) is False

    def test_group_mention_uid_mismatch_and_no_name_configured_false(self):
        adapter = _make_adapter(require_mention=True, own_uid="999")
        data = {"is_group": True, "chat_id": "g:1", "text": "hi", "mentions": []}
        assert adapter._should_respond(data) is False


class TestAccessControl:
    # --- DMs ---
    def test_dm_owner_allowed(self):
        adapter = _make_adapter(owner_id="u:owner")
        assert adapter._is_dm_allowed("u:owner") is True

    def test_dm_non_owner_denied(self):
        adapter = _make_adapter(owner_id="u:owner")
        assert adapter._is_dm_allowed("u:other") is False

    def test_dm_denied_when_no_owner_configured(self):
        adapter = _make_adapter(owner_id="")
        assert adapter._is_dm_allowed("u:anyone") is False

    def test_dm_denied_for_owner_when_disabled(self):
        adapter = _make_adapter(owner_id="u:owner", disable_dms=True)
        assert adapter._is_dm_allowed("u:owner") is False

    # --- Groups ---
    def test_group_owner_always_allowed(self):
        adapter = _make_adapter(owner_id="u:owner")
        assert adapter._is_group_allowed("g:unopened", "u:owner") is True

    def test_group_opened_allows_any_sender(self):
        adapter = _make_adapter(groups={"g:main": {"allow_from": ["*"]}})
        assert adapter._is_group_allowed("g:main", "u:random") is True

    def test_group_unopened_allows_group_allow_from_member(self):
        adapter = _make_adapter(group_allow_from={"u:1", "u:2"})
        assert adapter._is_group_allowed("g:other", "u:1") is True

    def test_group_unopened_denies_non_listed_sender(self):
        adapter = _make_adapter(group_allow_from={"u:1"})
        assert adapter._is_group_allowed("g:other", "u:2") is False

    def test_group_allow_from_wildcard(self):
        adapter = _make_adapter(group_allow_from={"*"})
        assert adapter._is_group_allowed("g:other", "u:anyone") is True

    # --- _is_message_access_allowed end-to-end ---
    def test_message_access_missing_sender_id_denied(self):
        adapter = _make_adapter(owner_id="u:owner")
        assert adapter._is_message_access_allowed({"is_group": False, "sender_id": ""}) is False

    def test_message_access_dm_owner_allowed(self):
        adapter = _make_adapter(owner_id="u:owner")
        assert adapter._is_message_access_allowed(
            {"is_group": False, "sender_id": "u:owner"}
        ) is True

    def test_message_access_group_opened_allowed(self):
        adapter = _make_adapter(groups={"g:main": {"allow_from": ["*"]}})
        assert adapter._is_message_access_allowed(
            {"is_group": True, "chat_id": "g:main", "sender_id": "u:random"}
        ) is True


class TestChatPermissionCommands:
    @pytest.mark.asyncio
    async def test_open_chat_permission_adds_without_removing_other_groups(self, monkeypatch):
        """!moquyenchat is additive — opening a new group must not disturb a
        pre-existing different group's entry (the union-not-replace fix)."""
        adapter = _make_adapter(owner_id="u:owner", groups={"g:other": {"allow_from": ["*"]}})
        adapter.send = AsyncMock()
        saved = {}
        monkeypatch.setattr(
            "plugins.platforms.zalo.adapter.save_zalo_extra_value",
            lambda k, v: saved.__setitem__(k, v) or True,
        )

        handled = await adapter._handle_chat_permission_command({
            "is_group": True,
            "chat_id": "g:main",
            "sender_id": "u:owner",
            "text": "!moquyenchat",
        })

        assert handled is True
        assert adapter._groups["g:main"] == {"allow_from": ["*"]}
        assert adapter._groups["g:other"] == {"allow_from": ["*"]}
        assert saved["groups"] == adapter._groups
        adapter.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_chat_permission_removes_only_current_group(self, monkeypatch):
        adapter = _make_adapter(
            owner_id="u:owner",
            groups={"g:main": {"allow_from": ["*"]}, "g:other": {"allow_from": ["*"]}},
        )
        adapter.send = AsyncMock()
        saved = {}
        monkeypatch.setattr(
            "plugins.platforms.zalo.adapter.save_zalo_extra_value",
            lambda k, v: saved.__setitem__(k, v) or True,
        )

        handled = await adapter._handle_chat_permission_command({
            "is_group": True,
            "chat_id": "g:main",
            "sender_id": "u:owner",
            "text": "!dongquyenchat",
        })

        assert handled is True
        assert "g:main" not in adapter._groups
        assert adapter._groups["g:other"] == {"allow_from": ["*"]}
        adapter.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chat_permission_command_rejects_non_owner_sender(self, monkeypatch):
        adapter = _make_adapter(owner_id="u:owner")
        adapter.send = AsyncMock()
        saved = {}
        monkeypatch.setattr(
            "plugins.platforms.zalo.adapter.save_zalo_extra_value",
            lambda k, v: saved.__setitem__(k, v) or True,
        )

        handled = await adapter._handle_chat_permission_command({
            "is_group": True,
            "chat_id": "g:main",
            "sender_id": "u:other",
            "text": "!moquyenchat",
        })

        assert handled is True
        assert adapter._groups == {}
        assert saved == {}
        adapter.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chat_permission_command_ignores_legacy_allow_all_users(self, monkeypatch):
        """Regression guard for the self-widening privilege-escalation bug:
        a non-owner sender must stay rejected even when the legacy
        ZALO_ALLOW_ALL_USERS/ZALO_ALLOWED_USERS env vars would have allowed
        them under the old model."""
        adapter = _make_adapter(owner_id="u:owner")
        adapter.send = AsyncMock()
        monkeypatch.setenv("ZALO_ALLOW_ALL_USERS", "true")
        monkeypatch.setenv("ZALO_ALLOWED_USERS", "u:other")

        handled = await adapter._handle_chat_permission_command({
            "is_group": True,
            "chat_id": "g:main",
            "sender_id": "u:other",
            "text": "!moquyenchat",
        })

        assert handled is True
        assert adapter._groups == {}

    @pytest.mark.asyncio
    async def test_chat_permission_commands_do_not_touch_dm_or_mention_settings(self, monkeypatch):
        adapter = _make_adapter(owner_id="u:owner", disable_dms=False, require_mention=True)
        adapter.send = AsyncMock()
        monkeypatch.setattr(
            "plugins.platforms.zalo.adapter.save_zalo_extra_value", lambda k, v: True
        )

        await adapter._handle_chat_permission_command({
            "is_group": True, "chat_id": "g:main", "sender_id": "u:owner", "text": "!moquyenchat",
        })
        assert adapter._disable_dms is False
        assert adapter._require_mention is True

        await adapter._handle_chat_permission_command({
            "is_group": True, "chat_id": "g:main", "sender_id": "u:owner", "text": "!dongquyenchat",
        })
        assert adapter._disable_dms is False
        assert adapter._require_mention is True

    @pytest.mark.asyncio
    async def test_open_chat_permission_persist_failure_still_applies_in_memory(self, monkeypatch):
        adapter = _make_adapter(owner_id="u:owner")
        adapter.send = AsyncMock()
        monkeypatch.setattr(
            "plugins.platforms.zalo.adapter.save_zalo_extra_value", lambda k, v: False
        )

        handled = await adapter._handle_chat_permission_command({
            "is_group": True, "chat_id": "g:main", "sender_id": "u:owner", "text": "!moquyenchat",
        })

        assert handled is True
        assert adapter._groups["g:main"] == {"allow_from": ["*"]}
        sent_text = adapter.send.await_args.args[1]
        assert "khong luu duoc" in sent_text


# ---------------------------------------------------------------------------
# _load_own_uid() / _adopt_own_uid_from_health()
# ---------------------------------------------------------------------------


class TestOwnUid:
    def test_load_own_uid_reads_file(self, tmp_path):
        adapter = _make_adapter(session_path=tmp_path)
        (tmp_path / "own_id.txt").write_text("abc123", encoding="utf-8")
        assert adapter._load_own_uid() == "abc123"

    def test_load_own_uid_returns_none_when_missing(self, tmp_path):
        adapter = _make_adapter(session_path=tmp_path)
        assert adapter._load_own_uid() is None

    def test_load_own_uid_returns_none_when_empty(self, tmp_path):
        adapter = _make_adapter(session_path=tmp_path)
        (tmp_path / "own_id.txt").write_text("  \n", encoding="utf-8")
        assert adapter._load_own_uid() is None

    def test_adopt_noop_when_own_uid_already_set(self, tmp_path):
        adapter = _make_adapter(session_path=tmp_path, own_uid="existing")
        adapter._adopt_own_uid_from_health({"ownId": "new-uid"})
        assert adapter._own_uid == "existing"
        assert not (tmp_path / "own_id.txt").exists()

    def test_adopt_noop_when_own_id_falsy(self, tmp_path):
        adapter = _make_adapter(session_path=tmp_path, own_uid=None)
        adapter._adopt_own_uid_from_health({"ownId": ""})
        assert adapter._own_uid is None
        adapter._adopt_own_uid_from_health({})
        assert adapter._own_uid is None

    def test_adopt_sets_and_persists_when_missing(self, tmp_path):
        adapter = _make_adapter(session_path=tmp_path, own_uid=None)
        adapter._adopt_own_uid_from_health({"ownId": "abc999"})
        assert adapter._own_uid == "abc999"
        assert (tmp_path / "own_id.txt").read_text(encoding="utf-8") == "abc999"


# ---------------------------------------------------------------------------
# connect() — preflight, reuse, staleness
# ---------------------------------------------------------------------------


class TestConnectPreflight:
    @pytest.mark.asyncio
    async def test_refuses_to_spawn_node_when_unpaired(self, tmp_path):
        """No zalo_creds.json -> fatal, non-retryable, subprocess.Popen never called."""
        bridge = tmp_path / "bridge.js"
        bridge.write_text("// stub")
        session_path = tmp_path / "session"
        session_path.mkdir()
        # Deliberately no zalo_creds.json written.

        adapter = _make_adapter(bridge_script=str(bridge), session_path=session_path)

        with patch("plugins.platforms.zalo.adapter.check_zalo_requirements", return_value=True), \
             patch("subprocess.Popen") as mock_popen:
            result = await adapter.connect()

        assert result is False
        assert adapter._fatal_error_code == "zalo_not_paired"
        assert adapter._fatal_error_retryable is False
        mock_popen.assert_not_called()

    @pytest.mark.asyncio
    async def test_fatal_when_node_missing(self, tmp_path):
        adapter = _make_adapter(session_path=tmp_path)
        with patch("plugins.platforms.zalo.adapter.check_zalo_requirements", return_value=False), \
             patch("subprocess.Popen") as mock_popen:
            result = await adapter.connect()
        assert result is False
        assert adapter._fatal_error_code == "zalo_node_missing"
        mock_popen.assert_not_called()

    @pytest.mark.asyncio
    async def test_fatal_when_bridge_script_missing(self, tmp_path):
        adapter = _make_adapter(
            bridge_script=str(tmp_path / "does-not-exist.js"),
            session_path=tmp_path,
        )
        with patch("plugins.platforms.zalo.adapter.check_zalo_requirements", return_value=True):
            result = await adapter.connect()
        assert result is False
        assert adapter._fatal_error_code == "zalo_bridge_missing"


class TestConnectBridgeReuse:
    @pytest.mark.asyncio
    async def test_reuses_connected_bridge_with_matching_hash(self, tmp_path):
        from plugins.platforms.zalo.adapter import _file_content_hash

        bridge_dir = _setup_bridge_dir(tmp_path)
        _fresh_node_modules(bridge_dir)
        session_path = tmp_path / "session"
        adapter = _make_adapter(
            bridge_script=str(bridge_dir / "bridge.js"), session_path=session_path,
        )
        disk_hash = _file_content_hash(bridge_dir / "bridge.js")
        mock_client = _mock_health({
            "status": "connected", "scriptHash": disk_hash, "ownId": "own-1",
        })

        with patch("plugins.platforms.zalo.adapter.check_zalo_requirements", return_value=True), \
             patch("aiohttp.ClientSession", mock_client), \
             patch.object(adapter, "_acquire_platform_lock", return_value=True, create=True), \
             patch("subprocess.Popen") as mock_popen, \
             patch("plugins.platforms.zalo.adapter.asyncio.create_task", return_value=MagicMock()):
            result = await adapter.connect()

        assert result is True
        assert adapter._running is True
        mock_popen.assert_not_called()
        assert adapter._own_uid == "own-1"
        assert (session_path / "own_id.txt").read_text(encoding="utf-8") == "own-1"

    @pytest.mark.asyncio
    async def test_stale_hash_triggers_restart_not_reuse(self, tmp_path):
        """A running bridge reporting a stale/different scriptHash must NOT
        be reused — connect() should fall through to spawning a fresh one."""
        bridge_dir = _setup_bridge_dir(tmp_path)
        _fresh_node_modules(bridge_dir)
        session_path = tmp_path / "session"
        adapter = _make_adapter(
            bridge_script=str(bridge_dir / "bridge.js"), session_path=session_path,
        )
        mock_client = _mock_health({
            "status": "connected", "scriptHash": "deadbeefdeadbeef",
        })
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # dies immediately -> connect() returns False
        mock_proc.returncode = 1

        with patch("plugins.platforms.zalo.adapter.check_zalo_requirements", return_value=True), \
             patch("aiohttp.ClientSession", mock_client), \
             patch("plugins.platforms.zalo.adapter.asyncio.sleep", new_callable=AsyncMock), \
             patch("plugins.platforms.zalo.adapter._kill_stale_bridge_by_pidfile"), \
             patch("plugins.platforms.zalo.adapter._kill_port_process"), \
             patch("subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch.object(adapter, "_acquire_platform_lock", return_value=True, create=True):
            result = await adapter.connect()

        # Reuse shortcut was NOT taken (diverged into the spawn path), which
        # then failed fast because the fake process died immediately.
        mock_popen.assert_called_once()
        assert result is False

    @pytest.mark.asyncio
    async def test_unconnected_running_bridge_triggers_restart(self, tmp_path):
        bridge_dir = _setup_bridge_dir(tmp_path)
        _fresh_node_modules(bridge_dir)
        session_path = tmp_path / "session"
        adapter = _make_adapter(
            bridge_script=str(bridge_dir / "bridge.js"), session_path=session_path,
        )
        mock_client = _mock_health({"status": "disconnected"})
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1
        mock_proc.returncode = 1

        with patch("plugins.platforms.zalo.adapter.check_zalo_requirements", return_value=True), \
             patch("aiohttp.ClientSession", mock_client), \
             patch("plugins.platforms.zalo.adapter.asyncio.sleep", new_callable=AsyncMock), \
             patch("plugins.platforms.zalo.adapter._kill_stale_bridge_by_pidfile"), \
             patch("plugins.platforms.zalo.adapter._kill_port_process"), \
             patch("subprocess.Popen", return_value=mock_proc) as mock_popen, \
             patch.object(adapter, "_acquire_platform_lock", return_value=True, create=True):
            result = await adapter.connect()

        mock_popen.assert_called_once()
        assert result is False


class TestConnectNpmInstall:
    @pytest.mark.asyncio
    async def test_skips_install_when_stamp_fresh(self, tmp_path):
        bridge_dir = _setup_bridge_dir(tmp_path)
        _fresh_node_modules(bridge_dir)
        session_path = tmp_path / "session"
        adapter = _make_adapter(
            bridge_script=str(bridge_dir / "bridge.js"), session_path=session_path,
        )
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1
        mock_proc.returncode = 1

        with patch("plugins.platforms.zalo.adapter.check_zalo_requirements", return_value=True), \
             patch("aiohttp.ClientSession", _mock_health({"status": "disconnected"})), \
             patch("plugins.platforms.zalo.adapter.asyncio.sleep", new_callable=AsyncMock), \
             patch("plugins.platforms.zalo.adapter._kill_stale_bridge_by_pidfile"), \
             patch("plugins.platforms.zalo.adapter._kill_port_process"), \
             patch("subprocess.run") as mock_run, \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(adapter, "_acquire_platform_lock", return_value=True, create=True):
            await adapter.connect()

        mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_installs_when_stamp_missing(self, tmp_path):
        bridge_dir = _setup_bridge_dir(tmp_path)
        session_path = tmp_path / "session"
        adapter = _make_adapter(
            bridge_script=str(bridge_dir / "bridge.js"), session_path=session_path,
        )
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1
        mock_proc.returncode = 1
        install_result = MagicMock(returncode=0)

        with patch("plugins.platforms.zalo.adapter.check_zalo_requirements", return_value=True), \
             patch("aiohttp.ClientSession", _mock_health({"status": "disconnected"})), \
             patch("plugins.platforms.zalo.adapter.asyncio.sleep", new_callable=AsyncMock), \
             patch("plugins.platforms.zalo.adapter._kill_stale_bridge_by_pidfile"), \
             patch("plugins.platforms.zalo.adapter._kill_port_process"), \
             patch("subprocess.run", return_value=install_result) as mock_run, \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(adapter, "_acquire_platform_lock", return_value=True, create=True):
            await adapter.connect()

        mock_run.assert_called_once()
        assert mock_run.call_args.args[0][:2] == [mock_run.call_args.args[0][0], "install"]

    @pytest.mark.asyncio
    async def test_fatal_when_npm_install_fails(self, tmp_path):
        bridge_dir = _setup_bridge_dir(tmp_path)
        session_path = tmp_path / "session"
        adapter = _make_adapter(
            bridge_script=str(bridge_dir / "bridge.js"), session_path=session_path,
        )
        install_result = MagicMock(returncode=1, stderr="boom")

        with patch("plugins.platforms.zalo.adapter.check_zalo_requirements", return_value=True), \
             patch("subprocess.run", return_value=install_result), \
             patch.object(adapter, "_acquire_platform_lock", return_value=True, create=True):
            result = await adapter.connect()

        assert result is False
        assert adapter._fatal_error_code == "zalo_npm_install_failed"


# ---------------------------------------------------------------------------
# pidfile recycled-PID guard (shared logic ported from WhatsApp)
# ---------------------------------------------------------------------------


def _spawn_sleeper(*extra_argv) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(0.2)", *extra_argv]
    )


def _wait_dead(proc: subprocess.Popen, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return True
        time.sleep(0.05)
    return False


class TestPidfileRecycledPidGuard:
    def test_kills_when_start_time_matches(self, tmp_path):
        from plugins.platforms.zalo.adapter import _kill_stale_bridge_by_pidfile, _write_bridge_pidfile

        proc = _spawn_sleeper()
        try:
            _write_bridge_pidfile(tmp_path, proc.pid)
            _kill_stale_bridge_by_pidfile(tmp_path)
            assert _wait_dead(proc), "the real bridge process should be killed"
            assert not (tmp_path / "bridge.pid").exists()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def test_does_not_kill_recycled_pid(self, tmp_path):
        """A pidfile PID that is alive but is NOT our bridge (different
        start time, unrelated cmdline) must be left alone."""
        from plugins.platforms.zalo import adapter as zalo_adapter

        proc = _spawn_sleeper()  # a real, unrelated process
        try:
            # Legacy-style pidfile: PID only, no recorded start time, and the
            # cmdline check will fail because this process is not "node".
            (tmp_path / "bridge.pid").write_text(str(proc.pid))

            zalo_adapter._kill_stale_bridge_by_pidfile(tmp_path)

            # _pid_exists() liveness probes use os.kill(pid, 0), which is not
            # a real signal — the only real-signal path is SIGTERM, and that
            # must never fire for a process the identity guard rejected.
            assert proc.poll() is None, "the unrelated process must survive"
        finally:
            proc.kill()
            proc.wait()


# ---------------------------------------------------------------------------
# _apply_yaml_config()
# ---------------------------------------------------------------------------


class TestApplyYamlConfig:
    def test_translates_all_keys_to_env(self, monkeypatch):
        from plugins.platforms.zalo.adapter import _apply_yaml_config

        for var in (
            "ZALO_REQUIRE_MENTION", "ZALO_MENTION_NAME",
            "ZALO_FREE_RESPONSE_CHATS",
            "ZALO_DISABLE_DMS", "ZALO_BRIDGE_PORT",
        ):
            monkeypatch.delenv(var, raising=False)

        result = _apply_yaml_config({}, {
            "require_mention": False,
            "mention_name": "Hermes",
            "free_response_chats": ["g:1", "g:2"],
            "disable_dms": True,
            "bridge_port": 4000,
        })

        assert result is None
        assert __import__("os").environ["ZALO_REQUIRE_MENTION"] == "false"
        assert __import__("os").environ["ZALO_MENTION_NAME"] == "Hermes"
        assert __import__("os").environ["ZALO_FREE_RESPONSE_CHATS"] == "g:1,g:2"
        assert __import__("os").environ["ZALO_DISABLE_DMS"] == "true"
        assert __import__("os").environ["ZALO_BRIDGE_PORT"] == "4000"

    def test_env_takes_precedence_over_yaml(self, monkeypatch):
        from plugins.platforms.zalo.adapter import _apply_yaml_config

        monkeypatch.setenv("ZALO_MENTION_NAME", "AlreadySet")
        _apply_yaml_config({}, {"mention_name": "FromYaml"})
        assert __import__("os").environ["ZALO_MENTION_NAME"] == "AlreadySet"


# ---------------------------------------------------------------------------
# _standalone_send()
# ---------------------------------------------------------------------------


class TestStandaloneSend:
    @pytest.mark.asyncio
    async def test_sends_text_successfully(self):
        from plugins.platforms.zalo.adapter import _standalone_send

        pconfig = MagicMock(extra={"bridge_port": 19850})
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"message_id": "m1"})
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_AsyncCM(mock_resp))

        with patch("aiohttp.ClientSession", return_value=_AsyncCM(mock_session)):
            result = await _standalone_send(pconfig, "u:1", "hello")

        assert result["success"] is True
        assert result["platform"] == "zalo"
        assert result["message_id"] == "m1"

    @pytest.mark.asyncio
    async def test_sends_media_successfully(self, tmp_path):
        from plugins.platforms.zalo.adapter import _standalone_send

        media_file = tmp_path / "pic.png"
        media_file.write_bytes(b"fake")
        pconfig = MagicMock(extra={"bridge_port": 19850})

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"message_id": "m2"})
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_AsyncCM(mock_resp))

        with patch("aiohttp.ClientSession", return_value=_AsyncCM(mock_session)):
            result = await _standalone_send(
                pconfig, "u:1", "", media_files=[(str(media_file), False)],
            )

        assert result["success"] is True
        assert result["message_id"] == "m2"

    @pytest.mark.asyncio
    async def test_error_path_on_non_200(self):
        from plugins.platforms.zalo.adapter import _standalone_send

        pconfig = MagicMock(extra={"bridge_port": 19850})
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.text = AsyncMock(return_value="bridge exploded")
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_AsyncCM(mock_resp))

        with patch("aiohttp.ClientSession", return_value=_AsyncCM(mock_session)):
            result = await _standalone_send(pconfig, "u:1", "hello")

        assert "error" in result
        assert "bridge exploded" in result["error"]

    @pytest.mark.asyncio
    async def test_error_path_when_media_file_missing(self):
        from plugins.platforms.zalo.adapter import _standalone_send

        pconfig = MagicMock(extra={"bridge_port": 19850})

        with patch("aiohttp.ClientSession", return_value=_AsyncCM(MagicMock())):
            result = await _standalone_send(
                pconfig, "u:1", "", media_files=[("/no/such/file.png", False)],
            )

        assert "error" in result
        assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# send_typing() error swallowing
# ---------------------------------------------------------------------------


class TestSendTyping:
    @pytest.mark.asyncio
    async def test_swallows_errors_silently(self):
        adapter = _make_adapter()
        adapter._running = True
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=RuntimeError("network exploded"))
        adapter._http_session = mock_session

        # Must not raise.
        await adapter.send_typing("u:1")

    @pytest.mark.asyncio
    async def test_noop_when_not_running(self):
        adapter = _make_adapter()
        adapter._running = False
        adapter._http_session = MagicMock()
        adapter._http_session.post = MagicMock(side_effect=AssertionError("should not be called"))

        await adapter.send_typing("u:1")
