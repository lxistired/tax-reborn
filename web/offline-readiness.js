'use strict';
(function(){
 const VERSION='tax-reborn-ui-2025-preview-20';
 const SHELL=['./','index.html','style.css','app.js','local-api.js','investment-corrections.js','tax-worker.js','native-file-bridge.js','document-import.js','state-workspace.js','state-worker.js','offline-readiness.js','ocr-worker.js','manifest.webmanifest','icon.svg','icon-192.png','icon-512.png'];
 const BOOT=['index.html','style.css','app.js','local-api.js','investment-corrections.js','tax-worker.js','offline-readiness.js'];
 const OCR_CORE=['tesseract-core','tesseract-core-lstm','tesseract-core-simd','tesseract-core-simd-lstm'].flatMap(name=>['vendor/tesseract/'+name+'.wasm.js','vendor/tesseract/'+name+'.wasm']);
 const PYODIDE=['vendor/pyodide/pyodide.js','vendor/pyodide/pyodide.asm.js','vendor/pyodide/pyodide.asm.wasm','vendor/pyodide/python_stdlib.zip','vendor/pyodide/pyodide-lock.json','vendor/pyodide/package.json'];
 const base=new URL('./',location.href),canonical=value=>new URL(value,base).href;
 function validAsset(value){
  if(typeof value!=='string'||!value||/[\\\u0000-\u001f\u007f]/.test(value))return false;
  try{let decoded=value;for(let step=0;step<8;step++){const next=decodeURIComponent(decoded);if(next===decoded)break;decoded=next;}if(decoded.includes('%')||decoded.includes('..')||/[\\\u0000-\u001f\u007f]/.test(decoded))return false;const url=new URL(value,base),decodedURL=new URL(decoded,base);return url.origin===location.origin&&decodedURL.origin===location.origin&&!url.username&&!url.password&&!url.search&&!url.hash&&decodedURL.pathname!=='/api'&&!decodedURL.pathname.startsWith('/api/');}catch{return false;}
 }
 const unique=values=>[...new Set(values.map(canonical))];
 const display=value=>new URL(value).pathname.slice(base.pathname.length);
 async function cachedManifest(cache){const response=await cache?.match(canonical('offline-assets.json'));if(!response)return null;try{const body=await response.json();if(!Array.isArray(body.assets))return null;return{...body,assets:body.assets.filter(validAsset)};}catch{return null;}}
 function resourceGroups(assets){
  const helpers=['tax_engine.py','tax_extended.py','tax_credits.py','presentation_schema.py','rules_2025.json','forms/paper-fact-schema-2025.json',...assets.filter(path=>/^tax_[^/]+\.py$/.test(path))];
  const engine=[...BOOT,...PYODIDE,...helpers];
  const image=['native-file-bridge.js','document-import.js','vendor/tesseract/tesseract.min.js','vendor/tesseract/worker.min.js','vendor/tesseract/eng.traineddata.gz',...OCR_CORE,...assets.filter(path=>path.startsWith('vendor/tesseract/')&&/\.wasm(?:\.js)?$/.test(path))];
  return[{id:'shell',label:'Application shell',assets:SHELL},{id:'engine',label:'Federal tax engine',assets:engine},{id:'pdf',label:'PDF draft and readable-PDF text',assets:[...engine,'forms.py','official_forms.py','privacy_review.py','vendor/python/pypdf-6.10.0.whl',...assets.filter(path=>path.startsWith('forms/'))]},{id:'photo',label:'Local W-2 image extraction',assets:[...BOOT,'ocr-worker.js',...image]},{id:'state',label:'State tax workspace',assets:[...BOOT,'state-workspace.js','state-worker.js']}];
 }
 async function inspect(){
  if(!window.caches)return{cache_version:VERSION,supported:false,error:'CacheStorage is unavailable in this browser. Packaged native assets are separate and are not verified by this browser-cache check.',groups:[]};
  const names=await caches.keys(),exists=names.includes(VERSION),cache=exists?await caches.open(VERSION):null,manifest=await cachedManifest(cache),assets=manifest?.assets||[],groups=[];
  for(const group of resourceGroups(assets)){const paths=unique(group.assets),missing=[];for(const path of paths)if(!await cache?.match(path))missing.push(display(path));groups.push({id:group.id,label:group.label,cached:!!manifest&&manifest.manifest_loaded!==false&&missing.length===0,required:paths.length,missing});}
  const all=unique([...SHELL,...assets]),missing=[];for(const path of all)if(!await cache?.match(path))missing.push(display(path));
  return{cache_version:VERSION,supported:true,cache_exists:exists,manifest_cached:!!manifest,manifest_loaded:manifest?.manifest_loaded!==false&&!!manifest,preparing:manifest?.preparing===true,prepared_at:manifest?.prepared_at||null,all_resources_cached:!!manifest&&manifest.manifest_loaded!==false&&missing.length===0,total_assets:all.length,missing_assets:missing,download_failures:manifest?.download_failures||[],manifest_error:manifest?.manifest_error||'',service_worker_controls_page:!!navigator.serviceWorker?.controller,groups};
 }
 async function prepare(onProgress=()=>{}){
  if(!window.caches)throw Error('This browser does not expose CacheStorage.');
  const cache=await caches.open(VERSION);let assets=[],manifestLoaded=false,manifestError='';
  try{const response=await fetch(canonical('offline-assets.json'),{cache:'no-store',headers:{'X-Tax-Reborn-Prepare-Offline':'1'}});if(!response.ok)throw Error('Asset manifest: HTTP '+response.status);const body=await response.json(),list=Array.isArray(body)?body:body.assets;if(!Array.isArray(list))throw Error('The asset manifest has no assets array.');assets=[...new Set(list.filter(validAsset))];manifestLoaded=true;}catch(error){manifestError=String(error.message||error);const previous=await cachedManifest(cache);assets=previous?.assets||[];manifestLoaded=!!previous;}
  const store=metadata=>cache.put(canonical('offline-assets.json'),new Response(JSON.stringify({assets,cache_version:VERSION,manifest_loaded:manifestLoaded,manifest_error:manifestError,...metadata}),{headers:{'Content-Type':'application/json'}}));
  await store({preparing:true,prepared_at:null});const failures=[],paths=unique([...SHELL,...assets]);
  for(let index=0;index<paths.length;index++){
   const path=paths[index];onProgress('Caching '+(index+1)+' / '+paths.length+': '+display(path));
   try{const response=await fetch(path,{cache:'reload',headers:{'X-Tax-Reborn-Prepare-Offline':'1'}});if(!response.ok)throw Error('HTTP '+response.status);await cache.put(path,response);}catch(error){failures.push({asset:display(path),error:String(error.message||error)});}
  }
  const missing=[];for(const path of paths)if(!await cache.match(path))missing.push(display(path));
  await store({preparing:false,prepared_at:new Date().toISOString(),missing_assets:missing,download_failures:failures});
  if(navigator.serviceWorker){try{const registration=await navigator.serviceWorker.register('service-worker.js');await registration.update();}catch{}}
  return inspect();
 }
 const node=(tag,text,className)=>{const item=document.createElement(tag);if(text!==undefined)item.textContent=text;if(className)item.className=className;return item;};
 window.showOfflineReadiness=async()=>{
  const overlay=node('div',undefined,'overlay'),dialog=node('section',undefined,'dialog');dialog.setAttribute('role','dialog');dialog.setAttribute('aria-modal','true');dialog.setAttribute('aria-label','Offline resource availability');overlay.append(dialog);
  const close=()=>overlay.remove(),header=node('header',undefined,'dialog-header'),closeButton=node('button','×','icon-button');closeButton.type='button';closeButton.setAttribute('aria-label','Close offline availability');closeButton.onclick=close;header.append(node('h2','Offline resource availability'),closeButton);
  const body=node('div',undefined,'dialog-body'),status=node('div',undefined,'note'),list=node('div'),progress=node('div',undefined,'note');progress.setAttribute('aria-live','polite');progress.hidden=true;
  body.append(node('p','This checks only explicitly listed application resources in the app’s static cache. It does not read saved returns, document attachments or private tax data. Cache presence does not prove that this browser can cold-start a dedicated worker.','intro'),status,list,progress);
  const footer=node('footer',undefined,'dialog-footer'),refresh=node('button','Refresh status','button secondary'),retry=node('button','Prepare / retry offline cache','button primary');refresh.type=retry.type='button';footer.append(refresh,retry);dialog.append(header,body,footer);document.body.append(overlay);
  async function render(report){
   list.replaceChildren();status.textContent=report.supported?'Target cache: '+report.cache_version+' · '+(report.manifest_cached?'asset manifest stored':'no stored asset manifest')+' · '+(report.service_worker_controls_page?'page controlled by a service worker':'page not controlled by a service worker'):report.error;
   if(!report.supported){retry.disabled=true;return;}
   if(report.preparing)list.append(node('p','Resource caching is in progress. Refresh to inspect the current files.','note warning'));
   if(report.manifest_error)list.append(node('p','Manifest fetch: '+report.manifest_error,'note warning'));
   for(const group of report.groups){const section=node('section',undefined,'section-card');section.append(node('h3',group.label+': '+(group.cached?'Cache complete':'Missing resources')),node('small',(group.required-group.missing.length)+' / '+group.required+' required resources cached'));
    if(group.missing.length){const details=node('details',undefined,'details-toggle');details.open=true;details.append(node('summary',group.missing.length+' missing paths'));const paths=node('ul',undefined,'issue-list');for(const path of group.missing)paths.append(node('li',path));details.append(paths);section.append(details);}list.append(section);
   }
   if(report.download_failures.length){const details=node('details',undefined,'details-toggle');details.open=true;details.append(node('summary','Last preparation download failures'));const errors=node('ul',undefined,'issue-list');for(const item of report.download_failures)errors.append(node('li',item.asset+': '+item.error));details.append(errors);list.append(details);}
   list.append(node('p',report.all_resources_cached?'All listed static resources are cached. Verify an actual cold start before relying on this browser while offline.':report.missing_assets.length+' listed static resources are missing. Keep the local service available and retry before attempting an offline cold start.','note warning'));
  }
  refresh.onclick=async()=>{try{await render(await inspect());}catch(error){status.textContent=error.message;}};
  retry.onclick=async()=>{retry.disabled=refresh.disabled=true;progress.hidden=false;try{await render(await prepare(text=>progress.textContent=text));progress.textContent='Preparation finished. Component statuses show actual cache presence; cold-start runtime verification is separate.';}catch(error){progress.textContent='Preparation failed: '+error.message;}finally{retry.disabled=refresh.disabled=false;}};
  try{await render(await inspect());}catch(error){status.textContent=error.message;}
 };
 window.taxOfflineResources={inspect,prepare,cacheVersion:VERSION};
})();
