// Aufgaben PWA Service Worker v2 – Network-First
// Scope: /aufgaben/  |  Keine Abhängigkeit zu anderen App-Repos
const CACHE = 'iab-aufgaben-v36';
const APP_SHELL = [
  '/aufgaben/',
  '/aufgaben/index.html',
  '/aufgaben/manifest.json',
  '/aufgaben/icon-192.png',
  '/aufgaben/icon-512.png',
];

// Install: App-Shell vorab cachen
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(APP_SHELL)).then(() => self.skipWaiting())
  );
});

// Activate: alte Cache-Versionen bereinigen
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Fetch: Network-First (verhindert veraltete Daten), Cache als Fallback
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Supabase & externe APIs: immer Netz, nie cachen
  if (url.hostname.includes('supabase.co') || url.hostname.includes('googleapis.com')) {
    e.respondWith(
      fetch(e.request).catch(() =>
        new Response(JSON.stringify({ error: 'offline' }), {
          headers: { 'Content-Type': 'application/json' }
        })
      )
    );
    return;
  }

  // App-Shell: Network-First, bei Netzwerkfehler aus Cache
  if (e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request)
      .then(resp => {
        if (resp.ok) {
          const clone = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return resp;
      })
      .catch(() =>
        caches.match(e.request).then(cached => cached || caches.match('/aufgaben/index.html'))
      )
  );
});
