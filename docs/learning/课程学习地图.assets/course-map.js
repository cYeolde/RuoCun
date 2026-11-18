(() => {
  "use strict";
  const toc = document.querySelector(".toc");
  const mobile = matchMedia("(max-width: 900px)");
  const sync = () => { if (toc) toc.open = !mobile.matches; };
  sync();
  mobile.addEventListener("change", sync);
  for (const link of document.querySelectorAll(".rail nav a")) {
    link.addEventListener("click", () => { if (mobile.matches && toc) toc.open = false; });
  }
  const items = [...document.querySelectorAll(".rail nav a")]
    .map(link => ({link, target: document.querySelector(link.getAttribute("href"))}))
    .filter(item => item.target);
  let queued = false;
  const update = () => {
    queued = false;
    let current = items[0];
    for (const item of items) if (item.target.getBoundingClientRect().top <= 160) current = item;
    if (scrollY + innerHeight >= document.documentElement.scrollHeight - 2) current = items.at(-1);
    for (const item of items) {
      if (item === current) item.link.setAttribute("aria-current", "location");
      else item.link.removeAttribute("aria-current");
    }
  };
  addEventListener("scroll", () => {
    if (!queued) { queued = true; requestAnimationFrame(update); }
  }, {passive: true});
  update();
})();
