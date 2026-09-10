// Support chat, embedded directly in the /support page (not a floating
// widget) so a page navigation can't abort an in-flight reply mid-request
// -- staying on this page while the bot is "thinking" is a normal,
// uninterrupted fetch instead of something a navigation could cut off.
(function () {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const log = document.getElementById('chat-log');
  const suggestions = document.getElementById('chat-suggestions');
  if (!form || !input || !log) return;
  const sendBtn = form.querySelector('button');

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

  function hideSuggestions() {
    if (suggestions) suggestions.hidden = true;
  }

  async function sendMessage(message) {
    appendMessage(message, 'user');
    hideSuggestions();
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
      appendMessage('Error contacting support assistant. Please stay on this page and try again.', 'bot');
    } finally {
      input.disabled = false;
      if (sendBtn) sendBtn.disabled = false;
      input.focus();
    }
  }

  // Conversation state lives server-side per logged-in customer (see
  // app/chatbot/agent.py) -- reload it so returning to this page shows the
  // same conversation instead of starting over.
  (async function loadHistory() {
    try {
      const res = await fetch('/api/chat/history');
      if (!res.ok) return;
      const data = await res.json();
      const messages = data.messages || [];
      if (messages.length === 0) {
        appendMessage("Hi! I'm Shopilot, ShopLite's support assistant. Ask me about your orders, account, or products.", 'bot');
        return;
      }
      hideSuggestions();
      messages.forEach((m) => appendMessage(m.content, m.role === 'user' ? 'user' : 'bot'));
    } catch (err) {
      appendMessage("Hi! I'm Shopilot, ShopLite's support assistant. Ask me about your orders, account, or products.", 'bot');
    }
  })();

  if (suggestions) {
    suggestions.querySelectorAll('.chip-btn').forEach((btn) => {
      btn.addEventListener('click', () => sendMessage(btn.textContent));
    });
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    sendMessage(message);
  });
})();
