// Real installed Python/Wasm reader. Only owned invalid bytes are used here.
// Complete original-resource calculations have separate private acceptance.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto,createHash}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..');
const out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/raw-interest-runtime');
const runtime=path.join(root,'web/raw-interest-runtime');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const observed=[],diagnostics=[];
const worker={console:{...console,error:message=>diagnostics.push(String(message))},URL,Uint8Array,TextDecoder,performance,crypto:webcrypto,
 self:{location:{href:'http://owned.local/raw-interest-runtime/raw-interest-worker.js'}},
 loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),
 fetch:async value=>{const file=path.join(root,'web',new URL(value).pathname.slice(1));return fs.existsSync(file)?new Response(fs.readFileSync(file)):new Response('missing',{status:404});}};
vm.createContext(worker);
vm.runInContext(fs.readFileSync(path.join(runtime,'raw-interest-worker-source.js'),'utf8'),worker);
let sequence=0;
async function command(command,payload){return new Promise((resolve,reject)=>{
 const id=++sequence;const timer=setTimeout(()=>reject(Error('Installed raw reader did not respond')),120000);
 worker.self.postMessage=message=>{if(message.id===id){clearTimeout(timer);observed.push(message);resolve(message);}};
 worker.self.onmessage({data:{id,command,payload}});
});}
(async()=>{
 const bytes=Buffer.from('Wholly owned invalid resource; never vendor code.');
 const base64=bytes.toString('base64'),sha256=createHash('sha256').update(bytes).digest('hex');
 const pair={source:{},local_resource:{base64,sha256},field_resource:{base64,sha256}};
 let result=await command('raw_interest_inspect',pair);
 assert.equal(result.error,'Choose the exact host-approved local original resource');
 // Matching a claimed digest cannot authorize different actual bytes.
 const authority=JSON.parse(fs.readFileSync(path.join(runtime,'raw-interest-authority.json')));
 pair.local_resource.sha256=authority.resource.carrier_sha256;
 result=await command('raw_interest_inspect',pair);
 assert.equal(result.error,'Caller-local resource content differs from approved identity');
 // The proposed-adjustment path has its own inspection session. No supplied
 // confirmation or amount can replace that inspection, even after a refusal.
 result=await command('raw_interest_inspect_cs24',pair);
 assert.equal(result.error,'Caller-local resource content differs from approved identity');
 result=await command('raw_interest_compare_cs24',{pair,inspection_token:'uninspected',confirmed:true});
 assert.equal(result.error,'Source or resources changed; inspect and confirm them again');
 result=await command('raw_interest_compare_cs24',{pair,inspection_token:'uninspected',confirmed:true,temporary_amounts:{TEMPA:'12.34'}});
 assert.equal(result.error,'Confirm the current same-source inspection before comparison');
 result=await command('raw_interest_inspect_cs24',pair);
 assert.equal(result.error,'Caller-local resource content differs from approved identity');
 result=await command('owned_unsupported_command',{});
 assert.equal(result.error,'Private raw calculation failed.');
 assert.equal(result.debug_type,'Error');
 assert(diagnostics.includes('Unsupported private raw calculation command.'));
 result=await command('raw_interest_inspect',pair);
 assert.equal(result.error,'Caller-local resource content differs from approved identity');
 const manifest=JSON.parse(fs.readFileSync(path.join(runtime,'raw-interest-runtime.json')));
 const receipt={all_passed:true,actual_worker_source:true,real_Pyodide:true,
   runtime_scope:process.env.TAX_REBORN_RUNTIME_ROOT?'caller-selected packaged assets':'source checkout',
   native_installation_verified_by_this_script:false,
   complete_owned_module_manifest_loaded_and_hash_verified:true,owned_runtime_files:manifest.files.length,
   original_resources_installed:false,owned_invalid_resources_only:true,
   claimed_digest_cannot_replace_actual_resource_bytes:true,same_worker_recovers_after_refusal:true,
   proposed_adjustments_require_separate_same_source_inspection:true,
   supplied_temporary_amounts_refused:true,
   errors_returned:observed.length,original_engine_execution:0,
   original_resource_calculation_tested:false,native_GUI_tested:false,full_original_compatibility:false};
 fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'raw-interest-runtime-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
 console.log(JSON.stringify(receipt));
})().catch(error=>{console.error(error);for(const message of diagnostics)console.error(message);process.exitCode=1;});
