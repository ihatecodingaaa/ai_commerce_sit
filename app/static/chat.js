// Support chat, embedded directly in the /support page (not a floating
// widget) so a page navigation can't abort an in-flight reply mid-request.
//
// Conversation state lives server-side per logged-in customer (see
// app/chatbot/agent.py). To keep that in-memory history from accumulating
// on a memory-tight host, this page WIPES the customer's conversation on
// every load/refresh: each visit starts fresh and the server frees whatever
// the previous conversation held. (This replaces the older behavior that
// persisted history across navigation to resume an in-flight reply --
// freeing server memory on refresh is preferred here.)
(function () {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const log = document.getElementById('chat-log');
  const suggestions = document.getElementById('chat-suggestions');
  if (!form || !input || !log) return;
  const sendBtn = form.querySelector('button');

  const GREETING = "Hi! I'm the Atelier concierge. Ask me about your orders, account, or the collection.";

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

  function setBusy(busy) {
    input.disabled = busy;
    if (sendBtn) sendBtn.disabled = busy;
    if (suggestions) {
      suggestions.querySelectorAll('.chip-btn').forEach((btn) => { btn.disabled = busy; });
    }
    if (!busy) input.focus();
  }

  async function sendMessage(message) {
    appendMessage(message, 'user');
    hideSuggestions();
    input.value = '';
    setBusy(true);
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
      // The fetch failed (e.g. this tab lost its network mid-request).
      typingEl.remove();
      appendMessage("Connection interrupted -- please try sending that again.", 'bot');
    } finally {
      setBusy(false);
    }
  }

  // On every page load/refresh, clear this customer's server-side
  // conversation so stale history doesn't pile up in memory, then show the
  // greeting fresh. The greeting is a client-side fixture, never stored.
  (async function resetAndGreet() {
    try {
      await fetch('/api/chat/reset', { method: 'POST' });
    } catch (err) {
      // If reset fails, stale history simply lingers until the next load --
      // nothing to render here.
    }
    appendMessage(GREETING, 'bot');
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
