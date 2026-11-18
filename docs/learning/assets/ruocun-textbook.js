(() => {
  'use strict';
  const toc = document.querySelector('.v2-course-toc');
  const rail = document.querySelector('.reading-nav');
  const mobile = matchMedia('(max-width: 900px)');
  const sync = () => { toc.open = !mobile.matches; };
  sync();
  mobile.addEventListener('change', () => {sync(); lastCurrent = null; update();});
  const links = [...toc.querySelectorAll('a[href^="#"]')];
  const sections = links.map(link => ({link, target:document.querySelector(link.getAttribute('href'))})).filter(item=>item.target);
  for (const link of links) link.addEventListener('click', () => {
    if (mobile.matches) toc.open = false;
  });
  let queued = false;
  let lastCurrent = null;
  const update = () => {
    queued = false;
    let current = sections[0];
    for (const item of sections) if (item.target.getBoundingClientRect().top <= 160) current = item;
    if (scrollY + innerHeight >= document.documentElement.scrollHeight - 2) current = sections.at(-1);
    for (const {link} of sections) {
      const selected = current?.link === link;
      link.classList.toggle('is-current', selected);
      if (selected) link.setAttribute('aria-current','location');
      else link.removeAttribute('aria-current');
    }
    if (current?.link !== lastCurrent) {
      lastCurrent = current?.link;
      if (lastCurrent && !mobile.matches && !rail.matches(':hover')) {
        const item = lastCurrent.getBoundingClientRect();
        const frame = rail.getBoundingClientRect();
        if (item.bottom > frame.bottom - 16) rail.scrollTop += item.bottom - frame.bottom + 24;
        else if (item.top < frame.top + 16) rail.scrollTop += item.top - frame.top - 24;
      }
    }
  };
  addEventListener('scroll', () => {if(!queued){queued=true;requestAnimationFrame(update);}}, {passive:true});
  update();
  for (const button of document.querySelectorAll('.textbook-copy')) {
    button.addEventListener('click', async () => {
      const text = button.closest('.ruocun-code').querySelector('pre code').textContent;
      try {
        if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
        else {
          const buffer = document.createElement('textarea');
          buffer.className = 'textbook-copy-buffer';
          buffer.value = text;
          buffer.setAttribute('aria-hidden','true');
          document.body.append(buffer);
          buffer.select();
          const copied = document.execCommand('copy');
          buffer.remove();
          if (!copied) throw new Error('Clipboard unavailable');
        }
        button.textContent='已复制';
      } catch {
        button.textContent='请手动选择';
      }
      setTimeout(()=>{button.textContent='复制';},1800);
    });
  }
})();
