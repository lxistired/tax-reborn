function sourceCalculationError(error){
 const message=String(error?.message||error);
 if(error?.name!=='PythonError')return message;
 const type=String(error.type||'').split('.').pop(),last=message.trimEnd().split('\n').pop()||'';
 const expected=last.match(/^(?:[A-Za-z_]\w*\.)*(ValueError|UnsupportedProfile): (.+)$/);
 if(expected&&expected[1]===type)return expected[2];
 console.error('Local comparison exception',message);
 return 'Local comparison could not complete. Keep the source files and try again.';
}
'';
// Independent local worker. Existing tax-worker.js is not changed.
let runtime;
const digest=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');
function ready(){
  if(!runtime)runtime=(async()=>{
    const base=new URL('./',self.location.href);
    const py=await loadPyodide({indexURL:new URL('vendor/pyodide/',base).href});
    const response=await fetch(new URL('source-calculation-runtime.json',base));
    if(!response.ok)throw Error('Local comparison runtime is missing.');
    const manifest=await response.json();
    if(manifest.format!=='tax-reborn-local-source-runtime-v1'||!Array.isArray(manifest.files)||manifest.files.length>100)throw Error('Unsupported local comparison runtime.');
    const files=await Promise.all(manifest.files.map(async row=>{
      if(!/^(?:[a-z_0-9-]+\.(?:py|json)|interop\/(?:__init__|(?:form_core|derived_form)\/[a-z_0-9]+)\.py)$/.test(row.path))throw Error('Invalid local runtime path.');
      const response=await fetch(new URL(row.path,base));if(!response.ok)throw Error('Missing local comparison file: '+row.path);
      const bytes=new Uint8Array(await response.arrayBuffer());
      if(await digest(bytes)!==row.sha256)throw Error('Local comparison runtime hash mismatch.');
      return [row.path,bytes];
    }));
    py.FS.mkdirTree('/home/pyodide/interop/form_core');py.FS.mkdirTree('/home/pyodide/interop/derived_form');
    for(const [path,bytes] of files)py.FS.writeFile('/home/pyodide/'+path,bytes);
    await py.runPythonAsync('import sys,json\nsys.path.insert(0,"/home/pyodide")\nimport source_calculation_command,tax_engine');
    return py;
  })();
  return runtime;
}
let queue=Promise.resolve();
self.onmessage=event=>{
  const {id,command,payload}=event.data;
  queue=queue.catch(()=>{}).then(async()=>{
    try{
      const py=await ready();py.globals.set('_source_input_json',JSON.stringify(payload));
      const expressions={source_calculation_inspect:'source_calculation_command.inspect_source(json.loads(_source_input_json))',
        source_calculation_compare:'source_calculation_command.compare_source(json.loads(_source_input_json))',
        current_app_calculate:'source_calculation_command.current_app_snapshot(json.loads(_source_input_json))'};
      if(!Object.hasOwn(expressions,command))throw Error('Unsupported local comparison command.');
      const result=JSON.parse(await py.runPythonAsync('json.dumps('+expressions[command]+',allow_nan=False)'));
      self.postMessage({id,result});
    }catch(error){self.postMessage({id,error:sourceCalculationError(error)});}
  });
};
