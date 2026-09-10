// Support chat, embedded directly in the /support page (not a floating
// widget) so a page navigation can't abort an in-flight reply mid-request
// -- staying on this page while the bot is "thinking" is a normal,
// uninterrupted fetch instead of something a navigation could cut off.
//
// Conversation state lives server-side per logged-in customer (see
// app/chatbot/agent.py), and the backend keeps working on a reply even
// after the browser that sent it navigates away or the tab is closed --
// handle_chat_message() finishes and appends the assistant's reply to
// that in-memory history regardless of whether anyone is still listening
// on the original connection. So when this page loads (including much
// later, in a new tab), if the *last* stored message is from the
// customer with no assistant reply after it, a reply is still being
// generated -- this polls until it shows up instead of leaving the
// conversation looking stuck.
(function () {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const log = document.getElementById('chat-log');
  const suggestions = document.getElementById('chat-suggestions');
  if (!form || !input || !log) return;
  const sendBtn = form.querySelector('button');

  const GREETING = "Hi! I'm Shopilot, ShopLite's support assistant. Ask me about your orders, account, or products.";
  const POLL_INTERVAL_MS = 3000;
  const POLL_MAX_ATTEMPTS = 90; // ~4.5 minutes, comfortably past the app's own Ollama timeout

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
    if (!busy) input.focus();
  }

  async function fetchHistory() {
    const res = await fetch('/api/chat/history');
    if (!res.ok) return null;
    const data = await res.json();
    return data.messages || [];
  }

  function renderNewMessages(messages) {
    hideSuggestions();
    messages.forEach((m) => appendMessage(m.content, m.role === 'user' ? 'user' : 'bot'));
  }

  async function pollForPendingReply(knownCount) {
    const typingEl = showTyping();
    setBusy(true);
    for (let attempt = 0; attempt < POLL_MAX_ATTEMPTS; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      let messages;
      try {
        messages = await fetchHistory();
      } catch (err) {
        continue; // transient network hiccup -- keep polling
      }
      if (messages && messages.length > knownCount) {
        typingEl.remove();
        renderNewMessages(messages.slice(knownCount));
        setBusy(false);
        return;
      }
    }
    typingEl.remove();
    appendMessage("Still waiting on a reply from earlier -- it may not have finished. Feel free to send a new message.", 'bot');
    setBusy(false);
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
      // The fetch itself failed (e.g. this tab lost its network mid-request).
      // The server-side handler is unaffected and keeps working -- reloading
      // this page will pick up the reply via the pending-reply poll above
      // once it's done, so this message doesn't claim the reply was lost.
      typingEl.remove();
      appendMessage("Connection interrupted -- Shopilot is likely still working on it. Reload this page in a bit to see the reply.", 'bot');
    } finally {
      setBusy(false);
    }
  }

  (async function loadHistory() {
    // The greeting always renders first, every load -- it's a client-side
    // fixture, not part of the stored conversation, so without this it
    // would only ever show up before the very first message was ever
    // sent and then disappear for good on every later visit/refresh.
    appendMessage(GREETING, 'bot');
    try {
      const messages = await fetchHistory();
      if (messages === null || messages.length === 0) return;
      renderNewMessages(messages);
      const last = messages[messages.length - 1];
      if (last && last.role === 'user') {
        pollForPendingReply(messages.length);
      }
    } catch (err) {
      // Greeting is already shown; nothing else to do.
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
