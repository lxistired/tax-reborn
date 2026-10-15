'use strict';
const VERSION='tax-reborn-ui-2025-preview-44';
const SHELL=['./','./index.html','./style.css','./app.js','./local-api.js','./investment-corrections.js','./income-preparation.js','./tax-worker.js','./native-file-bridge.js','./document-import.js','./taxml-import.js','./taxml_wire.py','./taxml_native.py','./taxml_xml_edit.py','./taxml_preparation.py','./state-workspace.js','./state-worker.js','./offline-readiness.js','./ocr-worker.js','./manifest.webmanifest','./icon.svg','./icon-192.png','./icon-512.png'];
let configuredAssets=[];
const canonical=value=>new URL(value,self.registration.scope).href;
function validAsset(value){
 if(typeof value!=='string'||!value||/[\\\u0000-\u001f\u007f]/.test(value))return false;
 try{
  let decoded=value;
  for(let iteration=0;iteration<8;iteration++){const next=decodeURIComponent(decoded);if(next===decoded)break;decoded=next;}
  if(decoded.includes('%')||decoded.includes('..')||/[\\\u0000-\u001f\u007f]/.test(decoded))return false;
  const url=new URL(value,self.registration.scope),decodedUrl=new URL(decoded,self.registration.scope),path=decodedUrl.pathname;
  return url.origin===self.location.origin&&decodedUrl.origin===self.location.origin&&!url.username&&!url.password&&!url.search&&!url.hash&&path!=='/api'&&!path.startsWith('/api/');
 }catch{return false;}
}
async function saveManifest(cache,metadata={}){
 await cache.put(canonical('offline-assets.json'),new Response(JSON.stringify({assets:configuredAssets,cache_version:VERSION,...metadata}),{headers:{'Content-Type':'application/json'}}));
}
async function prepareCache(){
 const cache=await caches.open(VERSION),failures=[];let manifestLoaded=false,manifestError='';
 try{
  const response=await fetch(canonical('offline-assets.json'),{cache:'no-store'});
  if(!response.ok)throw Error('Asset manifest: HTTP '+response.status);
  const body=await response.json(),assets=Array.isArray(body)?body:body.assets;
  if(!Array.isArray(assets))throw Error('Asset manifest must contain an assets array.');
  configuredAssets=[...new Set(assets.filter(validAsset))];manifestLoaded=true;
 }catch(error){
  manifestError=String(error.message||error);
  const stored=await cache.match(canonical('offline-assets.json'));
  if(stored){try{const body=await stored.json();configuredAssets=(body.assets||[]).filter(validAsset);manifestLoaded=Array.isArray(body.assets);}catch{configuredAssets=[];}}
 }
 // Save the whole asset list before any individual download can fail.
 await saveManifest(cache,{manifest_loaded:manifestLoaded,manifest_error:manifestError,preparing:true,prepared_at:null});
 for(const path of [...new Set([...SHELL,...configuredAssets])]){
  try{
   const response=await fetch(canonical(path),{cache:'reload'});
   if(!response.ok)throw Error('HTTP '+response.status);
   await cache.put(canonical(path),response);
  }catch(error){failures.push({asset:path,error:String(error.message||error)});}
 }
 const missing=[];
 for(const path of [...new Set([...SHELL,...configuredAssets])])if(!await cache.match(canonical(path)))missing.push(path);
 await saveManifest(cache,{manifest_loaded:manifestLoaded,manifest_error:manifestError,preparing:false,prepared_at:new Date().toISOString(),missing_assets:missing,download_failures:failures});
 return{cache_version:VERSION,manifest_loaded:manifestLoaded,missing_assets:missing,download_failures:failures};
}
self.addEventListener('install',event=>event.waitUntil((async()=>{await prepareCache();await self.skipWaiting();})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{
 const cache=await caches.open(VERSION),manifest=await cache.match(canonical('offline-assets.json'));
 if(manifest){try{configuredAssets=((await manifest.json()).assets||[]).filter(validAsset);}catch{configuredAssets=[];}}
 // Preserve earlier caches until the new manifest and shell are present.
 let shellComplete=!!manifest;
 for(const path of SHELL)if(!await cache.match(canonical(path)))shellComplete=false;
 if(shellComplete)for(const key of await caches.keys())if(key.startsWith('tax-reborn-ui-')&&key!==VERSION)await caches.delete(key);
 await self.clients.claim();
})()));
self.addEventListener('message',event=>{
 if(event.data?.type==='TAX_REBORN_CACHE_VERSION')event.ports?.[0]?.postMessage({cache_version:VERSION});
});
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url);
 if(request.method!=='GET'||url.origin!==self.location.origin||url.pathname==='/api'||url.pathname.startsWith('/api/')||request.headers.get('X-Tax-Reborn-Prepare-Offline')==='1')return;
 if(request.mode==='navigate'){event.respondWith(fetch(request).catch(()=>caches.match(canonical('index.html'))));return;}
 const allowed=new Set([...SHELL,...configuredAssets].map(canonical));if(!allowed.has(url.href))return;
 event.respondWith((async()=>{
  const cache=await caches.open(VERSION),editable=SHELL.map(canonical).includes(url.href)||(!url.pathname.includes('/vendor/')&&/\.(?:js|json|py|txt)$/.test(url.pathname));
  if(editable){try{const response=await fetch(request,{cache:'no-cache'});if(response.ok)await cache.put(request,response.clone());return response;}catch{const cached=await cache.match(request);if(cached)return cached;throw Error('The app resource is unavailable offline: '+url.pathname);}}
  const cached=await cache.match(request);if(cached)return cached;
  const response=await fetch(request);if(response.ok)await cache.put(request,response.clone());return response;
 })());
});
