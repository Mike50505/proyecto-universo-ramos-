(() => {
  const element = document.querySelector('[data-text-type]');
  if (!element) return;

  const phrase = element.dataset.textType.split('|')[0]?.trim();
  if (!phrase) return;
  element.classList.add('login-title-typed');
  element.textContent = '';

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    element.textContent = phrase;
    return;
  }

  let characterIndex = 0;
  let timer;

  const tick = () => {
    characterIndex = Math.min(phrase.length, characterIndex + 1);
    element.textContent = phrase.slice(0, characterIndex);
    if (characterIndex === phrase.length) {
      cursor.remove();
      return;
    }
    timer = window.setTimeout(tick, 48);
  };

  timer = window.setTimeout(tick, 400);
  window.addEventListener('pagehide', () => window.clearTimeout(timer), { once: true });
})();
