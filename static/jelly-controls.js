(() => {
  const nav = document.querySelector('.nav nav');
  if (!nav) return;
  const links = [...nav.querySelectorAll('a[href]')];
  if (!links.length) return;
  const normalized = path => {
    const clean = path.replace(/^\/+|\/+$/g, '');
    return clean ? `/${clean}/` : '/';
  };
  const currentPath = normalized(window.location.pathname);
  let current = links.find(link => normalized(new URL(link.href, location.href).pathname) === currentPath);
  if (!current) {
    current = links
      .filter(link => normalized(new URL(link.href, location.href).pathname) !== '/')
      .filter(link => currentPath.startsWith(normalized(new URL(link.href, location.href).pathname)))
      .sort((a, b) => b.href.length - a.href.length)[0];
  }
  if (!current && currentPath !== '/login/') current = links.find(link => normalized(new URL(link.href, location.href).pathname) === '/');
  current?.setAttribute('aria-current', 'page');

  const keyFor = link => normalized(new URL(link.href, location.href).pathname);
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let popTarget = '';
  try {
    popTarget = sessionStorage.getItem('universo-jelly-nav-pop') || '';
    sessionStorage.removeItem('universo-jelly-nav-pop');
  } catch {}
  if (current && popTarget === keyFor(current) && !reduceMotion) {
    current.classList.add('jelly-nav-pop');
    window.setTimeout(() => current.classList.remove('jelly-nav-pop'), 190);
  }
  nav.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || !current || link === current || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    try { sessionStorage.setItem('universo-jelly-nav-pop', keyFor(link)); } catch {}
  });

  document.querySelectorAll('.button, button:not(.glide-select__trigger), .page-button').forEach(control => {
    control.addEventListener('pointerdown', () => control.classList.add('jelly-pressed'));
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(type => {
      control.addEventListener(type, () => control.classList.remove('jelly-pressed'));
    });
  });
})();
