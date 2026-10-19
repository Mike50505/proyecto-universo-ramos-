document.querySelectorAll('[data-preview-sample]').forEach(form => {
  const checkbox = form.querySelector('input[type="checkbox"]');
  const button = form.querySelector('button[type="submit"]');
  if (!checkbox || !button || typeof form.requestSubmit !== 'function') return;
  button.hidden = true;
  checkbox.addEventListener('change', () => {
    form.setAttribute('aria-busy', 'true');
    form.requestSubmit();
  });
});
