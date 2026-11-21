(() => {
  'use strict';
  const toc = document.querySelector('.v2-course-toc');
  const rail = document.querySelector('.reading-nav');
  const mobile = matchMedia('(max-width: 900px)');
  const article = document.querySelector('article[data-format="article"]');
  let drawer;
  if (article) {
    drawer = document.createElement('dialog');
    drawer.id = 'article-toc-drawer';
    drawer.className = 'article-toc-drawer';
    drawer.setAttribute('aria-label', '文章目录');
    document.body.append(drawer);
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'article-toc-toggle';
    toggle.textContent = rail.querySelector('.chapter-number').textContent + ' · 目录';
    toggle.setAttribute('aria-haspopup', 'dialog');
    toggle.setAttribute('aria-controls', drawer.id);
    toggle.setAttribute('aria-expanded', 'false');
    document.querySelector('.textbook-brand').after(toggle);
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'article-toc-close';
    close.textContent = '关闭目录';
    drawer.append(close);
    toggle.addEventListener('click', () => {
      drawer.showModal();
      toggle.setAttribute('aria-expanded', 'true');
    });
    close.addEventListener('click', () => drawer.close());
    drawer.addEventListener('close', () => toggle.setAttribute('aria-expanded', String(drawer.open)));
    drawer.addEventListener('click', event => {
      if (event.target === drawer && event.clientX > drawer.getBoundingClientRect().right) drawer.close();
    });
  }
  const sync = () => {
    if (drawer) {
      if (mobile.matches) drawer.append(rail);
      else {
        if (drawer.open) drawer.close();
        article.before(rail);
      }
    }
    toc.open = !!drawer || !mobile.matches;
  };
  const links = [...toc.querySelectorAll('a[href^="#"]')];
  const sections = links.map(link => ({link, target:document.querySelector(link.getAttribute('href'))})).filter(item=>item.target);
  for (const link of links) link.addEventListener('click', () => {
    if (drawer?.open) {
      drawer.close();
      const target = document.querySelector(link.hash);
      target.setAttribute('tabindex', '-1');
      target.focus({preventScroll: true});
    } else if (mobile.matches) toc.open = false;
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
  sync();
  mobile.addEventListener('change', () => {sync(); lastCurrent = null; update();});
  update();
  const indentationColumns = indent => {
    let columns = 0;
    for (const char of indent) columns += char === '\t' ? 2 - (columns % 2) : 1;
    return columns;
  };
  const wrapSource = figure => {
    const code = figure.querySelector('pre code');
    const numbers = [...figure.querySelectorAll('.ruocun-code-gutter > span')];
    if (!code || !numbers.length) return;

    let commonIndent;
    for (const line of code.textContent.split('\n')) {
      if (!line.trim()) continue;
      const leading = line.match(/^[ \t]*/)[0];
      if (commonIndent === undefined) commonIndent = leading;
      while (!leading.startsWith(commonIndent)) commonIndent = commonIndent.slice(0, -1);
      if (!commonIndent) break;
    }

    const emptyLine = () => ({indent: '', tokens: document.createDocumentFragment()});
    const lines = [emptyLine()];
    let atIndent = true;
    const walker = document.createTreeWalker(code, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const parts = node.data.split('\n');
      for (const [index, part] of parts.entries()) {
        if (index) {
          lines.push(emptyLine());
          atIndent = true;
        }
        const line = lines.at(-1);
        const indent = atIndent ? part.match(/^[ \t]*/)[0] : '';
        line.indent += indent;
        const content = part.slice(indent.length);
        if (!content) continue;
        atIndent = false;
        let token = document.createTextNode(content);
        for (let parent = node.parentElement; parent !== code; parent = parent.parentElement) {
          const highlighted = parent.cloneNode(false);
          highlighted.append(token);
          token = highlighted;
        }
        line.tokens.append(token);
      }
    }
    if (lines.length !== numbers.length) return;

    const rows = document.createDocumentFragment();
    for (const [index, line] of lines.entries()) {
      const row = document.createElement('span');
      row.className = 'ruocun-code-row';
      const number = document.createElement('span');
      number.className = 'ruocun-code-line-number';
      number.dataset.line = numbers[index].dataset.line || '';
      number.setAttribute('aria-hidden', 'true');
      const text = document.createElement('span');
      text.className = 'ruocun-code-line';
      if (line.indent) {
        // Draw indentation as spacing so a wrapped row begins with visible code.
        const indentation = document.createElement('span');
        indentation.hidden = true;
        indentation.textContent = line.indent;
        text.append(indentation);
        text.style.setProperty('--code-line-indent', indentationColumns(line.indent));
      }
      text.append(line.tokens);
      row.append(number, text);
      // Retain logical newlines for the copy button. CSS only wraps within a row.
      if (index) rows.append('\n');
      rows.append(row);
    }
    code.replaceChildren(rows);
    figure.style.setProperty('--code-common-indent', indentationColumns(commonIndent || ''));
    figure.classList.add('ruocun-code--wrapped');
  };
  if (article) {
    const sourceFigures = 'figure.ruocun-code[data-language="python"], figure.ruocun-code[data-language="javascript"]';
    article.querySelectorAll(sourceFigures).forEach(wrapSource);
  }
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
