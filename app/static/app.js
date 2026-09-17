// Shared site chrome: toasts, responsive navigation, profile dropdown, and theme toggle.
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
    toggle.addEventListener('click', () => {
      const open = !links.classList.contains('open');
      links.classList.toggle('open', open);
      toggle.setAttribute('aria-expanded', String(open));
    });
    links.querySelectorAll('a').forEach((a) => a.addEventListener('click', () => {
      links.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }));
  }

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

  const MOON_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>';
  const SUN_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>';

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
        if (icon) icon.innerHTML = dark ? SUN_ICON : MOON_ICON;
        if (label) label.textContent = dark ? 'Light mode' : 'Dark mode';
        btn.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
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
