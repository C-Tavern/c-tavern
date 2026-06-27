/**
 * SANFFOURA — Service Worker v2
 * Strategies:
 *   Shell / static  → Cache-First
 *   API / auth      → Network-Only
 *   HTML navigation → Network-First → shell fallback
 *   CDN images      → Stale-While-Revalidate
 *   Push events     → Show notification + open app on click
 */

const CACHE_VERSION   = 'sanffoura-v2';
const SHELL_CACHE     = `${CACHE_VERSION}-shell`;
const IMAGE_CACHE     = `${CACHE_VERSION}-images`;
const MAX_IMAGE_CACHE = 30;

const SHELL_URLS = [
  '/',
  '/login',
  '/static/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/static/icons/apple-touch-icon.png',
];

const NETWORK_ONLY = [/^\/api\//, /^\/whatsapp\//, /^\/logout/, /^\/sw\.js/];
const CDN_PATTERNS = [/^https:\/\/i\.postimg\.cc\//, /^https:\/\/image\.pollinations\.ai\//];

// ── Install ──────────────────────────────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(SHELL_CACHE)
      .then(c => c.addAll(SHELL_URLS))
      .then(() => self.skipWaiting())
      .catch(err => console.warn('[SW] shell cache partial:', err))
  );
});

// ── Activate ─────────────────────────────────────────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k.startsWith('sanffoura-') && k !== SHELL_CACHE && k !== IMAGE_CACHE)
            .map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch ────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', e => {
  const { request } = e;
  const url = new URL(request.url);
  if (request.method !== 'GET') return;
  if (NETWORK_ONLY.some(p => p.test(url.pathname))) { e.respondWith(fetch(request)); return; }
  if (CDN_PATTERNS.some(p => p.test(request.url)))  { e.respondWith(staleWhileRevalidate(request, IMAGE_CACHE)); return; }
  if (url.pathname.startsWith('/static/'))           { e.respondWith(cacheFirst(request, SHELL_CACHE)); return; }
  if (request.mode === 'navigate')                   { e.respondWith(networkFirstNav(request)); return; }
  e.respondWith(fetch(request).catch(() => caches.match(request)));
});

async function cacheFirst(req, name) {
  const hit = await caches.match(req);
  if (hit) return hit;
  try {
    const res = await fetch(req);
    if (res.ok) (await caches.open(name)).put(req, res.clone());
    return res;
  } catch { return new Response('Offline', { status: 503 }); }
}

async function networkFirstNav(req) {
  try {
    const res = await fetch(req);
    if (res.ok) (await caches.open(SHELL_CACHE)).put(req, res.clone());
    return res;
  } catch {
    return (await caches.match(req))
        || (await caches.match('/login'))
        || (await caches.match('/'))
        || new Response(offlinePage(), { status: 200, headers: { 'Content-Type': 'text/html;charset=utf-8' } });
  }
}

async function staleWhileRevalidate(req, name) {
  const cache  = await caches.open(name);
  const cached = await cache.match(req);
  const fresh  = fetch(req).then(res => {
    if (res.ok) { cache.put(req, res.clone()); trimCache(cache, MAX_IMAGE_CACHE); }
    return res;
  }).catch(() => cached);
  return cached || fresh;
}

async function trimCache(cache, max) {
  const keys = await cache.keys();
  if (keys.length > max) cache.delete(keys[0]);
}

// ── Push Notifications ────────────────────────────────────────────────────────
self.addEventListener('push', e => {
  let data = { title: 'SANFFOURA 🔞', body: '💋 لديك رسالة جديدة', icon: '/static/icons/icon-192x192.png', url: '/' };
  try { if (e.data) data = { ...data, ...e.data.json() }; } catch {}

  e.waitUntil(
    self.registration.showNotification(data.title, {
      body:    data.body,
      icon:    data.icon,
      badge:   '/static/icons/icon-96x96.png',
      image:   data.image || undefined,
      vibrate: [200, 80, 200, 80, 400],
      tag:     'sanffoura-msg',
      renotify: true,
      requireInteraction: false,
      data:    { url: data.url },
      actions: [
        { action: 'open',    title: '💬 فتح المحادثة' },
        { action: 'dismiss', title: '✕ إغلاق' },
      ],
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  if (e.action === 'dismiss') return;
  const target = e.notification.data?.url || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) {
        if ('focus' in c) { c.focus(); return c.navigate ? c.navigate(target) : undefined; }
      }
      if (clients.openWindow) return clients.openWindow(target);
    })
  );
});

// ── Offline Fallback ──────────────────────────────────────────────────────────
function offlinePage() {
  return `<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SANFFOURA — غير متصل</title>
<style>*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Arial,sans-serif;min-height:100vh;display:flex;
align-items:center;justify-content:center;flex-direction:column;gap:20px;
background:#07000f;color:#f0e6ff;text-align:center;padding:24px}
.icon{font-size:4rem;animation:p 2s ease-in-out infinite}
@keyframes p{0%,100%{transform:scale(1)}50%{transform:scale(1.1)}}
h1{font-size:1.5rem;font-weight:900;background:linear-gradient(135deg,#f0abfc,#c026d3);
-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
p{color:rgba(240,230,255,.55);font-size:.9rem;line-height:1.6;max-width:300px}
button{margin-top:8px;padding:12px 28px;border-radius:12px;border:none;cursor:pointer;
background:linear-gradient(135deg,#86198f,#c026d3);color:#fff;font-size:1rem;font-weight:700}
</style></head><body>
<div class="icon">📡</div><h1>SANFFOURA غير متصلة</h1>
<p>تحقق من اتصالك بالإنترنت وحاول مجدداً</p>
<button onclick="location.reload()">🔄 إعادة المحاولة</button>
</body></html>`;
}
