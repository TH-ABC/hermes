import express from 'express';
import { Zalo, LoginQRCallbackEventType, CloseReason } from 'zca-js';
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'fs';
import path from 'path';
import { createHash } from 'crypto';
import { fileURLToPath } from 'url';

import { messageToEvent, parseChatId } from './bridge_helpers.js';

// --- CLI args -----------------------------------------------------------
const args = process.argv.slice(2);
function getArg(name, defaultVal) {
  const idx = args.indexOf(`--${name}`);
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : defaultVal;
}

const PORT = parseInt(getArg('port', '3000'), 10);
const SESSION_DIR = getArg('session', path.join(process.env.HOME || '~', '.hermes', 'zalo', 'session'));
const MODE = getArg('mode', null);
const CREDS_PATH = path.join(SESSION_DIR, 'zalo_creds.json');
const QR_PATH = path.join(SESSION_DIR, 'qr.png');
const SEND_TIMEOUT_MS = parseInt(process.env.ZALO_SEND_TIMEOUT_MS || '60000', 10);
const MAX_QUEUE_SIZE = 100;
// Version: 1.1.0 - Support rich media and fast async notification
if (MODE !== 'pair' && MODE !== 'resume') {
  console.error('ZALO_BRIDGE_FATAL: --mode must be "pair" or "resume"');
  process.exit(1);
}

mkdirSync(SESSION_DIR, { recursive: true });

// Self-hash of this script file. Reported in /health so the Python gateway
// can detect a running bridge that predates the current bridge.js on disk
// and restart it instead of silently reusing stale code.
let SCRIPT_HASH = '';
try {
  SCRIPT_HASH = createHash('sha256')
    .update(readFileSync(fileURLToPath(import.meta.url)))
    .digest('hex')
    .slice(0, 16);
} catch {}

function readImageSize(filePath) {
  try {
    const buf = readFileSync(filePath);
    if (buf.length < 24) return { width: 1024, height: 1024 };
    // PNG
    if (buf.toString('ascii', 1, 4) === 'PNG') {
      return { width: buf.readUInt32BE(16) || 1024, height: buf.readUInt32BE(20) || 1024 };
    }
    // GIF
    if (buf.toString('ascii', 0, 3) === 'GIF') {
      return { width: buf.readUInt16LE(6) || 1024, height: buf.readUInt16LE(8) || 1024 };
    }
    // WEBP
    if (buf.toString('ascii', 0, 4) === 'RIFF' && buf.toString('ascii', 8, 12) === 'WEBP') {
      if (buf.toString('ascii', 12, 16) === 'VP8X' && buf.length >= 30) {
        return { width: 1 + buf.readUIntLE(24, 3), height: 1 + buf.readUIntLE(27, 3) };
      }
      if (buf.toString('ascii', 12, 16) === 'VP8L' && buf.length >= 25) {
        const b1 = buf[21], b2 = buf[22], b3 = buf[23], b4 = buf[24];
        return {
          width: 1 + (((b2 & 0x3f) << 8) | b1),
          height: 1 + (((b4 & 0xf) << 10) | (b3 << 2) | ((b2 & 0xc0) >> 6)),
        };
      }
      if (buf.toString('ascii', 12, 16) === 'VP8 ' && buf.length >= 30) {
        return { width: (buf.readUInt16LE(26) & 0x3fff) || 1024, height: (buf.readUInt16LE(28) & 0x3fff) || 1024 };
      }
    }
    // JPEG
    if (buf[0] === 0xff && buf[1] === 0xd8) {
      let offset = 2;
      while (offset < buf.length - 8) {
        if (buf[offset] !== 0xff) break;
        const marker = buf[offset + 1];
        if (marker === 0xc0 || marker === 0xc2) {
          const height = buf.readUInt16BE(offset + 5);
          const width = buf.readUInt16BE(offset + 7);
          return { width: width || 1024, height: height || 1024 };
        }
        const len = buf.readUInt16BE(offset + 2);
        offset += 2 + len;
      }
    }
  } catch {}
  return { width: 1024, height: 1024 };
}

async function imageMetadataGetter(filePath) {
  try {
    const stat = statSync(filePath);
    const dims = readImageSize(filePath);
    return {
      width: dims.width || 1024,
      height: dims.height || 1024,
      size: stat.size,
      totalSize: stat.size,
    };
  } catch {
    return { width: 1024, height: 1024, size: 0, totalSize: 0 };
  }
}

// --- Runtime state --------------------------------------------------------
let api = null;
let connectionState = 'disconnected';
let ownId = null;
const messageQueue = [];

function enqueueMessage(event) {
  messageQueue.push(event);
  if (messageQueue.length > MAX_QUEUE_SIZE) {
    messageQueue.shift();
  }
}

// Serialise all api.sendMessage()/sendTypingEvent() calls across concurrent
// HTTP handlers so a single zca-js connection never has overlapping sends
// (mirrors scripts/whatsapp-bridge/bridge.js's _sendQueue, which exists to
// avoid cross-chat contamination from racing sends on one socket).
let _sendQueue = Promise.resolve();
function enqueueSend(fn) {
  const task = _sendQueue.then(() => fn(), () => fn());
  _sendQueue = task.catch(() => {});
  return task;
}

function withTimeout(promise, timeoutMs = SEND_TIMEOUT_MS) {
  let timer;
  const timeoutPromise = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`Timed out after ${timeoutMs / 1000}s`)), timeoutMs);
  });
  return Promise.race([promise, timeoutPromise]).finally(() => clearTimeout(timer));
}

function attachListener(apiInstance) {
  apiInstance.listener.on('connected', () => {
    connectionState = 'connected';
    console.log('Zalo listener: connected');
  });
  apiInstance.listener.on('closed', (code, reason) => {
    connectionState = 'disconnected';
    console.error(`Zalo listener: closed (code=${code} ${CloseReason[code] || ''}) ${reason || ''}`);
    setTimeout(() => {
      try {
        console.log('[Bridge] Auto-reconnecting Zalo listener...');
        apiInstance.listener.start();
      } catch (e) {
        console.error('[Bridge] Reconnect error:', e.message);
      }
    }, 3000);
  });
  apiInstance.listener.on('disconnected', (code, reason) => {
    connectionState = 'disconnected';
    console.error(`Zalo listener: disconnected (code=${code} ${CloseReason[code] || ''}) ${reason || ''}`);
    setTimeout(() => {
      try {
        console.log('[Bridge] Auto-reconnecting Zalo listener...');
        apiInstance.listener.start();
      } catch (e) {
        console.error('[Bridge] Reconnect error:', e.message);
      }
    }, 3000);
  });
  apiInstance.listener.on('error', (err) => {
    console.error(`Zalo listener: error ${err?.message || err}`);
  });
  apiInstance.listener.on('message', (message) => {
    // Never forward the bot's own outbound messages back to Python: this
    // bridge account is a normal group member (not a separate business
    // channel), so its own sent messages arrive back through the same
    // listener and would otherwise create an inbound echo loop.
    if (message.isSelf) return;
    try {
      enqueueMessage(messageToEvent(message));
    } catch (err) {
      console.error(`Failed to convert inbound message: ${err.message}`);
    }
  });
  apiInstance.listener.start();
}

// --- Pairing (QR login) ---------------------------------------------------
async function runPair() {
  const zalo = new Zalo({ logging: false, imageMetadataGetter });
  console.log('ZALO_PAIR_MODE_STARTED');

  let loggedIn;
  try {
    loggedIn = await zalo.loginQR({ qrPath: QR_PATH }, (event) => {
      switch (event.type) {
        case LoginQRCallbackEventType.QRCodeGenerated:
          event.actions
            .saveToFile(QR_PATH)
            .then(() => console.log(`QR_CODE_PATH:${QR_PATH}`))
            .catch((err) => console.error(`Failed to save QR image: ${err.message}`));
          break;
        case LoginQRCallbackEventType.QRCodeExpired:
          console.error('QR_CODE_EXPIRED');
          event.actions.retry();
          break;
        case LoginQRCallbackEventType.QRCodeScanned:
          console.log(`QR_CODE_SCANNED:${event.data?.display_name || ''}`);
          break;
        case LoginQRCallbackEventType.QRCodeDeclined:
          console.error('QR_CODE_DECLINED');
          event.actions.abort();
          break;
        case LoginQRCallbackEventType.GotLoginInfo:
          try {
            writeFileSync(
              CREDS_PATH,
              JSON.stringify(
                { imei: event.data.imei, cookie: event.data.cookie, userAgent: event.data.userAgent },
                null,
                2,
              ),
              { mode: 0o600 },
            );
          } catch (err) {
            console.error(`Failed to persist credentials: ${err.message}`);
          }
          break;
      }
    });
  } catch (err) {
    console.error(`PAIR_FAILED:${err?.message || err}`);
    process.exit(1);
    return;
  }

  console.log(`PAIRED:${loggedIn.getOwnId()}`);
  setTimeout(() => process.exit(0), 500);
}

// --- Resume (headless, no QR fallback) ------------------------------------
async function runResume() {
  if (!existsSync(CREDS_PATH)) {
    console.error(`RESUME_FAILED:no credentials at ${CREDS_PATH}. Run --mode pair first.`);
    process.exit(1);
    return;
  }

  let creds;
  try {
    creds = JSON.parse(readFileSync(CREDS_PATH, 'utf8'));
  } catch (err) {
    console.error(`RESUME_FAILED:invalid credentials file: ${err.message}`);
    process.exit(1);
    return;
  }

  const zalo = new Zalo({ logging: false, imageMetadataGetter });
  try {
    // Intentionally no QR fallback here: this process is headless (resume
    // mode). If the saved session is no longer valid, fail loudly so the
    // Python adapter surfaces a clear "re-pair required" error instead of
    // silently hanging on a QR code nobody can scan.
    api = await zalo.login(creds);
  } catch (err) {
    console.error(`RESUME_FAILED:${err?.message || err}`);
    process.exit(1);
    return;
  }

  attachListener(api);
  connectionState = 'connected';
  try {
    ownId = api.getOwnId();
  } catch (err) {
    console.error(`Failed to read own Zalo id: ${err.message}`);
  }
  startServer();
}

// --- HTTP server -----------------------------------------------------------
const app = express();
app.use(express.json({ limit: '25mb' }));

// Host-header validation — defends against DNS rebinding. The bridge binds
// loopback-only (127.0.0.1) but a victim browser on the same machine could
// be tricked into fetching from an attacker hostname that TTL-flips to
// 127.0.0.1. Reject any request whose Host header doesn't resolve to a
// loopback alias. See GHSA-ppp5-vxwm-4cf7.
const _ACCEPTED_HOST_VALUES = new Set(['localhost', '127.0.0.1', '[::1]', '::1']);
app.use((req, res, next) => {
  const raw = (req.headers.host || '').trim();
  if (!raw) {
    return res.status(400).json({ error: 'Missing Host header' });
  }
  const hostOnly = (raw.includes(':') ? raw.substring(0, raw.lastIndexOf(':')) : raw)
    .replace(/^\[|\]$/g, '')
    .toLowerCase();
  if (!_ACCEPTED_HOST_VALUES.has(hostOnly)) {
    return res.status(400).json({ error: 'Invalid Host header. Bridge accepts loopback hosts only.' });
  }
  next();
});

app.get('/health', (req, res) => {
  res.json({
    status: connectionState,
    queueLength: messageQueue.length,
    uptime: process.uptime(),
    scriptHash: SCRIPT_HASH,
    // The bot's own Zalo user id, once resumed/logged in. The Python adapter
    // caches this and uses it to detect "am I @mentioned in this group
    // message?" via GroupMessage.data.mentions[].uid, rather than fuzzy
    // name-text matching.
    ownId,
  });
});

app.get('/messages', (req, res) => {
  res.json(messageQueue.splice(0, messageQueue.length));
});

app.get('/groups', async (req, res) => {
  if (!api) {
    return res.status(503).json({ error: 'Not connected to Zalo' });
  }
  try {
    const allGroups = await api.getAllGroups();
    const groupIds = Object.keys(allGroups?.gridVerMap || {});
    if (groupIds.length === 0) {
      return res.json({ groups: [] });
    }
    const info = await api.getGroupInfo(groupIds);

    // Thu thập tất cả User ID để lấy tên thật
    const allMemberUids = new Set();
    for (const gid of groupIds) {
      const g = info?.gridInfoMap?.[gid];
      if (g && g.memVerList) {
        for (const m of g.memVerList) {
          const rawUid = m.split('_')[0];
          if (rawUid) allMemberUids.add(rawUid);
        }
      }
    }

    let memberProfiles = {};
    try {
      if (allMemberUids.size > 0) {
        const uidsArray = Array.from(allMemberUids);
        // zca-js supports batching getGroupMembersInfo
        const memResp = await api.getGroupMembersInfo(uidsArray);
        memberProfiles = memResp?.profiles || {};
      }
    } catch (e) {
      console.error('getGroupMembersInfo error:', e.message);
    }

    const result = [];
    for (const gid of groupIds) {
      const g = info?.gridInfoMap?.[gid];
      if (g) {
        const membersList = [];
        for (const m of (g.memVerList || [])) {
          const rawUid = m.split('_')[0];
          const prof = memberProfiles[rawUid] || {};
          let realName = prof.displayName || prof.zaloName;
          if (!realName) {
            if (rawUid === '7725451581835120119') realName = 'Sếp Hoàng (CEO)';
            else if (rawUid === ownId) realName = 'Hermes Bot';
            else realName = `Thành Viên ${rawUid.slice(-4)}`;
          }

          membersList.push({
            uid: rawUid,
            name: realName,
            avatar: prof.avatar || null,
          });
        }

        result.push({
          id: `g:${gid}`,
          name: g.name || `Nhóm ${gid}`,
          totalMembers: g.totalMember || membersList.length,
          avatar: g.avt || null,
          members: membersList
        });
      }
    }
    res.json({ groups: result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/friends', async (req, res) => {
  if (!api) {
    return res.status(503).json({ error: 'Not connected to Zalo' });
  }
  try {
    const friends = await api.getAllFriends();
    res.json({ friends: friends || [] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/send', async (req, res) => {
  if (!api) {
    return res.status(503).json({ error: 'Not connected to Zalo' });
  }
  const { chat_id: chatId, text } = req.body || {};
  if (!chatId || !text) {
    return res.status(400).json({ error: 'chat_id and text are required' });
  }
  let parsed;
  try {
    parsed = parseChatId(chatId);
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
  try {
    const result = await enqueueSend(() =>
      withTimeout(api.sendMessage({ msg: text }, parsed.threadId, parsed.threadType)),
    );
    res.json({ success: true, message_id: result?.message?.msgId ?? null });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/send-media', async (req, res) => {
  if (!api) {
    return res.status(503).json({ error: 'Not connected to Zalo' });
  }
  const { chat_id: chatId, file_path: filePath, caption } = req.body || {};
  if (!chatId || !filePath) {
    return res.status(400).json({ error: 'chat_id and file_path are required' });
  }
  if (!existsSync(filePath)) {
    return res.status(404).json({ error: `file_path does not exist: ${filePath}` });
  }
  let parsed;
  try {
    parsed = parseChatId(chatId);
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
  try {
    const result = await enqueueSend(() =>
      withTimeout(
        api.sendMessage({ msg: caption || '', attachments: filePath }, parsed.threadId, parsed.threadType),
      ),
    );
    res.json({ success: true, message_id: result?.message?.msgId ?? null });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/send-link', async (req, res) => {
  if (!api) {
    return res.status(503).json({ error: 'Not connected to Zalo' });
  }
  const { chat_id: chatId, link, msg } = req.body || {};
  if (!chatId || !link) {
    return res.status(400).json({ error: 'chat_id and link are required' });
  }
  let parsed;
  try {
    parsed = parseChatId(chatId);
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
  try {
    const result = await enqueueSend(() =>
      withTimeout(
        api.sendLink({ link, msg: msg || '' }, parsed.threadId, parsed.threadType),
      ),
    );
    res.json({ success: true, message_id: result?.msgId ?? null });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/typing', async (req, res) => {
  if (!api) {
    return res.status(503).json({ error: 'Not connected to Zalo' });
  }
  const { chat_id: chatId } = req.body || {};
  if (!chatId) {
    return res.status(400).json({ error: 'chat_id is required' });
  }
  let parsed;
  try {
    parsed = parseChatId(chatId);
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
  try {
    await enqueueSend(() => withTimeout(api.sendTypingEvent(parsed.threadId, parsed.threadType)));
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/create-group', async (req, res) => {
  if (!api) {
    return res.status(503).json({ error: 'Not connected to Zalo' });
  }
  const { name, members } = req.body || {};
  if (!name || !members || !Array.isArray(members) || members.length === 0) {
    return res.status(400).json({ error: 'name and non-empty members array are required' });
  }
  try {
    const cleanMembers = members
      .map(m => String(m).replace(/^u:/, '').split('_')[0])
      .filter(m => m && m !== ownId);

    const result = await enqueueSend(() =>
      withTimeout(api.createGroup({ name, members: cleanMembers }))
    );
    res.json({ success: true, group: result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/add-group-members', async (req, res) => {
  if (!api) {
    return res.status(503).json({ error: 'Not connected to Zalo' });
  }
  const { group_id: groupId, members } = req.body || {};
  if (!groupId || !members || !Array.isArray(members)) {
    return res.status(400).json({ error: 'group_id and members are required' });
  }
  let cleanId = String(groupId).trim();
  if (!cleanId.startsWith('g:') && !cleanId.startsWith('u:')) {
    cleanId = 'g:' + cleanId;
  }
  let parsed;
  try {
    parsed = parseChatId(cleanId);
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
  try {
    const cleanMembers = members
      .map(m => String(m).replace(/^u:/, '').split('_')[0])
      .filter(m => m && m !== ownId);

    const result = await enqueueSend(() =>
      withTimeout(api.addUserToGroup(cleanMembers, parsed.threadId))
    );
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/group-link', async (req, res) => {
  if (!api) {
    return res.status(503).json({ error: 'Not connected to Zalo' });
  }
  const groupId = req.query.group_id;
  if (!groupId) {
    return res.status(400).json({ error: 'group_id query param is required' });
  }
  let cleanId = String(groupId).trim();
  if (!cleanId.startsWith('g:') && !cleanId.startsWith('u:')) {
    cleanId = 'g:' + cleanId;
  }
  let parsed;
  try {
    parsed = parseChatId(cleanId);
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
  try {
    let linkDetail;
    try {
      linkDetail = await enqueueSend(() => withTimeout(api.getGroupLinkDetail(parsed.threadId)));
    } catch (e) {
      // If disabled, enable it
      linkDetail = await enqueueSend(() => withTimeout(api.enableGroupLink(parsed.threadId)));
    }
    res.json({ success: true, link: linkDetail });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/invite-to-group', async (req, res) => {
  if (!api) {
    return res.status(503).json({ error: 'Not connected to Zalo' });
  }
  const { group_id: groupId, user_id: userId } = req.body || {};
  if (!groupId || !userId) {
    return res.status(400).json({ error: 'group_id and user_id are required' });
  }
  let cleanId = String(groupId).trim();
  if (!cleanId.startsWith('g:') && !cleanId.startsWith('u:')) {
    cleanId = 'g:' + cleanId;
  }
  let parsed;
  try {
    parsed = parseChatId(cleanId);
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
  try {
    const cleanUid = String(userId).replace(/^u:/, '').split('_')[0];
    const result = await enqueueSend(() => withTimeout(api.inviteUserToGroups(cleanUid, parsed.threadId)));
    res.json({ success: true, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/leave-group', async (req, res) => {
  if (!api) {
    return res.status(503).json({ error: 'Not connected to Zalo' });
  }
  const { group_id: groupId, silent } = req.body || {};
  if (!groupId) {
    return res.status(400).json({ error: 'group_id is required' });
  }
  let cleanId = String(groupId).trim();
  if (!cleanId.startsWith('g:') && !cleanId.startsWith('u:')) {
    cleanId = 'g:' + cleanId;
  }
  let parsed;
  try {
    parsed = parseChatId(cleanId);
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
  try {
    console.log(`[Bridge] Leaving group ${parsed.threadId} (silent=${!!silent})...`);
    const result = await enqueueSend(() => withTimeout(api.leaveGroup(parsed.threadId, !!silent)));
    res.json({ success: true, result });
  } catch (err) {
    console.error(`[Bridge] Error leaving group ${groupId}:`, err.message);
    res.status(500).json({ success: false, error: err.message });
  }
});

function startServer() {
  app.listen(PORT, '127.0.0.1', () => {
    console.log(`Zalo bridge listening on 127.0.0.1:${PORT}`);
    console.log(`Session stored in: ${SESSION_DIR}`);
  });
}

// --- Entry point -------------------------------------------------------
if (MODE === 'pair') {
  runPair();
} else {
  runResume();
}
