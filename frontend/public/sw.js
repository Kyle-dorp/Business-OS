/*
 * Business-EOS service worker.
 *
 * Deliberately conservative about what it keeps. A point-of-sale tablet or a
 * manager's phone is often a shared device, so business data — invoices,
 * payroll figures, customer records — is never written to the cache. Only the
 * application shell and static assets are stored, so the app opens instantly
 * and degrades to a readable offline screen instead of a browser error.
 *
 * Strategies:
 *   navigation  -> network first, cached shell as fallback
 *   static      -> cache first, revalidated in the background
 *   /api, /auth -> network only, never stored
 */

const VERSION = 'v1';
const SHELL_CACHE = `eos-shell-${VERSION}`;
const ASSET_CACHE = `eos-assets-${VERSION}`;

const SHELL_URLS = ['/', '/index.html', '/offline.html', '/manifest.webmanifest'];

/* Anything matching these is user or business data. It does not get cached. */
const NEVER_CACHE = [
  /^\/api\//,
  /^\/auth\//,
  /^\/agent\//,
  /^\/billing\//,
  /^\/platform\//,
  /^\/finance\//,
  /^\/admin\//,
];

const isPrivate = (url) => NEVER_CACHE.some((re) => re.test(url.pathname));

const isStatic = (url) =>
  /\.(?:js|css|woff2?|ttf|otf|png|jpe?g|svg|webp|avif|ico)$/i.test(url.pathname);

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_URLS))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting()) // a missing shell file must not block install
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== SHELL_CACHE && k !== ASSET_CACHE)
            .map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (isPrivate(url)) return; // straight to the network, never stored

  /* Page navigations: fresh if possible, shell if not, offline page as the floor. */
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(SHELL_CACHE).then((c) => c.put('/index.html', copy)).catch(() => {});
          return response;
        })
        .catch(async () => {
          const cache = await caches.open(SHELL_CACHE);
          return (
            (await cache.match('/index.html')) ||
            (await cache.match('/offline.html')) ||
            new Response('Offline', { status: 503, headers: { 'Content-Type': 'text/plain' } })
          );
        })
    );
    return;
  }

  /* Static assets: serve instantly, refresh quietly in the background. */
  if (isStatic(url)) {
    event.respondWith(
      caches.open(ASSET_CACHE).then(async (cache) => {
        const hit = await cache.match(request);
        const network = fetch(request)
          .then((response) => {
            if (response.ok) cache.put(request, response.clone());
            return response;
          })
          .catch(() => hit);
        return hit || network;
      })
    );
  }
});

/* Lets the app trigger an update without a hard reload. */
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});
