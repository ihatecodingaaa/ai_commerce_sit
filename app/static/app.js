// Shared site chrome: toasts + mobile nav toggle + profile dropdown +
// dark mode toggle. No app/security logic here.
(function () {
  function ensureToastStack() {
    let stack = document.getElementById('toast-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.id = 'toast-stack';
      document.body.appendChild(stack);
    }
    return stack;
  }

  window.showToast = function (message, type) {
    const stack = ensureToastStack();
    const el = document.createElement('div');
    el.className = 'toast ' + (type === 'error' ? 'error' : 'success');
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => {
      el.classList.add('fade-out');
      setTimeout(() => el.remove(), 200);
    }, 3200);
  };

  const toggle = document.getElementById('nav-toggle');
  const links = document.getElementById('nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', () => links.classList.toggle('open'));
    links.querySelectorAll('a').forEach((a) => a.addEventListener('click', () => links.classList.remove('open')));
  }

  // Profile dropdown (nameplate top-right): Account, dark mode, log out.
  const profileMenu = document.getElementById('profile-menu');
  const profileTrigger = document.getElementById('profile-trigger');
  const profileDropdown = document.getElementById('profile-dropdown');
  function closeProfileDropdown() {
    if (!profileDropdown) return;
    profileDropdown.hidden = true;
    if (profileTrigger) profileTrigger.setAttribute('aria-expanded', 'false');
  }
  if (profileTrigger && profileDropdown) {
    profileTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const willOpen = profileDropdown.hidden;
      profileDropdown.hidden = !willOpen;
      profileTrigger.setAttribute('aria-expanded', String(willOpen));
    });
    document.addEventListener('click', (e) => {
      if (profileMenu && !profileMenu.contains(e.target)) closeProfileDropdown();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeProfileDropdown();
    });
  }

  // Dark mode: an explicit choice (stored in localStorage) always wins;
  // otherwise the page already follows prefers-color-scheme via CSS alone.
  // Two possible controls share the .theme-toggle-control class: a plain
  // icon button for logged-out visitors, and an icon+label row inside the
  // profile dropdown for logged-in ones -- both get kept in sync.
  function effectiveTheme() {
    const explicit = localStorage.getItem('theme');
    if (explicit === 'dark' || explicit === 'light') return explicit;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  const themeControls = document.querySelectorAll('.theme-toggle-control');
  if (themeControls.length) {
    const syncControls = () => {
      const dark = effectiveTheme() === 'dark';
      themeControls.forEach((btn) => {
        const icon = btn.querySelector('.theme-toggle-icon');
        const label = btn.querySelector('.theme-toggle-label');
        if (icon) icon.textContent = dark ? '☀️' : '🌙';
        if (label) label.textContent = dark ? 'Light mode' : 'Dark mode';
      });
    };
    syncControls();
    themeControls.forEach((btn) => {
      btn.addEventListener('click', () => {
        const next = effectiveTheme() === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        try { localStorage.setItem('theme', next); } catch (e) {}
        syncControls();
        closeProfileDropdown();
      });
    });
  }
})();
