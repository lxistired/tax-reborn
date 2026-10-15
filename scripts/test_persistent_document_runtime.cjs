// Installed worker + real WebAssembly + the same reviewed-record contracts as UI.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/binary-persistent-document');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const ctx={console,URL,URLSearchParams,TextEncoder,crypto:webcrypto,Response,Blob,File,Uint8Array,ArrayBuffer,setTimeout,clearTimeout,location:{href:'http://stage.local/',search:''},btoa:t=>Buffer.from(t,'binary').toString('base64'),atob:t=>Buffer.from(t,'base64').toString('binary')};ctx.window=ctx;vm.createContext(ctx);
for(const name of ['local-api.js','investment-corrections.js','income-preparation.js','taxml-import.js'])vm.runInContext(fs.readFileSync(path.join(root,'web',name),'utf8'),ctx,{filename:name});
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
const originalFormatter=worker.taxWorkerError;worker.taxWorkerError=error=>{fs.mkdirSync(out,{recursive:true});fs.appendFileSync(path.join(out,'error-type-observations.jsonl'),JSON.stringify({name:error.name,type:error.type,last:String(error.message).trimEnd().split('\n').pop()})+'\n');return originalFormatter(error);};
let sequence=0;async function command(command,payload){return new Promise((resolve,reject)=>{const id=++sequence;worker.self.postMessage=m=>{if(m.id===id)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id,command,payload}});});}ctx.taxLocalEngine=command;
async function inspect(request){return ctx.taxMLImport.inspect(new File([Buffer.from(request.base64,'base64')],'synthetic.taxbin'),new File([JSON.stringify(request.profile)],'profile.json'),request.carriers.map((c,i)=>new File([Buffer.from(c.base64,'base64')],i+'.xprf')),'binary_entity',true);}
async function main(){
 fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'error-type-observations.jsonl'),'');
 const req=JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/persistent-document-income-request.json'))),before=await inspect(req);
 assert.equal(before.candidates.length,8);assert(before.candidates.every(c=>c.can_review));assert.equal(before.unresolved_facts.length,0);
 const forms=before.binary_archive.forms,objects=before.binary_archive.persistent_objects;
 assert.equal(forms.length,8);assert.equal(before.binary_archive.formsets,2);assert.equal(objects.entity.objects.length,3);assert.equal(objects.formsets.length,2);
 assert(objects.formsets.every(fs=>fs.persistent_attributes.objects.length===2));
 const changes=[{path:[0,0],field_id:'WAGES',element:0,value:'1234.57'}];
 function mutate(fn){const r=JSON.parse(JSON.stringify(req)),wire=Buffer.from(r.base64,'base64');fn(wire,r);r.base64=wire.toString('base64');return r;}
 const bad=[mutate(w=>w[objects.entity.source_position]=0),mutate(w=>w[objects.formsets[0].persistent_attributes.source_position]=0),
  mutate(w=>{const n=Buffer.from('zccPersisUUID'),at=w.indexOf(n)+n.length;w[at]++;}),
  mutate(w=>{const n=Buffer.from('MetaDataKeyValueFormSetPO'),at=w.indexOf(n)+n.length;w.writeUInt16BE(3,at);}),
  mutate((w,r)=>r.profile.formset_factories=[]),mutate((w,r)=>r.profile.entity_factory='base_entity')];
 for(const r of bad)await assert.rejects(()=>inspect(r));
 const output=await ctx.taxMLImport.editBinary(before,changes,true),after=await inspect({...req,base64:output.base64});
 assert.equal(after.candidates[0].amounts.wages,'1234.57');assert.equal(output.output_sha256,'c5bdc13fb5bdd8cb435e4e2eaad2fdb21077b5024a28e89e8b1bbcbc0e30ba26');assert.equal(Buffer.from(output.base64,'base64').length,8110);
 function compareGroup(a,b){assert.equal(a.sha256,b.sha256);assert.deepEqual(Array.from(a.relative_offsets),Array.from(b.relative_offsets));assert.equal(b.source_position-a.source_position,2);
  assert.deepEqual(JSON.parse(JSON.stringify(a.objects.map(({source_position,...rest})=>rest))),JSON.parse(JSON.stringify(b.objects.map(({source_position,...rest})=>rest))));assert(b.objects.every(o=>!o.active_native_value));}
 compareGroup(objects.entity,after.binary_archive.persistent_objects.entity);for(let i=0;i<2;i++)compareGroup(objects.formsets[i].persistent_attributes,after.binary_archive.persistent_objects.formsets[i].persistent_attributes);
 for(let i=0;i<forms.length;i++){assert.equal(forms[i].derived.sha256,after.binary_archive.forms[i].derived.sha256);assert.equal(after.binary_archive.forms[i].derived.source_position-forms[i].derived.source_position,2);assert.deepEqual(JSON.parse(JSON.stringify(forms[i].links)),JSON.parse(JSON.stringify(after.binary_archive.forms[i].links)));}
 for(const n of ['zccPersistentEntityUUID','zccPersistentFormSetUUID']){
  const r=mutate(w=>w[w.indexOf(Buffer.from(n))]=88),v=await inspect(r);assert(v.candidates.every(c=>!c.can_review));await assert.rejects(()=>ctx.taxMLImport.editBinary(v,changes,true));
 }
 const legacy=mutate(w=>{const n=Buffer.from('MetaDataKeyValuePersistentObject');w.writeUInt16BE(1,w.indexOf(n)+n.length);}),v=await inspect(legacy);assert(v.candidates.every(c=>!c.can_review));await assert.rejects(()=>ctx.taxMLImport.editBinary(v,changes,true));
 fs.writeFileSync(path.join(out,'persistent-document-corrected.taxbin'),Buffer.from(output.base64,'base64'));
 const receipt={real_pyodide_worker:true,malformed_refusals:bad.length,unknown_scope_relocation_refusals:2,unmodeled_14B_original_version_refused_on_move:true,formsets:2,forms:8,whole_document_bytes:8110,sha256:output.output_sha256,all_eight_tails_and_Entity_FormSet_bodies_retained:true,all_layers_moved_by:2,active_metadata_executed:false,original_engine_executed:false,whole_original_tax_compatibility:false};
 fs.writeFileSync(path.join(out,'persistent-document-worker-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
}main().catch(error=>{console.error(error);process.exitCode=1;});
