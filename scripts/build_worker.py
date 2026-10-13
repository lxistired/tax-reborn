#!/usr/bin/env python3
"""Bundle local Pyodide bootstrap to avoid uncached worker importScripts.

No eval/blob scripts or external URLs. Original vendor files/notices remain
unmodified. Worker static fetch can read app-only CacheStorage if offline.
"""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];web=ROOT/'web'
prefix=r'''// Generated from pinned local runtime plus independently written worker source.
// A dedicated worker may not inherit its parent ServiceWorker's request handler.
const taxNativeFetch=self.fetch.bind(self);
self.fetch=async function(resource,options){
 try {const response=await taxNativeFetch(resource,options);if(response.ok)return response;throw Error('Static resource returned HTTP '+response.status);}
 catch(error){
  const url=new URL(typeof resource==='string'?resource:resource.url||resource.href,self.location.href);
  if(url.origin!==self.location.origin||url.pathname==='/api'||url.pathname.startsWith('/api/')||options?.method&&options.method!=='GET')throw error;
  if(typeof caches!=='undefined'){
   const names=(await caches.keys()).filter(n=>n.startsWith('tax-reborn-ui-')).sort((a,b)=>Number(b.match(/preview-(\d+)/)?.[1]||0)-Number(a.match(/preview-(\d+)/)?.[1]||0));
   for(const name of names){const cached=await(await caches.open(name)).match(url.href);if(cached)return cached;}
  }
  throw error;
 }
};
'''
files=['vendor/pyodide/pyodide.js','vendor/pyodide/pyodide.asm.js','tax-worker-source.js']
parts=[prefix]+[f'\n// Source: {name}\n'+(web/name).read_text()+'\n' for name in files]
(web/'tax-worker.js').write_text('\n'.join(parts))
(web/'tax-worker-build.json').write_text(json.dumps({'builder':'scripts/build_worker.py','network_services':False,'dynamic_eval':False,'sources':[{'file':name,'sha256':hashlib.sha256((web/name).read_bytes()).hexdigest()}for name in files],'worker_sha256':hashlib.sha256((web/'tax-worker.js').read_bytes()).hexdigest()},indent=2)+'\n')
print('Worker bundle:',(web/'tax-worker.js').stat().st_size,'bytes')

# Fixed LSTM/OEM1 engine avoids a second, uncontrolled importScripts in OCR.
core='vendor/tesseract/tesseract-core-lstm.wasm.js'
worker='vendor/tesseract/worker.min.js'
bridge="\nconst taxOCRCoreFactory=self.TesseractCore; self.TesseractCore=(options={})=>taxOCRCoreFactory({...options,locateFile:path=>new URL('vendor/tesseract/'+path,self.location.href).href});\n"
(web/'ocr-worker.js').write_text(prefix+'\n'+(web/core).read_text()+'\n'+bridge+(web/worker).read_text()+'\n')
(web/'ocr-worker-build.json').write_text(json.dumps({'builder':'scripts/build_worker.py','ocr_engine':'Tesseract6.0.0 non-SIMD LSTM OEM1','sources':[{'file':name,'sha256':hashlib.sha256((web/name).read_bytes()).hexdigest()}for name in (core,worker)],'worker_sha256':hashlib.sha256((web/'ocr-worker.js').read_bytes()).hexdigest()},indent=2)+'\n')
print('OCR bundle:',(web/'ocr-worker.js').stat().st_size,'bytes')
