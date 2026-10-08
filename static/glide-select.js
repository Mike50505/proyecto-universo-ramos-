(() => {
  const nativeSelects = [...document.querySelectorAll('select:not([multiple]):not([size])')];
  const selectStyles = document.createElement('style');
  selectStyles.textContent = '.glide-native-select{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}';
  document.head.append(selectStyles);

  nativeSelects.forEach((select, selectNumber) => {
    if (select.dataset.glideReady) return;
    select.dataset.glideReady = 'true';
    select.classList.add('glide-native-select');
    const options = [...select.options];
    const selectedIndex = () => options.findIndex(option => option.value === select.value);
    const field = select.closest('.field');
    const label = (field?.querySelector('label')?.textContent || select.getAttribute('aria-label') || 'Seleccionar opción').trim();
    const root = document.createElement('div');
    root.className = 'glide-select';
    root.dataset.size = 'md';
    root.dataset.disabled = select.disabled ? '' : 'false';
    const trigger = document.createElement('button');
    trigger.className = 'glide-select__trigger';
    trigger.id = `glide-select-trigger-${selectNumber}`;
    trigger.type = 'button';
    trigger.setAttribute('role', 'combobox');
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-label', label);
    if (field?.querySelector('label[for="' + select.id + '"]')) {
      field.querySelector('label[for="' + select.id + '"]').htmlFor = trigger.id;
    }
    const listId = `glide-select-list-${selectNumber}`;
    trigger.setAttribute('aria-controls', listId);
    trigger.disabled = select.disabled;
    const selectedLabel = document.createElement('span');
    selectedLabel.className = 'glide-select__label';
    const chevron = document.createElement('span');
    chevron.className = 'glide-select__chevron';
    chevron.setAttribute('aria-hidden', 'true');
    chevron.textContent = '⌄';
    trigger.append(selectedLabel, chevron);

    const menu = document.createElement('div');
    menu.className = 'glide-select__menu';
    menu.dataset.state = 'closed';
    menu.dataset.side = 'bottom';
    menu.dataset.align = 'left';
    const list = document.createElement('div');
    list.id = listId;
    list.className = 'glide-select__list';
    list.setAttribute('role', 'listbox');
    list.setAttribute('aria-label', label);
    const pill = document.createElement('span');
    pill.className = 'glide-select__pill';
    pill.setAttribute('aria-hidden', 'true');
    list.append(pill);
    const rows = options.map((option, index) => {
      const row = document.createElement('div');
      row.className = 'glide-select__option';
      row.id = `${listId}-option-${index}`;
      row.dataset.index = String(index);
      row.setAttribute('role', 'option');
      row.setAttribute('aria-selected', 'false');
      row.setAttribute('aria-disabled', String(option.disabled));
      const name = document.createElement('span');
      name.className = 'glide-select__name';
      name.textContent = option.text;
      const check = document.createElement('span');
      check.className = 'glide-select__check';
      check.setAttribute('aria-hidden', 'true');
      check.textContent = '✓';
      row.append(name, check);
      list.append(row);
      return row;
    });
    menu.append(list);
    root.append(trigger, menu);
    select.insertAdjacentElement('afterend', root);

    let open = false;
    let active = null;
    let closeTimer;
    let typeahead = '';
    let typeaheadTimer;
    const step = 38;
    const update = () => {
      const index = selectedIndex();
      selectedLabel.textContent = index >= 0 ? options[index].text : 'Seleccionar…';
      selectedLabel.toggleAttribute('data-empty', index < 0);
      rows.forEach((row, rowIndex) => {
        const isSelected = rowIndex === index;
        row.setAttribute('aria-selected', String(isSelected));
        row.querySelector('.glide-select__check').toggleAttribute('data-on', isSelected);
      });
      root.dataset.disabled = select.disabled ? '' : 'false';
      trigger.disabled = select.disabled;
    };
    const setActive = index => {
      active = index;
      list.toggleAttribute('data-live', index !== null);
      if (index === null) {
        trigger.removeAttribute('aria-activedescendant');
        pill.style.opacity = '0';
        return;
      }
      if (!rows[index]) return;
      trigger.setAttribute('aria-activedescendant', rows[index].id);
      pill.style.transform = `translateY(${index * step}px)`;
      pill.style.opacity = '1';
      rows[index].scrollIntoView({ block: 'nearest' });
    };
    const close = immediate => {
      if (!open) return;
      open = false;
      trigger.setAttribute('aria-expanded', 'false');
      menu.dataset.state = 'closed';
      setActive(null);
      clearTimeout(closeTimer);
      if (immediate) menu.remove();
      else closeTimer = window.setTimeout(() => menu.remove(), 130);
    };
    const choose = index => {
      const option = options[index];
      if (!option || option.disabled) return;
      const changed = select.value !== option.value;
      select.value = option.value;
      update();
      close(true);
      if (changed) select.dispatchEvent(new Event('change', { bubbles: true }));
      trigger.focus({ preventScroll: true });
    };
    const openMenu = viaKeyboard => {
      if (select.disabled || open || !rows.length) return;
      clearTimeout(closeTimer);
      open = true;
      menu.dataset.state = 'closed';
      root.append(menu);
      trigger.setAttribute('aria-expanded', 'true');
      const rect = root.getBoundingClientRect();
      const estimated = Math.min(options.length * step + 10, 300);
      const side = rect.bottom + estimated + 6 > window.innerHeight && rect.top > estimated ? 'top' : 'bottom';
      menu.dataset.side = side;
      menu.dataset.align = rect.right + 190 > window.innerWidth ? 'right' : 'left';
      const index = selectedIndex();
      setActive(index >= 0 ? index : viaKeyboard ? 0 : null);
      requestAnimationFrame(() => {
        menu.dataset.state = 'open';
      });
    };
    const onKeyDown = event => {
      const key = event.key;
      if (!open) {
        if (['Enter', ' ', 'ArrowDown', 'ArrowUp'].includes(key)) {
          event.preventDefault();
          openMenu(true);
        }
        return;
      }
      if (key === 'Escape' || key === 'Tab') {
        if (key === 'Escape') event.preventDefault();
        close(true);
      } else if (key === 'ArrowDown' || key === 'ArrowUp') {
        event.preventDefault();
        move((active ?? Math.max(0, selectedIndex())) + (key === 'ArrowDown' ? 1 : -1));
      } else if (key === 'Home' || key === 'End') {
        event.preventDefault();
        move(key === 'Home' ? 0 : rows.length - 1);
      } else if (key === 'Enter' || key === ' ') {
        event.preventDefault();
        if (active !== null) choose(active);
      } else if (key.length === 1 && !event.metaKey && !event.ctrlKey && !event.altKey) {
        typeahead += key.toLocaleLowerCase();
        clearTimeout(typeaheadTimer);
        typeaheadTimer = window.setTimeout(() => { typeahead = ''; }, 600);
        const start = active ?? Math.max(0, selectedIndex());
        for (let offset = 1; offset <= options.length; offset += 1) {
          const index = (start + offset) % options.length;
          if (!options[index].disabled && options[index].text.toLocaleLowerCase().startsWith(typeahead)) {
            event.preventDefault();
            setActive(index);
            break;
          }
        }
      }
    };
    const move = index => {
      const direction = index >= (active ?? selectedIndex()) ? 1 : -1;
      let next = Math.max(0, Math.min(rows.length - 1, index));
      while (options[next]?.disabled && next >= 0 && next < rows.length) next += direction;
      if (next >= 0 && next < rows.length) setActive(next);
    };
    trigger.addEventListener('click', () => open ? close(false) : openMenu(false));
    trigger.addEventListener('keydown', onKeyDown);
    list.addEventListener('pointerover', event => {
      const row = event.target.closest('.glide-select__option');
      if (row && !options[Number(row.dataset.index)].disabled) setActive(Number(row.dataset.index));
    });
    list.addEventListener('click', event => {
      const row = event.target.closest('.glide-select__option');
      if (row) choose(Number(row.dataset.index));
    });
    document.addEventListener('pointerdown', event => {
      if (open && !root.contains(event.target)) close(false);
    }, true);
    select.addEventListener('change', update);
    select.form?.addEventListener('reset', () => window.setTimeout(update, 0));
    update();
  });
})();
