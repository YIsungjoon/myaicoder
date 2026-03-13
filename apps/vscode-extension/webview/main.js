// @ts-check
(function () {
  /** @type {any} */
  const vscode = acquireVsCodeApi();

  const messageList = document.getElementById('message-list');
  const messageInput = document.getElementById('message-input');
  const sendBtn = document.getElementById('send-btn');

  /**
   * Basic markdown rendering.
   * Handles code blocks, inline code, bold, italic, and line breaks.
   * @param {string} text
   * @returns {string}
   */
  function renderMarkdown(text) {
    // Escape HTML first
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Code blocks (```lang\ncode\n```)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
      return `<pre><code class="language-${lang}">${code}</code></pre>`;
    });

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Line breaks (outside of pre blocks)
    html = html.replace(/\n/g, '<br>');

    // Fix: remove <br> inside <pre> blocks
    html = html.replace(/<pre>([\s\S]*?)<\/pre>/g, (match) => {
      return match.replace(/<br>/g, '\n');
    });

    return html;
  }

  /**
   * Add a message to the chat.
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
   * Create a collapsible tool result card.
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
   * @param {string} text
   * @returns {string}
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Show or hide loading indicator.
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

  function sendMessage() {
    const text = messageInput.value.trim();
    if (!text) return;

    vscode.postMessage({ type: 'sendMessage', text: text });
    messageInput.value = '';
    messageInput.style.height = 'auto';
  }

  sendBtn.addEventListener('click', sendMessage);

  messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Extension -> Webview messages
  window.addEventListener('message', (event) => {
    const message = event.data;
    switch (message.type) {
      case 'addMessage':
        addMessage(message.message);
        break;
      case 'setLoading':
        setLoading(message.loading);
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

  vscode.postMessage({ type: 'ready' });
})();
