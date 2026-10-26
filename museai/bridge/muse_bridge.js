/**
 * Muse.ai In-Browser RPC Bridge
 * Injected into the muse.ai web application context.
 * 
 * Bypasses UI DOM keyboard simulation and directly interacts with the
 * internal React component / composer context and state dispatcher.
 */

(function () {
  // Allow re-initialization if script updated
  window.__museBridgeInitialized = true;

  console.log("[MuseBridge] Initializing internal RPC bridge...");

  const bridge = {
    // Check if the chat interface is loaded and ready
    isReady() {
      const textarea = document.querySelector('textarea, [data-hatch-composer-root]');
      return !!textarea;
    },

    // Extract current assistant turn (all text bubbles and media after the last user bubble)
    // Convert a rendered Muse bubble back to markdown so lists / bold / code keep their layout.
    toMarkdown(root) {
      const SKIP = new Set(['SVG', 'BUTTON', 'STYLE', 'SCRIPT', 'IMG', 'VIDEO']);
      const inline = (n) => Array.from(n.childNodes).map(walk).join('');
      const list = (n, depth) => {
        const ordered = n.tagName === 'OL';
        let k = 0;
        return Array.from(n.children).filter(c => c.tagName === 'LI').map(li => {
          k++;
          const pad = '  '.repeat(depth);
          let own = '', nested = '';
          Array.from(li.childNodes).forEach(c => {
            if (c.nodeType === 1 && (c.tagName === 'UL' || c.tagName === 'OL')) nested += '\n' + list(c, depth + 1);
            else own += walk(c);
          });
          return pad + (ordered ? k + '. ' : '- ') + own.trim().replace(/\n{2,}/g, '\n') + nested;
        }).join('\n');
      };
      const walk = (n) => {
        if (n.nodeType === 3) return n.nodeValue.replace(/\s+/g, ' ');
        if (n.nodeType !== 1 || SKIP.has(n.tagName.toUpperCase())) return '';
        const t = n.tagName.toUpperCase();
        switch (t) {
          case 'STRONG': case 'B': { const x = inline(n).trim(); return x ? '**' + x + '**' : ''; }
          case 'EM': case 'I': { const x = inline(n).trim(); return x ? '*' + x + '*' : ''; }
          case 'CODE': return n.closest('pre') ? n.textContent : '`' + n.textContent + '`';
          case 'PRE': return '\n\n```\n' + n.textContent.replace(/\n$/, '') + '\n```\n\n';
          case 'BR': return '\n';
          case 'A': { const x = inline(n).trim(); const h = n.getAttribute('href'); return h && x ? '[' + x + '](' + h + ')' : x; }
          case 'UL': case 'OL': return '\n\n' + list(n, 0) + '\n\n';
          case 'H1': case 'H2': case 'H3': case 'H4': case 'H5': case 'H6':
            return '\n\n' + '#'.repeat(+t[1]) + ' ' + inline(n).trim() + '\n\n';
          case 'BLOCKQUOTE': return '\n\n' + inline(n).trim().split('\n').map(l => '> ' + l).join('\n') + '\n\n';
          case 'HR': return '\n\n---\n\n';
          case 'TABLE': {
            const rows = Array.from(n.querySelectorAll('tr')).map(tr =>
              '| ' + Array.from(tr.children).map(c => c.innerText.trim().replace(/\|/g, '\\|').replace(/\n/g, ' ')).join(' | ') + ' |');
            if (rows.length > 1) {
              const cols = (rows[0].match(/\|/g) || []).length - 1;
              rows.splice(1, 0, '|' + ' --- |'.repeat(cols));
            }
            return '\n\n' + rows.join('\n') + '\n\n';
          }
          case 'P': case 'DIV': case 'SECTION': case 'ARTICLE': {
            const x = inline(n);
            return /^\s*$/.test(x) ? '' : '\n\n' + x.trim() + '\n\n';
          }
          default: return inline(n);
        }
      };
      return walk(root).replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
    },

    // After opening a thread, wait until its history has rendered (bubble count stable) before sending.
    async waitForHistory(maxMs = 15000) {
      const t0 = Date.now(); let last = -1, same = 0;
      while (Date.now() - t0 < maxMs) {
        const n = document.querySelectorAll('.hatch-chat-groupable-bubble').length;
        if (n > 0 && n === last) { if (++same >= 4) return n; } else same = 0;
        last = n;
        await new Promise(r => setTimeout(r, 400));
      }
      return last;
    },

    _bubbleKey(b) {
      const im = b.querySelector('img');
      return (b.innerText || '').slice(0, 200) + '|' + (im ? im.src : '');
    },

    extractCurrentTurn() {
      const bubbles = Array.from(document.querySelectorAll('.hatch-chat-groupable-bubble'));
      if (bubbles.length === 0) return { content: '', media: [] };

      let lastUserIdx = -1;
      for (let i = bubbles.length - 1; i >= 0; i--) {
        if (bubbles[i].classList.contains('bg-chat-user-bubble') || bubbles[i].className.includes('bg-chat-user-bubble')) {
          lastUserIdx = i;
          break;
        }
      }

      // Muse virtualises the chat list: with a long reply the user bubble can scroll out of the DOM.
      // Then fall back to "every bubble that was not there before we sent the prompt".
      let asstBubbles;
      if (lastUserIdx === -1) {
        const base = window.__museBase;
        if (!base) return { content: '', media: [] };
        asstBubbles = bubbles.filter(b => !base.has(this._bubbleKey(b)));
      } else {
        asstBubbles = bubbles.slice(lastUserIdx + 1);
      }
      const textParts = [];
      const media = [];

      asstBubbles.forEach(b => {
        // Video card / wrapper
        if (b.getAttribute('data-hatch-video-wrapper') === 'true' || !!b.querySelector('video')) {
          const video = b.querySelector('video');
          const blobUrl = b.getAttribute('data-hatch-video-src') || video?.src;
          if (blobUrl) {
            media.push({ type: 'video', url: blobUrl });
          }
          return;
        }

        // Generated image
        const imgs = Array.from(b.querySelectorAll('img')).filter(im =>
          im.src && !im.src.includes('avatar') && !im.src.includes('icon') &&
          !(im.naturalWidth && im.naturalWidth < 64));
        if (imgs.length) {
          imgs.forEach(im => { if (!media.some(m => m.url === im.src)) media.push({ type: 'image', url: im.src }); });
          return;
        }

        // Text bubble
        let txt = '';
        try { txt = this.toMarkdown(b); } catch (e) { txt = ''; }
        if (!txt) txt = b.innerText.trim();
        if (txt && txt !== 'Message') {
          textParts.push(txt);
        }
      });

      return {
        content: textParts.join('\n\n'),
        media: media
      };
    },

    // Get full turn-by-turn conversation history
    getHistory() {
      const bubbles = Array.from(document.querySelectorAll('.hatch-chat-groupable-bubble'));
      const userIndices = [];
      bubbles.forEach((b, i) => {
        if (b.classList.contains('bg-chat-user-bubble') || b.className.includes('bg-chat-user-bubble')) {
          userIndices.push(i);
        }
      });

      const turns = [];
      for (let t = 0; t < userIndices.length; t++) {
        const uIdx = userIndices[t];
        const nextUIdx = t + 1 < userIndices.length ? userIndices[t + 1] : bubbles.length;
        
        const userPrompt = bubbles[uIdx].innerText.replace(/^You:\s*/i, '').trim();
        const asstBubbles = bubbles.slice(uIdx + 1, nextUIdx);
        
        const textParts = [];
        const media = [];
        asstBubbles.forEach(b => {
          if (b.getAttribute('data-hatch-video-wrapper') === 'true' || !!b.querySelector('video')) {
            const video = b.querySelector('video');
            const blobUrl = b.getAttribute('data-hatch-video-src') || video?.src;
            if (blobUrl) media.push({ type: 'video', url: blobUrl });
          } else if (b.querySelector("img:not([src*='avatar']):not([src*='icon'])")) {
            media.push({ type: 'image', url: b.querySelector('img').src });
          } else {
            const txt = b.innerText.trim();
            if (txt && txt !== 'Message') textParts.push(txt);
          }
        });

        turns.push({
          userPrompt,
          assistantText: textParts.join('\n\n'),
          media
        });
      }
      return turns;
    },

    // Get list of all conversation threads from the sidebar
    getThreads() {
      const rows = document.querySelectorAll('[class*="group/nav-row"]');
      const threads = [];
      rows.forEach((r, idx) => {
        const titleEl = r.querySelector("p span, p, span[title]");
        const title = titleEl ? (titleEl.getAttribute("title") || titleEl.innerText.trim()) : r.innerText.trim();
        const timeEl = r.querySelector(".text-caption-1");
        const time = timeEl ? timeEl.innerText.trim() : "";
        if (title) {
          threads.push({
            id: "thread_" + idx,
            index: idx,
            title: title,
            time: time,
            isCurrent: r.getAttribute("aria-current") === "page" || r.className.includes("secondary-elevated") || r.className.includes("selected")
          });
        }
      });
      return threads;
    },

    // Switch to a thread by index, thread_id, or title
    async switchThread(target) {
      const rows = Array.from(document.querySelectorAll('[class*="group/nav-row"]'));
      let targetRow = null;
      if (typeof target === 'number') {
        targetRow = rows[target];
      } else if (typeof target === 'string') {
        if (target.startsWith('thread_')) {
          const idx = parseInt(target.replace('thread_', ''), 10);
          targetRow = rows[idx];
        } else {
          targetRow = rows.find(r => r.innerText.toLowerCase().includes(target.toLowerCase()));
        }
      }

      if (!targetRow) {
        throw new Error(`Thread '${target}' not found in sidebar (available: 0..${rows.length - 1})`);
      }

      targetRow.click();
      await new Promise(r => setTimeout(r, 1200));
      return {
        ok: true,
        currentUrl: window.location.href,
        threads: this.getThreads()
      };
    },

    // Create a new side chat thread
    async createNewThread() {
      const btn = document.querySelector('button[aria-label="New side chat"], button[aria-label="New chat"]');
      if (btn) {
        btn.click();
        await new Promise(r => setTimeout(r, 1200));
        return { ok: true, currentUrl: window.location.href, threads: this.getThreads() };
      }
      window.location.href = 'https://muse.ai/thread/new';
      await new Promise(r => setTimeout(r, 1500));
      return { ok: true, currentUrl: window.location.href, threads: this.getThreads() };
    },

    // Send a prompt directly via React composer state & button trigger.
    // Verifies the message really landed in the chat (retries up to 3x) so a silently dropped send is never waited on.
    async sendPrompt(text, options = {}) {
      const snip = text.replace(/\s+/g, ' ').trim().slice(0, 40);
      const countSnip = () => {
        const hay = (document.body.innerText || '').replace(/\s+/g, ' ');
        let n = 0, i = -1;
        while ((i = hay.indexOf(snip, i + 1)) !== -1) n++;
        return n;
      };
      const before = countSnip();
      window.__museBase = new Set(Array.from(document.querySelectorAll('.hatch-chat-groupable-bubble')).map(b => this._bubbleKey(b)));
      const sleep = (ms) => new Promise(r => setTimeout(r, ms));

      for (let attempt = 1; attempt <= 3; attempt++) {
        let textarea = null;
        for (let i = 0; i < 50; i++) {
          textarea = document.querySelector('textarea');
          if (textarea) break;
          await sleep(200);
        }
        if (!textarea) {
          throw new Error("Không tìm thấy ô nhập tin, hãy gửi lại.");
        }

        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        textarea.focus();
        setter.call(textarea, text);
        textarea.dispatchEvent(new Event('input', { bubbles: true }));

        let sendBtn = null;
        for (let i = 0; i < 25; i++) {
          sendBtn = document.querySelector('button[aria-label="Send"]');
          if (sendBtn && !sendBtn.disabled) break;
          await sleep(200);
        }
        if (!sendBtn) {
          if (attempt < 3) { await sleep(1500); continue; }
          throw new Error("Send button not found or remained disabled in composer.");
        }

        const key = Object.keys(sendBtn).find(k => k.startsWith('__reactProps'));
        if (attempt === 1 && key && sendBtn[key] && typeof sendBtn[key].onClick === 'function') {
          sendBtn[key].onClick({ stopPropagation: () => {}, preventDefault: () => {} });
        } else {
          sendBtn.click();
        }

        // Confirm: message shows up in the chat, or Muse started generating.
        for (let i = 0; i < 20; i++) {
          await sleep(300);
          const composer = document.querySelector('[data-hatch-composer-root]') || textarea.closest('form');
          const generating = composer ? !!composer.querySelector('button[aria-label="Stop"], button[aria-label="Cancel"]') : false;
          if (generating || countSnip() > before) return { ok: true, prompt: text, attempt };
        }
        console.log("[MuseBridge] send not confirmed, retry", attempt);
      }
      throw new Error("Server không nhận được tin nhắn (đã thử gửi 3 lần). Hãy gửi lại.");
    },

    // Access internal Hatch Zustand store directly from React Fiber
    getStore() {
      if (window.__hatchZustandStore) return window.__hatchZustandStore;
      const el = document.querySelector('textarea') || document.body;
      const fiberKey = Object.keys(el).find(k => k.startsWith('__reactFiber'));
      let fiber = el[fiberKey];
      while (fiber) {
        if (fiber.dependencies && fiber.dependencies.firstContext) {
          let ctx = fiber.dependencies.firstContext;
          while (ctx) {
            if (ctx.memoizedValue && typeof ctx.memoizedValue.getState === 'function') {
              const st = ctx.memoizedValue.getState();
              if (st && st.chat) {
                window.__hatchZustandStore = ctx.memoizedValue;
                return ctx.memoizedValue;
              }
            }
            ctx = ctx.next;
          }
        }
        fiber = fiber.return;
      }
      return null;
    },

    // Wait for the assistant response to complete (including media generation)
    async waitForCompletion(options = {}) {
      const timeoutMs = options.timeoutMs || 180000; // Allow 3 mins for video generation
      const pollIntervalMs = options.pollIntervalMs || 500;
      const startTime = Date.now();

      let lastSignature = '';
      let stableCount = 0;
      let textOnlyStableCount = 0;
      let hasStarted = false;
      const store = this.getStore();

      while (Date.now() - startTime < timeoutMs) {
        await new Promise(r => setTimeout(r, pollIntervalMs));

        if (!hasStarted && Date.now() - startTime > 90000) {
          throw new Error("Server không phản hồi tin nhắn này sau 90 giây. Hãy gửi lại.");
        }

        const composer = document.querySelector('[data-hatch-composer-root]') || document.querySelector('textarea')?.closest('form');
        const isGeneratingDom = composer ? !!composer.querySelector('button[aria-label="Stop"], button[aria-label="Cancel"]') : false;

        // Check Zustand store if available
        let storeIsStreaming = false;
        let storeIsExpecting = false;
        if (store) {
          try {
            const chatState = store.getState().chat;
            storeIsStreaming = !!chatState.isStreaming;
            storeIsExpecting = !!chatState.isExpectingBotResponse;
          } catch(e) {}
        }

        const isActivelyGenerating = isGeneratingDom || storeIsStreaming || storeIsExpecting;

        const turnData = this.extractCurrentTurn();

        // Check if any media placeholder or spinner is running in the current turn
        const bubbles = Array.from(document.querySelectorAll('.hatch-chat-groupable-bubble'));
        let lastUserIdx = -1;
        for (let i = bubbles.length - 1; i >= 0; i--) {
          if (bubbles[i].classList.contains('bg-chat-user-bubble') || bubbles[i].className.includes('bg-chat-user-bubble')) {
            lastUserIdx = i;
            break;
          }
        }
        const asstBubbles = lastUserIdx !== -1 ? bubbles.slice(lastUserIdx + 1) : (window.__museBase ? bubbles.filter(b => !window.__museBase.has(this._bubbleKey(b))) : []);
        const hasMediaSpinner = asstBubbles.some(b => 
          !!b.querySelector('[data-testid="chat-video-placeholder"], [data-testid*="attachment-presentation-video"]:not(:has(video)), svg[class*="animate-spin"], [role="progressbar"]')
        );

        if (isActivelyGenerating || turnData.content || turnData.media.length > 0) {
          hasStarted = true;
        }

        const promptMedia = options.prompt && /video|tvc|clip|quay|phim|mp4|ảnh|anh|hình|hinh|picture|photo|image|draw|paint|vẽ|ve/i.test(options.prompt);
        // The bot itself says it is generating/sending media (the raw prompt may be just "Hướng A").
        const botPromises = /đang\s+(tạo|vẽ|chạy|render|generate|gen|xử lý|làm|dựng)|xong\s+(mình|em|tôi)|sẽ\s+(gửi|giao|trả)|rồi giao|generating|will send/i.test(turnData.content || '');
        const isMediaExpected = !!(promptMedia || botPromises);
        const currentSignature = (turnData.content || '') + turnData.media.map(m => m.url).join(',');

        if (hasStarted && (turnData.content || turnData.media.length > 0)) {
          const mediaReady = !isMediaExpected || turnData.media.length > 0;

          // If Zustand confirms bot response is complete, no spinner
          if (!isActivelyGenerating && !hasMediaSpinner) {
            if (mediaReady) {
              // images land one by one: wait until the set of media stays unchanged for ~3 s
              if (currentSignature !== lastSignature) stableCount = 0;
              stableCount++;
              if (stableCount >= (turnData.media.length > 0 ? 6 : 2)) {
                const finalTurn = this.extractCurrentTurn();
                return {
                  status: 'completed',
                  content: finalTurn.content || turnData.content,
                  media: finalTurn.media.length > 0 ? finalTurn.media : turnData.media,
                  durationMs: Date.now() - startTime
                };
              }
            } else {
              // Media was expected but not present.
              const contentLower = (turnData.content || '').toLowerCase();
              const isExplicitError = /lỗi 503|503|tạm ngưng|không render được|chưa tạo được video|không khả dụng|hệ thống tạo video đang bận|lỗi kỹ thuật|không thể tạo/i.test(contentLower);

              if (isExplicitError) {
                // If bot responded with an explicit error or 503, exit early after 3s
                if (currentSignature === lastSignature) {
                  textOnlyStableCount++;
                  if (textOnlyStableCount >= 6) {
                    return {
                      status: 'failed_refusal',
                      content: turnData.content,
                      media: turnData.media,
                      durationMs: Date.now() - startTime
                    };
                  }
                } else {
                  textOnlyStableCount = 0;
                }
              } else {
                // Media is expected, no error text shown (e.g. video rendering is finalizing)
                // Wait up to ~45 seconds (90 polls * 500ms) after text stabilizes
                if (currentSignature === lastSignature) {
                  textOnlyStableCount++;
                  // Bot says it is still generating -> wait much longer (up to ~4 min) for the media to land.
                  const promisesMedia = /đang\s+(tạo|vẽ|chạy|render|generate|gen|xử lý|làm|dựng)|xong\s+(mình|em|tôi)|sẽ\s+(gửi|giao|trả)|rồi giao|generating|will send/i.test(contentLower);
                  if (textOnlyStableCount >= (promisesMedia ? 480 : 90)) {
                    const finalTurn = this.extractCurrentTurn();
                    return {
                      status: 'completed_no_media',
                      content: finalTurn.content || turnData.content,
                      media: finalTurn.media.length > 0 ? finalTurn.media : turnData.media,
                      durationMs: Date.now() - startTime
                    };
                  }
                } else {
                  textOnlyStableCount = 0;
                }
              }
            }
          } else {
            stableCount = 0;
            textOnlyStableCount = 0;
          }
          lastSignature = currentSignature;
        }
      }

      const finalTurn = this.extractCurrentTurn();
      if (finalTurn.content || finalTurn.media.length > 0) {
        return {
          status: 'timeout_partial',
          content: finalTurn.content,
          media: finalTurn.media,
          durationMs: Date.now() - startTime
        };
      }

      throw new Error(`Timeout after ${timeoutMs}ms waiting for response`);
    }
  };

  window.__muse = bridge;
  console.log("[MuseBridge] Ready. Accessible at window.__muse");
})();
