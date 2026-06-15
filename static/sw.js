const CACHE_NAME = 'litreview-v1';
const OFFLINE_URL = '/offline';

const PRECACHE_URLS = [
  '/',
  '/offline',
  '/dashboard',
  '/papers',
  '/reviews',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return Promise.allSettled(PRECACHE_URLS.map(url => cache.add(url).catch(() => {})));
    })
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.protocol === 'chrome-extension:') return;
  if (url.pathname.startsWith('/julisunkan')) return;
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ai/api/') || url.pathname.startsWith('/export/')) return;

  if (url.pathname.startsWith('/static/') || url.hostname.includes('cdn.jsdelivr') || url.hostname.includes('cdnjs.cloudflare')) {
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request).then(resp => {
        if (resp && resp.status === 200) {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return resp;
      }))
    );
    return;
  }

  event.respondWith(
    fetch(event.request).then(resp => {
      if (resp && resp.status === 200 && event.request.headers.get('Accept')?.includes('text/html')) {
        const clone = resp.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
      }
      return resp;
    }).catch(() =>
      caches.match(event.request).then(cached => cached || caches.match(OFFLINE_URL))
    )
  );
});
