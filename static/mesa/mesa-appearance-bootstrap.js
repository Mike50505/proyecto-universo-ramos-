(() => {
  const themes = {classic:'light',pearl:'light',ivory:'light',sage:'light',slate:'dark',night:'dark'};
  let choice;
  try {
    const saved = localStorage.getItem('heiliang-color-mode');
    const previous = localStorage.getItem('mesa-theme') || localStorage.getItem('mesa-empaque-theme');
    choice = Object.hasOwn(themes,saved) ? saved : (previous === 'dark' || (!previous && matchMedia('(prefers-color-scheme: dark)').matches) ? 'night' : 'classic');
  } catch {
    choice = matchMedia('(prefers-color-scheme: dark)').matches ? 'night' : 'classic';
  }
  document.documentElement.dataset.palette = choice;
  document.documentElement.dataset.theme = themes[choice];
})();
