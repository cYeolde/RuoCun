(() => {
  'use strict';
  const entry = document.getElementById('revised-course-entry');
  if (!entry) return;

  const destination = new URL(entry.href);
  if (location.hash) {
    let anchor;
    try {
      anchor = decodeURIComponent(location.hash.slice(1));
    } catch {
      return;
    }
    const routes = JSON.parse(entry.dataset.routes);
    if (!Object.hasOwn(routes, anchor)) return;
    const route = routes[anchor];
    if (route.startsWith('#')) {
      destination.hash = route;
    } else {
      const moved = new URL(route, destination);
      destination.pathname = moved.pathname;
      destination.hash = moved.hash;
    }
  }
  destination.search = location.search;
  location.replace(destination.href);
})();
