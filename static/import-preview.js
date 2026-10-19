(() => {
  let saving = false;
  const initialize = () => {
    document.querySelectorAll('[data-preview-sample] button').forEach(button => { button.hidden = true; });
    document.querySelectorAll('[data-preview-sample] input[type="checkbox"]').forEach(checkbox => {
      checkbox.dataset.saved = String(checkbox.checked);
    });
    const all = document.querySelector('#all-pending');
    if (all) all.indeterminate = !all.checked && all.dataset.mixed === 'true';
  };
  initialize();
  const save = async form => {
    if (saving) return;
    const checkbox = form.querySelector('input[type="checkbox"]');
    const previous = checkbox.dataset.saved === 'true';
    const data = new FormData(form);
    const feedback = document.querySelector('[data-preview-feedback]');
    const content = document.querySelector('[data-preview-content]');
    const disabled = [];
    saving = true;
    content.setAttribute('aria-busy', 'true');
    content.querySelectorAll('input, button, select').forEach(control => {
      if (!control.disabled) { control.disabled = true; disabled.push(control); }
    });
    feedback.textContent = 'Guardando clasificación…';
    try {
      const response = await fetch(window.location.href, {
        method: 'POST', body: data, credentials: 'same-origin', redirect: 'error',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      const html = await response.text();
      if (!response.ok) throw new Error(response.status === 400 ? html : 'No se pudo guardar. Intente de nuevo.');
      const next = new DOMParser().parseFromString(html, 'text/html').querySelector('[data-preview-content]');
      if (!next) throw new Error('La sesión cambió. Recargue la página para continuar.');
      const scroll = { x: window.scrollX, y: window.scrollY };
      const horizontal = content.querySelector('.table-scroll')?.scrollLeft || 0;
      const focusId = checkbox.id;
      content.replaceWith(next);
      initialize();
      const table = next.querySelector('.table-scroll');
      if (table) table.scrollLeft = horizontal;
      document.getElementById(focusId)?.focus({ preventScroll: true });
      window.scrollTo({ left: scroll.x, top: scroll.y, behavior: 'instant' });
      feedback.textContent = 'Clasificación guardada. Se aplicará al confirmar la importación.';
    } catch (error) {
      checkbox.checked = previous;
      initialize();
      feedback.textContent = error.message || 'No se pudo guardar. Intente de nuevo.';
    } finally {
      saving = false;
      content.removeAttribute('aria-busy');
      disabled.forEach(control => { control.disabled = false; });
    }
  };
  document.addEventListener('change', event => {
    const form = event.target.closest('[data-preview-sample]');
    if (form && event.target.matches('input[type="checkbox"]')) save(form);
  });
  document.addEventListener('submit', event => {
    const form = event.target.closest('[data-preview-sample]');
    if (form) { event.preventDefault(); save(form); }
    else if (saving && event.target.closest('[data-preview-content]')) event.preventDefault();
  });
  document.addEventListener('click', event => {
    if (saving && event.target.closest('[data-preview-content] a')) event.preventDefault();
  });
  window.addEventListener('beforeunload', event => {
    if (saving) { event.preventDefault(); event.returnValue = ''; }
  });
})();
