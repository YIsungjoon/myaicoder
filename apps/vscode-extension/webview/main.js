// @ts-check
import { marked } from 'marked';
import DOMPurify from 'dompurify';

(function () {
  /** @type {any} */
  const vscode = acquireVsCodeApi();

  const messageList = /** @type {HTMLElement} */ (document.getElementById('message-list'));
  const messageInput = /** @type {HTMLTextAreaElement} */ (document.getElementById('message-input'));
  const sendBtn = /** @type {HTMLButtonElement} */ (document.getElementById('send-btn'));

  /**
   * @param {string} str
   * @returns {string}
   */
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // Custom renderer for code blocks — adds Apply button and preserves "lang:filepath" format.
  marked.use({
    renderer: {
      /**
       * @param {string} code
       * @param {string | undefined} infostring
       * @returns {string}
       */
      code(code, infostring) {
        const info = infostring || '';
        const colonIdx = info.indexOf(':');
        const langLabel = escapeHtml(colonIdx >= 0 ? info.slice(0, colonIdx) || 'text' : info || 'text');
        const filePath = colonIdx >= 0 ? info.slice(colonIdx + 1).trim() : '';
        const safeFilePath = escapeHtml(filePath);

        const blockId = 'code-' + Math.random().toString(36).substr(2, 9);
        const applyBtn = filePath
          ? `<button class="apply-btn" data-block-id="${blockId}" data-file="${safeFilePath}">Apply to ${safeFilePath}</button>`
          : `<button class="apply-btn" data-block-id="${blockId}">Apply to Editor</button>`;

        return (
          `<div class="code-block-wrapper">` +
          `<div class="code-block-header"><span class="code-lang">${langLabel}</span>${applyBtn}</div>` +
          `<pre><code id="${blockId}" class="language-${langLabel}">${escapeHtml(code)}</code></pre>` +
          `</div>`
        );
      },
    },
  });

  const PURIFY_CONFIG = /** @type {import('dompurify').Config} */ ({
    ADD_ATTR: ['data-block-id', 'data-file'],
    ALLOWED_TAGS: [
      'div', 'span', 'p', 'br', 'strong', 'em', 'code', 'pre', 'button',
      'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'blockquote', 'a', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'hr', 'del', 'ins',
    ],
    ALLOWED_ATTR: ['class', 'id', 'href', 'data-block-id', 'data-file'],
  });

  /**
   * Render markdown to sanitized HTML.
   * @param {string} text
   * @returns {string}
   */
  function renderMarkdown(text) {
    const rawHtml = /** @type {string} */ (marked.parse(text));
    return DOMPurify.sanitize(rawHtml, PURIFY_CONFIG);
  }

  /**
   * @param {{ role: string; content: string; isError?: boolean; toolResults?: any[] }} message
   */
  function addMessage(message) {
    const div = document.createElement('div');
    const classes = ['message', message.role];
    if (message.isError) {
      classes.push('error');
    }
    div.className = classes.join(' ');
    div.innerHTML = renderMarkdown(message.content);

    if (message.toolResults) {
      message.toolResults.forEach((tr) => {
        div.appendChild(createToolResultCard(tr));
      });
    }

    messageList.appendChild(div);
    messageList.scrollTop = messageList.scrollHeight;
  }

  /**
   * @param {{ toolName: string; duration: number; result: string }} toolResult
   * @returns {HTMLElement}
   */
  function createToolResultCard(toolResult) {
    const card = document.createElement('div');
    card.className = 'tool-result-card';

    const header = document.createElement('div');
    header.className = 'tool-result-header';
    header.innerHTML =
      '<span class="tool-name">' + escapeHtml(toolResult.toolName) + '</span>' +
      '<span class="tool-duration">' + toolResult.duration + 'ms</span>';
    header.addEventListener('click', () => {
      card.classList.toggle('expanded');
    });

    const body = document.createElement('div');
    body.className = 'tool-result-body';
    body.textContent = toolResult.result;

    card.appendChild(header);
    card.appendChild(body);
    return card;
  }

  /**
   * @param {boolean} loading
   */
  function setLoading(loading) {
    const existing = document.querySelector('.loading-indicator');
    if (loading && !existing) {
      const div = document.createElement('div');
      div.className = 'message assistant loading-indicator';
      div.innerHTML = '<span class="loading-dots">Thinking</span>';
      messageList.appendChild(div);
      messageList.scrollTop = messageList.scrollHeight;
    } else if (!loading && existing) {
      existing.remove();
    }
  }

  let isGenerating = false;

  function sendMessage() {
    if (isGenerating) {
      vscode.postMessage({ type: 'cancelRequest' });
      return;
    }
    const text = messageInput.value.trim();
    if (!text) return;

    isGenerating = true;
    updateSendButton();

    vscode.postMessage({ type: 'sendMessage', text: text });
    messageInput.value = '';
    messageInput.style.height = 'auto';
  }

  function updateSendButton() {
    if (isGenerating) {
      sendBtn.textContent = 'Stop';
      sendBtn.classList.add('generating');
      messageInput.disabled = true;
    } else {
      sendBtn.textContent = 'Send';
      sendBtn.classList.remove('generating');
      messageInput.disabled = false;
      messageInput.focus();
    }
  }

  sendBtn.addEventListener('click', sendMessage);

  messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isGenerating) {
        sendMessage();
      }
    }
  });

  window.addEventListener('message', (event) => {
    const message = event.data;
    switch (message.type) {
      case 'addMessage':
        addMessage(message.message);
        break;
      case 'setLoading':
        setLoading(message.loading);
        isGenerating = message.loading;
        updateSendButton();
        break;
      case 'clearChat':
        messageList.innerHTML = '';
        break;
      case 'setInput':
        messageInput.value = message.text;
        messageInput.focus();
        break;
      case 'toolResult': {
        const lastMsg = messageList.querySelector('.message.assistant:last-child');
        if (lastMsg) {
          lastMsg.appendChild(createToolResultCard(message.result));
        }
        break;
      }
    }
  });

  messageList.addEventListener('click', (e) => {
    const btn = /** @type {HTMLElement} */ (e.target)?.closest?.('.apply-btn');
    if (!btn) return;

    const blockId = /** @type {HTMLElement} */ (btn).dataset.blockId;
    const filePath = /** @type {HTMLElement} */ (btn).dataset.file || null;
    const codeEl = blockId ? document.getElementById(blockId) : null;
    if (!codeEl) return;

    vscode.postMessage({
      type: 'applyCode',
      code: codeEl.textContent,
      filePath: filePath,
    });
  });

  vscode.postMessage({ type: 'ready' });
})();
