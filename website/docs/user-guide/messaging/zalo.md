---
sidebar_position: 6
title: "Zalo"
description: "Set up Hermes Agent as a Zalo bot via the unofficial zca-js Node.js bridge"
---

# Zalo Setup

Hermes connects to Zalo — Vietnam's most widely used chat app — through a local Node.js bridge built on **zca-js**, an unofficial, reverse-engineered Zalo Web client. Zalo has no official bot API for a personal account that can join a group as a normal member, so this works by emulating a Zalo Web session, the same way Hermes bridges WhatsApp via Baileys.

> Run `hermes gateway setup` and pick **Zalo** for a guided walk-through, or run `hermes zalo setup` directly.

:::warning Unofficial client — ban/lock risk
Zalo does not officially support third-party bots. Driving your account through zca-js can get it **temporarily locked or banned**. Use a secondary/dedicated Zalo account if you have one — not your primary account. This warning is shown every time you run `hermes zalo setup`.
:::

:::warning One web-listener session per account
Zalo allows only **one** active web-listener session per account at a time. If you open Zalo Web or Zalo Desktop with the same account the bridge is using, it will silently kick the bridge offline — and vice versa. Don't run the bridge and another Zalo Web session on the same account simultaneously.
:::

---

## Prerequisites

- **Node.js v18+** and **npm** — the Zalo bridge runs as a Node.js process
- **A phone with the Zalo app** installed (for scanning the QR code)
- A Zalo account, ideally a secondary one dedicated to the bot

---

## Step 1: Run the Setup Wizard

```bash
hermes zalo setup
```

The wizard will:

1. Print the ban-risk and one-listener-per-account warnings (every run)
2. Check for Node.js and install bridge dependencies on first run
3. Ask for confirmation, since setup disconnects any bridge already running for this session
4. Launch the bridge in pairing mode and display a **QR code**
5. Wait for you to scan it with the Zalo app

**To scan the QR code:**

1. Open Zalo on your phone
2. Use the in-app QR scanner (Zalo → the scan icon) to scan the code shown by the wizard
3. Confirm the login on your phone if prompted

Once paired, the wizard persists the bot's own Zalo uid (used for @mention gating), then prompts for:

- **Allowed users** — comma-separated Zalo user IDs allowed to talk to the bot (can be configured later)
- **Home channel** — default chat ID (`u:...` for a DM, `g:...` for a group) for reminders/cron delivery
- **Require @mention in groups** — whether the bot must be @-mentioned to respond in a group chat (default: yes)

Finally it sets `ZALO_ENABLED=true` and enables the plugin.

:::tip
If the QR code expires (they're time-limited) or the login is declined on the phone, `hermes zalo setup` reports the failure — just run it again.
:::

---

## Step 2: Start the Gateway

```bash
hermes gateway              # Foreground
hermes gateway install      # Install as a user service
sudo hermes gateway install --system   # Linux only: boot-time system service
```

The gateway starts the Zalo bridge automatically using the saved session under `~/.hermes/platforms/zalo/session`.

---

## Mention Gating in Groups

Zalo groups are **mention-gated by default** — the bot only responds to messages that either @-mention it or come from a chat explicitly configured to always respond. **Direct messages never require a mention**, but are owner-only by default — see [Access Control & Chat Permission Commands](#access-control--chat-permission-commands) below.

| Setting | Purpose |
|---------|---------|
| `ZALO_REQUIRE_MENTION` | Set to `false` to make the bot respond to every group message (default: `true`) |
| `ZALO_MENTION_NAME` | Bot display name used as a text-match fallback when the bridge can't resolve a structured `@mention` (e.g. the bot's own uid isn't known yet) |
| `ZALO_FREE_RESPONSE_CHATS` | Comma-separated group chat IDs (`g:...`) that bypass mention-gating entirely and always respond |

The bot's own Zalo uid is captured during pairing and stored in `~/.hermes/platforms/zalo/session/own_id.txt` for structured mention matching. If that file is ever lost, the adapter recovers the uid automatically from the running bridge on the next successful connection — no re-pairing needed.

---

## Configuration

Add the following to your `~/.hermes/.env` file:

```bash
# Required
ZALO_ENABLED=true

# Group mention gating (optional — defaults shown)
ZALO_REQUIRE_MENTION=true
ZALO_MENTION_NAME=
ZALO_FREE_RESPONSE_CHATS=

# Cron / notification delivery target (optional)
ZALO_HOME_CHANNEL=u:123456789

# Bridge port (optional)
ZALO_BRIDGE_PORT=3050
```

Access control (who may DM the bot, and which groups it responds in) lives in `~/.hermes/config.yaml`, not `.env` — see the next section.

See the full list in [Environment Variables → Zalo](/reference/environment-variables#zalo-bridge-zca-js).

---

## Access Control & Chat Permission Commands

Unlike most Hermes platforms, Zalo owns its own access policy directly (it does not use `ZALO_ALLOWED_USERS`/`ZALO_ALLOW_ALL_USERS` — see the note at the end of this section). Configure it under `platforms.zalo.extra` in `~/.hermes/config.yaml`:

```yaml
platforms:
  zalo:
    enabled: true
    extra:
      owner_id: "your_zalo_uid"       # the only account that may DM the bot
      group_allow_from: []            # uids allowed in groups NOT opened via !moquyenchat ("*" = everyone)
      groups: {}                      # populated automatically by !moquyenchat/!dongquyenchat
      disable_dms: false              # true blocks DMs entirely, including the owner
```

Set the owner without re-pairing:

```bash
hermes zalo owner <your_uid>   # or with no argument, print the current owner
```

**DMs** are owner-only: only `owner_id` may message the bot directly. With no `owner_id` configured, DMs are blocked for everyone (fail-closed) until you set one.

**Groups** default to closed. Members can talk to the bot in a group once either:
- they're listed in `group_allow_from` (or it contains `"*"`), or
- the group was opened with `!moquyenchat` (see below) — the owner is always allowed everywhere, including groups they haven't opened yet.

### `!moquyenchat` / `!dongquyenchat`

Typed as a plain message in a group (owner only):

| Command | Effect |
|---------|--------|
| `!moquyenchat` | Opens **this group** to every member — additive, does not affect any other group or DMs |
| `!dongquyenchat` | Closes **this group** back down to the regular `group_allow_from` list — does not affect any other group |

Both persist to `config.yaml` (`platforms.zalo.extra.groups`) immediately — no gateway restart needed.

### `!promptcapnhat [nội dung]`

Owner-only. Appends `nội dung` as a dated addition to `agent.system_prompt` in `config.yaml`, so the bot's instructions can be tuned from chat instead of editing files. With no text, echoes back the current system prompt. **Requires a gateway restart** to take effect (`agent.system_prompt` is loaded once at gateway startup) — send `/restart` as a DM afterward.

:::note Legacy escape hatch
Setting `ZALO_ALLOWED_USERS` or `ZALO_ALLOW_ALL_USERS` in `.env` disables everything above and falls back to a flat, platform-wide allowlist for every Zalo chat. Leave both unset to use the owner/group model.
:::

---

## Session Persistence

The bridge saves its session under `~/.hermes/platforms/zalo/session`. This means:

- **Sessions survive restarts** — you don't need to re-scan the QR code every time
- The session data includes credentials sufficient to act as the paired Zalo account
- **Do not share or commit this session directory** — it grants full access to the Zalo account

To unpair and remove all stored credentials:

```bash
hermes zalo logout
```

To check pairing/bridge status:

```bash
hermes zalo status
```

---

## Capabilities

This is a Phase 1 integration: Zalo reuses Hermes's existing general-purpose tools (reminders, notes, document drafting/generation, AI image generation, web search) rather than shipping Zalo- or Vietnam-specific tools.

- **Outbound media** — the agent can send images, documents, audio, and video natively via the bridge; include `MEDIA:/absolute/path/to/file` in a response to attach a file.
- **Inbound media** — the bridge does not forward attachment files in v1. A media message the user sends arrives to the agent only as a short text description (e.g. "Received a photo message"), never as a downloadable file.
- **Rendering** — treat Zalo as plain-text only. The platform hint instructs the model to avoid markdown (no bold, headers, tables) and use `-` bullets for lists instead.
- **Replies/quotes** — the bridge has no reply-to/quote support in v1; messages send as plain new messages.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **QR code expires before scanning** | QR codes are time-limited. Run `hermes zalo setup` again. |
| **Login declined on phone** | You (or someone with the phone) tapped "decline" on the login prompt. Run `hermes zalo setup` again and approve it. |
| **Bridge won't start / "Node.js not installed"** | Install Node.js 18+ and make sure it's on PATH. On macOS launchd services, run `hermes gateway install` again to re-snapshot PATH. |
| **Bot goes offline unexpectedly** | Check whether Zalo Web or Zalo Desktop was opened with the same account — only one web-listener session is allowed at a time. |
| **Account temporarily locked** | This is a known risk of unofficial automation. Wait it out, use a secondary account going forward, and avoid bulk/spam-like behavior. |
| **@mention not triggering a group response** | Confirm `~/.hermes/platforms/zalo/session/own_id.txt` exists (run `hermes zalo status`); if missing, the adapter recovers it automatically on the next successful bridge connection. As a fallback, set `ZALO_MENTION_NAME` to the bot's display name. |
| **Messages not being received at all** | Check `hermes zalo status` for the configured owner and opened groups. DMs only work from `platforms.zalo.extra.owner_id`; a group only works once it's opened via `!moquyenchat` or the sender is in `group_allow_from`. |

---

## Security

:::warning
**Set `platforms.zalo.extra.owner_id`** before going live — with no owner configured, DMs are blocked for everyone (including you) and `!moquyenchat`/`!dongquyenchat`/`!promptcapnhat` are unusable. Groups default to closed until explicitly opened. See [Access Control & Chat Permission Commands](#access-control--chat-permission-commands).
:::

- The `~/.hermes/platforms/zalo/session` directory contains full session credentials — protect it like a password
- Set file permissions: `chmod 700 ~/.hermes/platforms/zalo/session`
- Use a **dedicated Zalo account** for the bot to isolate ban/lock risk from your personal account
- If you suspect compromise, run `hermes zalo logout` to revoke the session, then re-pair with a fresh account if needed
