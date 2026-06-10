// @ts-check
(function () {
  /** @type {any} */
  const vscode = acquireVsCodeApi();

  const messageList = /** @type {HTMLElement} */ (document.getElementById('message-list'));
  const messageInput = /** @type {HTMLTextAreaElement} */ (document.getElementById('message-input'));
  const sendBtn = /** @type {HTMLButtonElement} */ (document.getElementById('send-btn'));

  /** @param {string} text @returns {string} */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /** @param {string} text @returns {string} */
  function renderMarkdown(text) {
    // Escape HTML first to prevent XSS
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Fenced code blocks with optional lang:filepath
    html = html.replace(/```([\w.:/-]*)\n([\s\S]*?)```/g, (_, info, code) => {
      const colonIdx = info.indexOf(':');
      const lang = colonIdx >= 0 ? info.slice(0, colonIdx) || 'text' : info || 'text';
      const filePath = colonIdx >= 0 ? info.slice(colonIdx + 1).trim() : '';
      const blockId = 'code-' + Math.random().toString(36).slice(2, 10);
      const applyBtn = filePath
        ? '<button class="apply-btn" data-block-id="' + blockId + '" data-file="' + escapeHtml(filePath) + '">Apply to ' + escapeHtml(filePath) + '</button>'
        : '<button class="apply-btn" data-block-id="' + blockId + '">Apply to Editor</button>';
      return '<div class="code-block-wrapper">'
        + '<div class="code-block-header"><span class="code-lang">' + escapeHtml(lang) + '</span>' + applyBtn + '</div>'
        + '<pre><code id="' + blockId + '">' + code + '</code></pre>'
        + '</div>';
    });

    // Inline code
    html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    // Bold
    html = html.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    // Italic
    html = html.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    // Restore newlines inside pre
    html = html.replace(/<pre>([\s\S]*?)<\/pre>/g, (m) => m.replace(/<br>/g, '\n'));

    return html;
  }

  /** @param {{ role: string; content: string; isError?: boolean }} message */
  function addMessage(message) {
    const div = document.createElement('div');
    const classes = ['message', message.role];
    if (message.isError) classes.push('error');
    div.className = classes.join(' ');
    div.innerHTML = renderMarkdown(message.content);
    messageList.appendChild(div);
    messageList.scrollTop = messageList.scrollHeight;
  }

  /** @param {{ toolName: string; duration: number; result: string }} toolResult @returns {HTMLElement} */
  function createToolResultCard(toolResult) {
    const card = document.createElement('div');
    card.className = 'tool-result-card';

    const header = document.createElement('div');
    header.className = 'tool-result-header';
    header.innerHTML =
      '<span class="tool-name">' + escapeHtml(toolResult.toolName) + '</span>' +
      '<span class="tool-duration">' + toolResult.duration + 'ms</span>';
    header.addEventListener('click', () => card.classList.toggle('expanded'));

    const body = document.createElement('div');
    body.className = 'tool-result-body';
    body.textContent = toolResult.result;

    card.appendChild(header);
    card.appendChild(body);
    return card;
  }

  /** @param {boolean} loading */
  function setLoading(loading) {
    const existing = document.querySelector('.loading-indicator');
    if (loading && !existing) {
      const div = document.createElement('div');
      div.className = 'message assistant loading-indicator';
      div.innerHTML = '<span class="loading-dots">Thinking</span><div class="progress-detail">준비 중...</div>';
      messageList.appendChild(div);
      messageList.scrollTop = messageList.scrollHeight;
    } else if (!loading && existing) {
      existing.remove();
    }
  }

  let isGenerating = false;

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

  sendBtn.addEventListener('click', sendMessage);

  messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isGenerating) sendMessage();
    }
  });

  messageList.addEventListener('click', (e) => {
    const btn = /** @type {HTMLElement} */ (e.target)?.closest?.('.apply-btn');
    if (!btn) return;
    const blockId = /** @type {HTMLElement} */ (btn).dataset.blockId;
    const filePath = /** @type {HTMLElement} */ (btn).dataset.file || null;
    const codeEl = blockId ? document.getElementById(blockId) : null;
    if (!codeEl) return;
    vscode.postMessage({ type: 'applyCode', code: codeEl.textContent, filePath: filePath });
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
        if (lastMsg) lastMsg.appendChild(createToolResultCard(message.result));
        break;
      }
      case 'updateProgress': {
        const progressDetail = document.querySelector('.loading-indicator .progress-detail');
        if (progressDetail) {
          let progressText = message.text;
          if (progressText.includes("Thinking")) progressText = "💡 " + progressText;
          else if (progressText.includes("Running tool")) progressText = "🛠️ " + progressText;
          else if (progressText.includes("finished")) progressText = "✅ " + progressText;
          
          progressDetail.textContent = progressText;
        }
        break;
      }
    }
  });

  vscode.postMessage({ type: 'ready' });
})();
