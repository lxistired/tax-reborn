// Public-safe installed-package smoke: no original/vendor resource bytes.
// This only checks the dedicated source_mc_interest_compare worker's refusal paths.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const root=path.resolve(process.env.TAX_REBORN_RUNTIME_ROOT||path.join(__dirname,'..'));
const out=path.resolve(process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa','source-mc-interest-guards'));
fs.mkdirSync(out,{recursive:true});
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
function environment(tamper=null){
  const worker={console,URL,Uint8Array,TextDecoder,crypto:webcrypto,performance:{now:()=>Date.now()},
    loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide')+path.sep}),
    self:{location:{href:'file://'+path.join(root,'web/mc-interest-runtime/worker.js')}}};
  worker.self.fetch=async resource=>{
    const url=new URL(typeof resource==='string'?resource:resource.url||resource.href,worker.self.location.href);
    const marker='/web/'; const at=url.pathname.indexOf(marker);
    const rel=at>=0?url.pathname.slice(at+marker.length):null;
    if(!rel)return new Response('missing',{status:404});
    const p=path.join(root,'web',rel);
    if(!fs.existsSync(p))return new Response('missing',{status:404});
    let data=fs.readFileSync(p);
    if(rel===tamper)data=Buffer.concat([data,Buffer.from('\npublic-safe-guard-tamper\n')]);
    return new Response(data,{status:200});
  };
  worker.fetch=worker.self.fetch;
  vm.createContext(worker);
  const full=fs.readFileSync(path.join(root,'web/mc-interest-runtime/worker.js'),'utf8');
  const source=full.slice(full.indexOf('const fixedManifestSHA'));
  vm.runInContext(source,worker);
  let serial=0;
  const command=(command,payload)=>new Promise((resolve,reject)=>{
    const id=++serial; const timer=setTimeout(()=>reject(Error('installed source-interest worker timeout')),120000);
    worker.self.postMessage=m=>{if(m.id!==id)return;clearTimeout(timer);m.error?reject(Error(m.error)):resolve(m.result)};
    worker.self.onmessage({data:{id,command,payload}});
  });
  return {command};
}
(async()=>{
  const guards=[];
  await assert.rejects(()=>environment().command('unknown_source_mc_interest_command',{}),e=>{guards.push({case:'unknown-command',error:e.message});return /Unsupported source-interest comparison command/.test(e.message)});
  await assert.rejects(()=>environment().command('source_mc_interest_compare',{}),e=>{guards.push({case:'malformed-request',error:e.message});return !/Traceback/.test(e.message)&&/Exact source\/local-resource L1 request required/.test(e.message)});
  await assert.rejects(()=>environment('mc-interest-runtime/mc-interest-runtime.json').command('source_mc_interest_compare',{}),e=>{guards.push({case:'manifest-tamper',error:e.message});return /changed/.test(e.message)});
  await assert.rejects(()=>environment('mc-interest-runtime/source_calculation_request.py').command('source_mc_interest_compare',{}),e=>{guards.push({case:'module-tamper',error:e.message});return /changed/.test(e.message)});
  const receipt={all_passed:true,actual_installed_source_interest_worker:true,positive_original_resource_tested:false,original_resource_calculation_tested:false,guards,native_runtime:0,original_engine_execution:0,whole_original_compatibility:false};
  fs.writeFileSync(path.join(out,'source-mc-interest-guards-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
  console.log(JSON.stringify(receipt));
})().catch(e=>{console.error(e);process.exitCode=1});
