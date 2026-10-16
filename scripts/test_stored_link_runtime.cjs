// Actual local JS/Pyodide command, complete independently owned source inputs.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/stored-link-worker');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const ctx={console,URL,URLSearchParams,TextEncoder,crypto:webcrypto,Response,Blob,File,Uint8Array,ArrayBuffer,setTimeout,clearTimeout,location:{href:'http://stage.local/',search:''},btoa:t=>Buffer.from(t,'binary').toString('base64'),atob:t=>Buffer.from(t,'base64').toString('binary')};ctx.window=ctx;vm.createContext(ctx);
for(const name of['local-api.js','investment-corrections.js','income-preparation.js','taxml-import.js'])vm.runInContext(fs.readFileSync(path.join(root,'web',name),'utf8'),ctx,{filename:name});
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
let sequence=0;async function command(command,payload){return new Promise((resolve,reject)=>{const id=++sequence;worker.self.postMessage=m=>{if(m.id===id)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id,command,payload}});});}ctx.taxLocalEngine=command;
const plain=value=>JSON.parse(JSON.stringify(value));
(async()=>{
 fs.mkdirSync(out,{recursive:true});const req=JSON.parse(fs.readFileSync(path.join(root,'fixtures/binary-tax/owned-existing-link-request.json'))),expected=JSON.parse(fs.readFileSync(path.join(root,'fixtures/binary-tax/owned-existing-link-expected.json'))),before=JSON.stringify(req);
 const view=await ctx.taxMLImport.inspect(new File([Buffer.from(req.base64,'base64')],'owned-existing-link.taxbin'),new File([JSON.stringify(req.profile)],'profile.json'),req.carriers.map((x,i)=>new File([Buffer.from(x.base64,'base64')],i+'.xprf')),'binary_entity',true);
 assert.equal(view.binary_archive.forms.length,2);const result=plain(await ctx.taxMLImport.storedLinkDiagnostics(view));assert.deepEqual(result,expected);assert.equal(JSON.stringify(req),before);
 await assert.rejects(()=>ctx.taxMLImport.storedLinkDiagnostics({...view}));const refused=['detached_inspection'];
 for(const key of['native_inventory_verified','trusted_profile','prepared_descriptor','owner_present']){await assert.rejects(()=>command('source_link_diagnostics',{...req,[key]:true}),e=>!e.message.includes('Traceback'));refused.push(key);}
 const bad=plain(req);bad.carriers[0].base64=Buffer.from('different source resource bytes').toString('base64');await assert.rejects(()=>command('source_link_diagnostics',bad));refused.push('changed_carrier_bytes');
 const manual=plain(req);manual.profile.format='tax-reborn-binary-entity-profile-v4';manual.profile.compiled_arrays=manual.profile.templates.map(x=>({formset_id:x.formset_id,form_id:x.form_id,visible:[],hidden:[]}));await assert.rejects(()=>command('source_link_diagnostics',manual));refused.push('manual_arrays');
 assert.deepEqual(plain(await command('source_link_diagnostics',req)),expected);assert.deepEqual(plain(await ctx.taxMLImport.storedLinkDiagnostics(view)),expected);
 const receipt={all_passed:true,actual_JS_and_Pyodide:true,actual_WeakMap_request:true,complete_owned_source_bytes:713,full_diagnostic_equal: true,refusals:refused,same_worker_recovered_after_bad_input:true,source_profile_carriers_unchanged:true,native_inventory_verified:false,writeback_allowed:false,original_resource_payload:false};
 fs.writeFileSync(path.join(out,'stored-link-runtime-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(error=>{console.error(error);process.exitCode=1;});
