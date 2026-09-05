import test from 'node:test';
import assert from 'node:assert/strict';

import {
  THREAD_TYPE_GROUP,
  THREAD_TYPE_USER,
  formatChatId,
  messageToEvent,
  parseChatId,
} from './bridge_helpers.js';

test('formatChatId prefixes users with u: and groups with g:', () => {
  assert.equal(formatChatId('12345', THREAD_TYPE_USER), 'u:12345');
  assert.equal(formatChatId('67890', THREAD_TYPE_GROUP), 'g:67890');
});

test('formatChatId requires a threadId', () => {
  assert.throws(() => formatChatId('', THREAD_TYPE_USER));
  assert.throws(() => formatChatId(undefined, THREAD_TYPE_USER));
});

test('parseChatId is the inverse of formatChatId', () => {
  assert.deepEqual(parseChatId('u:12345'), {
    threadId: '12345',
    threadType: THREAD_TYPE_USER,
    isGroup: false,
  });
  assert.deepEqual(parseChatId('g:67890'), {
    threadId: '67890',
    threadType: THREAD_TYPE_GROUP,
    isGroup: true,
  });
});

test('parseChatId rejects malformed chat ids', () => {
  assert.throws(() => parseChatId('12345'));
  assert.throws(() => parseChatId('x:12345'));
  assert.throws(() => parseChatId(''));
  assert.throws(() => parseChatId(null));
});

test('messageToEvent converts a plain-text user message', () => {
  const message = {
    type: THREAD_TYPE_USER,
    threadId: '111',
    isSelf: false,
    data: {
      msgId: '999',
      msgType: 'webchat',
      content: 'hello there',
      uidFrom: '222',
      dName: 'Alice',
      ts: '1700000000000',
    },
  };
  assert.deepEqual(messageToEvent(message), {
    chat_id: 'u:111',
    is_group: false,
    message_id: '999',
    text: 'hello there',
    content_type: 'webchat',
    sender_id: '222',
    sender_name: 'Alice',
    timestamp: 1700000000000,
    is_self: false,
    mentions: [],
  });
});

test('messageToEvent surfaces mentions on group messages', () => {
  const message = {
    type: THREAD_TYPE_GROUP,
    threadId: '333',
    isSelf: false,
    data: {
      msgId: '1000',
      msgType: 'webchat',
      content: '@bot hi',
      uidFrom: '444',
      dName: 'Bob',
      ts: '1700000001000',
      mentions: [{ uid: '555', pos: 0, len: 4 }],
    },
  };
  const event = messageToEvent(message);
  assert.equal(event.is_group, true);
  assert.deepEqual(event.mentions, [{ uid: '555', pos: 0, len: 4 }]);
});

test('messageToEvent treats non-string content (attachments) as empty text', () => {
  const message = {
    type: THREAD_TYPE_USER,
    threadId: '111',
    isSelf: false,
    data: {
      msgId: '1001',
      msgType: 'chat.photo',
      content: { title: 'photo.jpg', href: 'https://example.com/photo.jpg' },
      uidFrom: '222',
      dName: 'Alice',
      ts: '1700000002000',
    },
  };
  const event = messageToEvent(message);
  assert.equal(event.text, '');
  assert.equal(event.content_type, 'chat.photo');
});

test('messageToEvent marks self-sent messages', () => {
  const message = {
    type: THREAD_TYPE_USER,
    threadId: '111',
    isSelf: true,
    data: { msgId: '1002', msgType: 'webchat', content: 'echo', uidFrom: '999', ts: '1700000003000' },
  };
  assert.equal(messageToEvent(message).is_self, true);
});
