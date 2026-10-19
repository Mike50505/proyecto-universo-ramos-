/* The same single palette choice as Heiliang, for plain HTML applications. */
(() => {
  'use strict';
  const root = document.documentElement;
  const modes = {
    classic:{theme:'light',label:'Claro · azul MESA',copy:'Azul MESA sobre superficies claras.'},
    pearl:{theme:'light',label:'Perla · gris suave',copy:'Grises suaves y azules discretos, con menos blanco brillante.'},
    ivory:{theme:'light',label:'Marfil · tonos cálidos',copy:'Fondos cálidos y acentos azul grisáceos.'},
    sage:{theme:'light',label:'Salvia · verde tenue',copy:'Verdes tenues y superficies suaves.'},
    slate:{theme:'dark',label:'Pizarra · oscuro suave',copy:'Azul grisáceo oscuro, sin fondo negro puro.'},
    night:{theme:'dark',label:'Oscuro · negro',copy:'El modo oscuro original de MESA.'},
  };
  const store = {get(key){try{return localStorage.getItem(key)}catch{return null}},set(key,value){try{localStorage.setItem(key,value)}catch{}}};
  const preference = matchMedia('(prefers-color-scheme: dark)');
  const read = () => {
    const saved = store.get('heiliang-color-mode');
    if (Object.hasOwn(modes,saved)) return saved;
    const previous = store.get('mesa-theme') || store.get('mesa-empaque-theme');
    return previous === 'dark' || (!previous && preference.matches) ? 'night' : 'classic';
  };
  const pick = () => Object.hasOwn(modes,root.dataset.palette) ? root.dataset.palette : 'classic';
  const panels = new Set();
  let syncing = false;
  function apply(key,persist=true) {
    if (!Object.hasOwn(modes,key)) return;
    root.dataset.palette = key;
    root.dataset.theme = modes[key].theme;
    if (persist) {store.set('heiliang-color-mode',key);store.set('mesa-theme',modes[key].theme)}
    syncing = true;
    for (const panel of panels) {
      if (!panel.isConnected) { panels.delete(panel); continue; }
      const select = panel.querySelector('select');
      if (select && select.value !== key) {select.value=key;select.dispatchEvent(new Event('change',{bubbles:true}))}
      panel.querySelector('[data-palette-copy]').textContent = modes[key].copy;
    }
    syncing = false;
    dispatchEvent(new Event('mesa-palette-change'));
  }
  function mount(host,index) {
    if (host.dataset.paletteMounted) return;
    host.dataset.paletteMounted='true';
    host.classList.add('mesa-appearance');
    const id=`mesa-palette-${index}`;
    host.innerHTML=`<button class="mesa-palette-toggle" type="button" aria-label="Elegir colores" aria-expanded="false" aria-controls="${id}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 1.6-3.2 1.8 1.8 0 0 1 1.4-2.9h1a4 4 0 0 0 4-4C21 6.5 17 3 12 3Z"/><circle cx="7.5" cy="10" r=".8"/><circle cx="11" cy="6.8" r=".8"/><circle cx="15.5" cy="8" r=".8"/></svg><strong>Colores</strong></button><section class="mesa-palette-panel" id="${id}" data-color-panel aria-label="Apariencia" hidden><h2>Apariencia</h2><p>Elige los tonos que te resulten más cómodos.</p><label for="${id}-select">Paleta de colores</label><select id="${id}-select" aria-label="Paleta de colores">${Object.entries(modes).map(([key,mode])=>`<option value="${key}">${mode.label}</option>`).join('')}</select><div class="mesa-palette-preview" aria-hidden="true"><span><i></i><i></i><i></i></span><b></b></div><p data-palette-copy role="status"></p><small>Tu elección se guarda en este navegador.</small></section>`;
    const button=host.querySelector('button');
    const panel=host.querySelector('.mesa-palette-panel');
    const select=panel.querySelector('select');
    const place=()=>{if(panel.hidden)return;const box=button.getBoundingClientRect();const width=panel.getBoundingClientRect().width;panel.style.left=`${Math.max(16,Math.min(box.right-width,innerWidth-width-16))}px`;panel.style.top=`${box.bottom+12}px`;panel.style.maxHeight=`${Math.max(120,innerHeight-box.bottom-28)}px`};
    const close=(focus=false)=>{if(panel.hidden)return;panel.hidden=true;button.setAttribute('aria-expanded','false');if(focus)button.focus({preventScroll:true})};
    button.addEventListener('click',()=>{if(!panel.hidden){close();return}for(const other of panels)if(other!==panel){other.hidden=true;other.previousElementSibling?.setAttribute('aria-expanded','false')}panel.hidden=false;button.setAttribute('aria-expanded','true');place();(panel.querySelector('.glide-select__trigger')||select).focus({preventScroll:true})});
    select.addEventListener('change',()=>{if(!syncing)apply(select.value)});
    document.addEventListener('keydown',event=>{if(event.key!=='Escape'||panel.hidden)return;if(panel.querySelector('.glide-select__trigger[aria-expanded="true"]'))return;event.preventDefault();close(true)},true);
    document.addEventListener('click',event=>{if(panel.hidden||host.contains(event.target)||event.target.closest('.glide-select__menu'))return;close()});
    document.addEventListener('focusin',event=>{if(panel.hidden||host.contains(event.target)||event.target.closest('.glide-select__menu'))return;close()});
    addEventListener('resize',place,{passive:true});
    panels.add(panel);
    select.value=pick();
    panel.querySelector('[data-palette-copy]').textContent=modes[pick()].copy;
  }
  let sequence=0;
  const scan=()=>document.querySelectorAll('[data-mesa-palette]:not([data-palette-mounted])').forEach(host=>mount(host,++sequence));
  scan();
  new MutationObserver(scan).observe(document.body,{childList:true,subtree:true});
  addEventListener('storage',event=>{if(['heiliang-color-mode','mesa-theme','mesa-empaque-theme',null].includes(event.key))apply(read(),false)});
  preference.addEventListener('change',()=>{if(!store.get('heiliang-color-mode')&&!store.get('mesa-theme')&&!store.get('mesa-empaque-theme'))apply(read(),false)});
  apply(pick(),false);
  window.MesaAppearance={apply};
})();
