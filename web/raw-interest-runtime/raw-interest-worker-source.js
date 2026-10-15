// Independent private worker. No original resource bytes are installed here.

const digest=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');
let runtime;
function ready(){
 if(!runtime)runtime=(async()=>{
  const base=new URL('./',self.location.href),py=await loadPyodide({indexURL:new URL('../vendor/pyodide/',base).href});
  const manifest=await(await fetch(new URL('raw-interest-runtime.json',base))).json();
  if(manifest.format!=='tax-reborn-private-raw-interest-runtime-v1'||!Array.isArray(manifest.files)||manifest.files.length>256)throw Error('Unsupported bounded raw calculation runtime.');
  for(const row of manifest.files){
   if(!/^(?:[A-Za-z_0-9-]+\.(?:py|json)|interop\/(?:__init__|(?:form_core|derived_form|container)\/[a-z_0-9]+)\.py)$/.test(row.path))throw Error('Invalid raw runtime path.');
   const response=await fetch(new URL(row.path,base));if(!response.ok)throw Error('Missing independent raw calculation module.');
   const bytes=new Uint8Array(await response.arrayBuffer());if(await digest(bytes)!==row.sha256)throw Error('Raw calculation runtime hash mismatch.');
   const destination='/home/pyodide/'+row.path;py.FS.mkdirTree(destination.slice(0,destination.lastIndexOf('/')));py.FS.writeFile(destination,bytes);
  }
  await py.runPythonAsync('import sys,json,gc\nsys.path.insert(0,"/home/pyodide")\nimport raw_interest_request,raw_interest_workflow');
  return py;
 })();
 return runtime;
}
let queue=Promise.resolve();
self.onmessage=event=>{const{id,command,payload}=event.data;queue=queue.catch(()=>{}).then(async()=>{
 try{
  if(!['raw_interest_calculate','raw_interest_inspect','raw_interest_compare'].includes(command))throw Error('Unsupported private raw calculation command.');
  const t=performance.now(),py=await ready(),before=py._module.HEAPU8?.buffer?.byteLength??null;
  py.globals.set('_raw_interest_request_json',JSON.stringify(payload));
  const target=command==='raw_interest_inspect'?'raw_interest_workflow.inspect_request':command==='raw_interest_compare'?'raw_interest_workflow.calculate_request':'raw_interest_request.calculate_request';
  const result=JSON.parse(await py.runPythonAsync('json.dumps('+target+'(json.loads(_raw_interest_request_json)),allow_nan=False)'));
  await py.runPythonAsync('del _raw_interest_request_json\ngc.collect()');
  self.postMessage({id,result,runtime:{elapsed_ms:performance.now()-t,wasm_linear_allocated_before:before,wasm_linear_allocated_after:py._module.HEAPU8?.buffer?.byteLength??null,native_engine_execution:0,public_binary_context_unmodified:true}});
 }catch(error){const raw=String(error.message||error),last=raw.trimEnd().split('\n').pop()||'';console.error(raw);if(runtime){try{const py=await runtime;await py.runPythonAsync("globals().pop(\"_raw_interest_request_json\",None)\ngc.collect()");}catch{}}self.postMessage({id,error:/^(?:[A-Za-z_]\w*\.)*(?:ValueError|UnsupportedProfile): /.test(last)?last.replace(/^(?:[A-Za-z_]\w*\.)*(?:ValueError|UnsupportedProfile): /,''):'Private raw calculation failed.',debug_type:String(error.type||error.name||'Error')});}
 });};
