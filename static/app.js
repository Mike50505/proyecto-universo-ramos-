document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

const themeToggle = document.querySelector('.theme-toggle');
const themeColor = document.querySelector('meta[name="theme-color"]');
const applyTheme = theme => {
  document.documentElement.dataset.theme = theme;
  const dark = theme === 'dark';
  themeToggle?.setAttribute('aria-label', dark ? 'Activar modo claro' : 'Activar modo oscuro');
  themeToggle?.setAttribute('aria-pressed', String(dark));
  if (themeColor) themeColor.content = dark ? '#000000' : '#ffffff';
};

applyTheme(document.documentElement.dataset.theme || 'light');
themeToggle?.addEventListener('click', () => {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('universo-theme', next);
  applyTheme(next);
});
