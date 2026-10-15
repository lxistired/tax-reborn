#!/usr/bin/env python3
"""Bundle local Pyodide bootstrap to avoid uncached worker importScripts.

No eval/blob scripts or external URLs. Original vendor files/notices remain
unmodified. Worker static fetch can read app-only CacheStorage if offline.
"""
from pathlib import Path
import hashlib,json,re,shutil
ROOT=Path(__file__).resolve().parents[1];web=ROOT/'web'
# The packaged worker uses the same independent codec as host acceptance.
# This is generated from our source, never from private binary evidence.
generated=web/'interop'
if generated.exists():shutil.rmtree(generated)
shutil.copytree(ROOT/'interop',generated,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
binary_modules=sorted(p.relative_to(web).as_posix() for p in generated.rglob('*.py'))
samples=web/'samples/binary-tax';samples.mkdir(parents=True,exist_ok=True)
sample_assets=['samples/plaintext-container-request.json','samples/plaintext-container-blocked-request.json','samples/mac-taxml-request.json','samples/mac-taxml-blocked-request.json']
for source_name,target_name in [('request.json','mac-taxml-request.json'),('blocked-request.json','mac-taxml-blocked-request.json')]:
 shutil.copy2(ROOT/'fixtures/mac-taxml'/source_name,web/'samples'/target_name)
for source_name,target_name in [('request.json','mac-scalar-request.json'),('blocked-request.json','mac-scalar-blocked-request.json')]:
 shutil.copy2(ROOT/'fixtures/mac-scalar-taxml'/source_name,web/'samples'/target_name);sample_assets.append('samples/'+target_name)
for source_name,target_name in [('request.json','mac-date-request.json'),('blocked-request.json','mac-date-blocked-request.json')]:
 shutil.copy2(ROOT/'fixtures/mac-date-taxml'/source_name,web/'samples'/target_name);sample_assets.append('samples/'+target_name)
for name in ('income-request.json','nested-request.json','filing-status-request.json','merged-request.json','merged-nested-request.json','value-table-request.json','derived-income-request.json','derived-array-request.json','derived-opaque-request.json','auto-array-income-request.json','auto-array-used-request.json','auto-array-opaque-request.json','typed-value-income-request.json','typed-value-empty-request.json','typed-value-opaque-request.json','whole-number-income-request.json','persistent-document-income-request.json','instance-map-income-request.json'):
 source=ROOT/'fixtures/binary-tax'/name
 if not source.is_file():raise FileNotFoundError('Generate independent binary samples before bundling: '+str(source))
 shutil.copy2(source,samples/name);sample_assets.append('samples/binary-tax/'+name)
(web/'binary-runtime.json').write_text(json.dumps({'format':'tax-reborn-binary-runtime-v1',
 'modules':binary_modules,'sha256':{name:hashlib.sha256((web/name).read_bytes()).hexdigest() for name in binary_modules}},indent=2)+'\n')
manifest=web/'offline-assets.json'
if manifest.exists():
 data=json.loads(manifest.read_text());assets=data if isinstance(data,list) else data['assets']
 assets[:]=sorted(set(assets+binary_modules+sample_assets+['binary_tax.py','binary_derived.py','source_integer.py','binary-runtime.json']))
 manifest.write_text(json.dumps(data,indent=2)+'\n')
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

# The read-only comparison uses its own pinned worker and byte manifest.
import subprocess,sys
subprocess.run([sys.executable,str(ROOT/'scripts/build_source_comparison.py')],check=True)

# Rebuild the separate source-interest reader without any original resources.
subprocess.run([sys.executable,str(ROOT/'scripts/build_raw_interest_worker.py')],check=True)

# The availability panel must inspect the cache used by the service worker.
cache_version=re.search(r"const VERSION='([^']+)';",(web/'service-worker.js').read_text()).group(1)
readiness=web/'offline-readiness.js'
updated,count=re.subn(r"const VERSION='[^']+';",lambda _:"const VERSION='"+cache_version+"';",readiness.read_text(),count=1)
if count!=1:raise ValueError('Expected one offline availability cache version')
readiness.write_text(updated)
