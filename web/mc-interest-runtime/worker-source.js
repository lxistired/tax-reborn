// Separate independent receiver/formula runtime. No original resources bundled.
const fixedManifestSHA='bf511b0908d277d6a23fc3643d1cdfa16e99bcbcabadc2cc46ca8426bb4897b5';
const digest=async data=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',data))].map(x=>x.toString(16).padStart(2,'0')).join('');
let runtime;
function ready(){if(!runtime)runtime=(async()=>{
 const base=new URL('./',self.location.href),py=await loadPyodide({indexURL:new URL('../vendor/pyodide/',base).href});
 const response=await fetch(new URL('mc-interest-runtime.json',base));if(!response.ok)throw Error('Local comparison modules are unavailable.');
 const raw=await response.arrayBuffer();if(await digest(raw)!==fixedManifestSHA)throw Error('Local comparison module list changed.');
 const manifest=JSON.parse(new TextDecoder().decode(raw)),rows=manifest.files;
 if(manifest.format!=='tax-reborn-owned-mc-interest-runtime-v1'||manifest.command!=='source_mc_interest_compare'||manifest.python_module_limit!==192||!Array.isArray(rows)||rows.length!==188||new Set(rows.map(x=>x.path)).size!==rows.length||rows.filter(x=>x.path.endsWith('.py')).length!==184||rows.some(x=>!x||typeof x.path!=='string'||!(/^(?:[A-Za-z_0-9-]+\.(?:py|json)|source_mc\/[A-Za-z_0-9]+\.py|interop\/(?:__init__|(?:form_core|derived_form|container)\/[a-z_0-9]+)\.py)$/.test(x.path))||!Number.isSafeInteger(x.bytes)||x.bytes<1||x.bytes>1048576||!(/^[0-9a-f]{64}$/.test(x.sha256))))throw Error('Unsupported local comparison module list.');
 const verified=await Promise.all(rows.map(async row=>{const response=await fetch(new URL(row.path,base));if(!response.ok)throw Error('Local comparison module missing.');const bytes=new Uint8Array(await response.arrayBuffer());if(bytes.length!==row.bytes||await digest(bytes)!==row.sha256)throw Error('Local comparison module changed.');return [row.path,bytes];}));
 for(const[path,bytes]of verified){const dest='/home/pyodide/'+path;py.FS.mkdirTree(dest.slice(0,dest.lastIndexOf('/')));py.FS.writeFile(dest,bytes);}
 await py.runPythonAsync('import sys,json,gc\nsys.path.insert(0,"/home/pyodide")\nimport source_MC_raw_L4_request');return py;
})();return runtime;}
let queue=Promise.resolve();self.onmessage=({data:{id,command,payload}})=>{queue=queue.catch(()=>{}).then(async()=>{
 try{if(command!=='source_mc_interest_compare'){self.postMessage({id,error:'Unsupported source-interest comparison command.'});return;}const py=await ready(),started=performance.now();py.globals.set('_source_MC_interest_json',JSON.stringify(payload));const result=JSON.parse(await py.runPythonAsync('json.dumps(source_MC_raw_L4_request.calculate_request(json.loads(_source_MC_interest_json)),allow_nan=False)'));await py.runPythonAsync('del _source_MC_interest_json\ngc.collect()');self.postMessage({id,result,runtime:{elapsed_ms:performance.now()-started,native_engine_execution:0}});}
 catch(error){let message='The supported source-interest comparison could not complete.';if(error.name==='PythonError'){const last=String(error.message||error).trimEnd().split('\n').pop()||'',match=last.match(/^(?:[A-Za-z_]\w*\.)*(?:ValueError|UnsupportedProfile): (.+)$/);if(match)message=match[1];}else if(/^(?:Local comparison|Unsupported local comparison)/.test(error.message||''))message=error.message;if(runtime){try{const py=await runtime;await py.runPythonAsync('globals().pop("_source_MC_interest_json",None)\ngc.collect()');}catch{}}self.postMessage({id,error:message});}
});};
