(function () {
  const toggle = document.getElementById('chat-toggle');
  const panel = document.getElementById('chat-panel');
  const closeBtn = document.getElementById('chat-close');
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const log = document.getElementById('chat-log');
  const sendBtn = form ? form.querySelector('button') : null;

  function appendMessage(text, cls) {
    const div = document.createElement('div');
    div.className = 'msg ' + cls;
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function showTyping() {
    const div = document.createElement('div');
    div.className = 'msg bot typing';
    div.innerHTML = '<span></span><span></span><span></span>';
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  // Conversation state lives server-side per logged-in customer (see
  // app/chatbot/agent.py) -- reload it here so the widget shows the same
  // conversation after a page navigation instead of starting over.
  async function loadHistory() {
    try {
      const res = await fetch('/api/chat/history');
      if (!res.ok) return;
      const data = await res.json();
      const messages = data.messages || [];
      if (messages.length === 0) {
        appendMessage("Hi! I'm Shopilot, ShopLite's support assistant. Ask me about your orders, account, or products.", 'bot');
        return;
      }
      messages.forEach((m) => appendMessage(m.content, m.role === 'user' ? 'user' : 'bot'));
    } catch (err) {
      appendMessage("Hi! I'm Shopilot, ShopLite's support assistant. Ask me about your orders, account, or products.", 'bot');
    }
  }
  const historyLoaded = loadHistory();

  function open() {
    panel.hidden = false;
    input.focus();
    log.scrollTop = log.scrollHeight;
  }
  toggle.addEventListener('click', () => { panel.hidden ? open() : (panel.hidden = true); });
  closeBtn.addEventListener('click', () => { panel.hidden = true; });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    await historyLoaded; // avoid racing the initial history render
    appendMessage(message, 'user');
    input.value = '';
    input.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
    const typingEl = showTyping();

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      const data = await res.json();
      typingEl.remove();
      appendMessage(res.ok ? data.reply : ('Error: ' + (data.error || 'unknown')), 'bot');
    } catch (err) {
      typingEl.remove();
      appendMessage('Error contacting support assistant.', 'bot');
    } finally {
      input.disabled = false;
      if (sendBtn) sendBtn.disabled = false;
      input.focus();
    }
  });
})();
