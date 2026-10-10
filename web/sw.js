const CACHE = 'fittag-shell-free-v7';
const SHELL = ['./','./index.html','./app.css','./app.js','./client.mjs','./manifest.webmanifest','./icons/icon-192.png','./icons/icon-512.png','./icons/icon.svg','./demo.json','./demo.jpg','./free.css','./free.js','./free.mjs','./request.mjs','./photo-check.mjs','./batch.mjs','./example-jeans.jpg','./free-demo.json','./free-demo.jpg','./button.html'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('fittag-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
  const url = new URL(event.request.url), base = new URL(self.registration.scope);
  if(event.request.method!=='GET'||url.origin!==base.origin) return;
  const allowed = SHELL.some(path=>new URL(path,base).pathname===url.pathname);
  // Never cache health, uploaded photos, overlays or measurement API responses.
  if(!allowed) return;
  event.respondWith(fetch(event.request).then(response=>{
    if(response.ok){const copy=response.clone();event.waitUntil(caches.open(CACHE).then(cache=>cache.put(event.request,copy)));}
    return response;
  }).catch(()=>caches.match(event.request,{ignoreSearch:true}).then(cached=>cached||caches.match(new URL('./',base).href))));
});
