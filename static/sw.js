/**
 * SANFFOURA — Service Worker
 * Strategy:
 *   • Shell / static assets  → Cache-First (long-lived)
 *   • API calls              → Network-Only  (always fresh)
 *   • Navigation (HTML)      → Network-First → fallback to cached shell
 *   • Images (external CDN)  → Stale-While-Revalidate
 */

const CACHE_VERSION  = 'sanffoura-v1';
const SHELL_CACHE    = `${CACHE_VERSION}-shell`;
const IMAGE_CACHE    = `${CACHE_VERSION}-images`;
const MAX_IMAGE_CACHE = 30;

/** Pages and assets that form the app shell — cached on install */
const SHELL_URLS = [
  '/',
  '/login',
  '/static/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/static/icons/apple-touch-icon.png',
];

/** Routes that must ALWAYS go to the network (never serve stale) */
const NETWORK_ONLY_PATTERNS = [
  /^\/api\//,
  /^\/whatsapp\//,
  /^\/logout/,
];

/** External image domains — use stale-while-revalidate */
const CDN_PATTERNS = [
  /^https:\/\/i\.postimg\.cc\//,
  /^https:\/\/image\.pollinations\.ai\//,
];

// ─── Install ────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then(cache => cache.addAll(SHELL_URLS))
      .then(() => self.skipWaiting())
      .catch(err => console.warn('[SW] Shell cache partial failure:', err))
  );
});

// ─── Activate ───────────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k.startsWith('sanffoura-') && k !== SHELL_CACHE && k !== IMAGE_CACHE)
          .map(k => { console.log('[SW] Deleting old cache:', k); return caches.delete(k); })
      )
    ).then(() => self.clients.claim())
  );
});

// ─── Fetch ───────────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // 1. Only handle GET
  if (request.method !== 'GET') return;

  // 2. Network-only for API / auth routes
  if (NETWORK_ONLY_PATTERNS.some(p => p.test(url.pathname))) {
    event.respondWith(fetch(request));
    return;
  }

  // 3. CDN images — stale-while-revalidate
  if (CDN_PATTERNS.some(p => p.test(request.url))) {
    event.respondWith(staleWhileRevalidate(request, IMAGE_CACHE, MAX_IMAGE_CACHE));
    return;
  }

  // 4. Static assets (/static/...) — cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(request, SHELL_CACHE));
    return;
  }

  // 5. Navigation requests — network-first, fall back to cached '/'
  if (request.mode === 'navigate') {
    event.respondWith(networkFirstNavigation(request));
    return;
  }

  // 6. Anything else — network, no cache involvement
  event.respondWith(fetch(request).catch(() => caches.match(request)));
});

// ─── Strategies ──────────────────────────────────────────────────────────────

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Offline — asset unavailable', { status: 503 });
  }
}

async function networkFirstNavigation(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(SHELL_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request)
                || await caches.match('/login')
                || await caches.match('/');
    if (cached) return cached;
    return new Response(offlinePage(), {
      status: 200,
      headers: { 'Content-Type': 'text/html; charset=utf-8' },
    });
  }
}

async function staleWhileRevalidate(request, cacheName, maxEntries) {
  const cache  = await caches.open(cacheName);
  const cached = await cache.match(request);

  const fetchPromise = fetch(request).then(response => {
    if (response.ok) {
      cache.put(request, response.clone());
      trimCache(cache, maxEntries);
    }
    return response;
  }).catch(() => cached);

  return cached || fetchPromise;
}

async function trimCache(cache, maxEntries) {
  const keys = await cache.keys();
  if (keys.length > maxEntries) {
    await cache.delete(keys[0]);
  }
}

// ─── Offline fallback page ────────────────────────────────────────────────────
function offlinePage() {
  return `<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>SANFFOURA — غير متصل</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{
      font-family:'Segoe UI',Arial,sans-serif;
      min-height:100vh;display:flex;align-items:center;
      justify-content:center;flex-direction:column;gap:20px;
      background:#07000f;color:#f0e6ff;text-align:center;padding:24px;
    }
    .icon{font-size:4rem;animation:pulse 2s ease-in-out infinite}
    @keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.1)}}
    h1{font-size:1.6rem;font-weight:900;
       background:linear-gradient(135deg,#f0abfc,#c026d3);
       -webkit-background-clip:text;-webkit-text-fill-color:transparent;
       background-clip:text}
    p{color:rgba(240,230,255,.55);font-size:.95rem;line-height:1.6;max-width:320px}
    button{
      margin-top:8px;padding:12px 28px;border-radius:12px;border:none;cursor:pointer;
      background:linear-gradient(135deg,#86198f,#c026d3);color:#fff;
      font-size:1rem;font-weight:700;font-family:inherit;
    }
  </style>
</head>
<body>
  <div class="icon">📡</div>
  <h1>SANFFOURA غير متصلة</h1>
  <p>يبدو أنك غير متصل بالإنترنت.<br>تحقق من اتصالك وحاول مجدداً.</p>
  <button onclick="location.reload()">🔄 إعادة المحاولة</button>
</body>
</html>`;
}

// ─── Background Sync (future-proof hook) ────────────────────────────────────
self.addEventListener('sync', event => {
  console.log('[SW] Background sync:', event.tag);
});

// ─── Push Notifications (future-proof hook) ─────────────────────────────────
self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(
    self.registration.showNotification(data.title || 'SANFFOURA 🔞', {
      body:    data.body    || 'لديك رسالة جديدة 💋',
      icon:    '/static/icons/icon-192x192.png',
      badge:   '/static/icons/icon-96x96.png',
      vibrate: [200, 100, 200],
      data:    { url: data.url || '/' },
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const client of list) {
        if (client.url === '/' && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(event.notification.data?.url || '/');
    })
  );
});
