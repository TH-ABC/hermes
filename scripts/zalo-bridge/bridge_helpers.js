// Pure, dependency-free helpers for the Zalo bridge.
//
// These mirror the numeric values of zca-js's real ThreadType enum
// (User = 0, Group = 1) without importing zca-js, so this module has zero
// dependencies and can be unit-tested with plain object literals.

export const THREAD_TYPE_USER = 0;
export const THREAD_TYPE_GROUP = 1;

const CHAT_ID_PATTERN = /^(u|g):(.+)$/;

export function formatChatId(threadId, threadType) {
  if (threadId === undefined || threadId === null || threadId === '') {
    throw new Error('formatChatId: threadId is required');
  }
  const prefix = threadType === THREAD_TYPE_GROUP ? 'g' : 'u';
  return `${prefix}:${threadId}`;
}

export function parseChatId(chatId) {
  if (typeof chatId !== 'string') {
    throw new Error('parseChatId: chat_id must be a string');
  }
  const match = CHAT_ID_PATTERN.exec(chatId);
  if (!match) {
    throw new Error(`parseChatId: invalid chat_id "${chatId}", expected "u:<id>" or "g:<id>"`);
  }
  const [, prefix, threadId] = match;
  const isGroup = prefix === 'g';
  return {
    threadId,
    threadType: isGroup ? THREAD_TYPE_GROUP : THREAD_TYPE_USER,
    isGroup,
  };
}

// Converts a raw zca-js Message (UserMessage | GroupMessage) into the flat
// JSON event shape the Python-side adapter consumes via GET /messages.
//
// `data.content` is `string | TAttachmentContent | TOtherContent` in zca-js
// -- only plain string content (regular chat text) is surfaced as `text`;
// media/attachment messages get an empty `text` and a descriptive
// `content_type` from `data.msgType` instead.
export function messageToEvent(message) {
  const data = (message && message.data) || {};
  const isGroup = message && message.type === THREAD_TYPE_GROUP;
  const mentions = Array.isArray(data.mentions)
    ? data.mentions.map((m) => ({ uid: m.uid, pos: m.pos, len: m.len }))
    : [];

  let text = '';
  if (typeof data.content === 'string') {
    text = data.content;
  } else if (data.content && typeof data.content === 'object') {
    text = data.content.description || data.content.caption || data.content.title || data.content.text || '';
  }

  let attachmentUrl = null;
  if (data.content && typeof data.content === 'object') {
    attachmentUrl = data.content.href || data.content.hdUrl || data.content.url || data.content.thumb || null;
  }

  return {
    chat_id: formatChatId(message.threadId, message.type),
    is_group: Boolean(isGroup),
    message_id: data.msgId !== undefined ? String(data.msgId) : null,
    text: text,
    content_type: data.msgType || 'unknown',
    attachment_url: attachmentUrl,
    raw_content: data.content,
    sender_id: data.uidFrom !== undefined ? String(data.uidFrom) : null,
    sender_name: data.dName || null,
    timestamp: data.ts !== undefined ? Number(data.ts) : null,
    is_self: Boolean(message.isSelf),
    mentions,
  };
}
