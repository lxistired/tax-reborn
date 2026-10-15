// Installed JS and actual Pyodide with wholly owned complete binary sources.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/instance-map-worker');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const ctx={console,URL,URLSearchParams,TextEncoder,crypto:webcrypto,Response,Blob,File,Uint8Array,ArrayBuffer,setTimeout,clearTimeout,location:{href:'http://stage.local/',search:''},btoa:t=>Buffer.from(t,'binary').toString('base64'),atob:t=>Buffer.from(t,'base64').toString('binary')};ctx.window=ctx;vm.createContext(ctx);
for(const name of['local-api.js','investment-corrections.js','income-preparation.js','taxml-import.js'])vm.runInContext(fs.readFileSync(path.join(root,'web',name),'utf8'),ctx,{filename:name});
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
let sequence=0;async function command(command,payload){return new Promise((resolve,reject)=>{const id=++sequence;worker.self.postMessage=m=>{if(m.id===id)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id,command,payload}});});}ctx.taxLocalEngine=command;
async function inspect(req){return ctx.taxMLImport.inspect(new File([Buffer.from(req.base64,'base64')],'owned-instance-maps.taxbin'),new File([JSON.stringify(req.profile)],'profile.json'),req.carriers.map((c,i)=>new File([Buffer.from(c.base64,'base64')],i+'.xprf')),'binary_entity',true);}
(async()=>{
 fs.mkdirSync(out,{recursive:true});const req=JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/instance-map-income-request.json'))),before=await inspect(req);
 assert.equal(before.binary_archive.forms.length,8);assert.equal(before.binary_archive.formsets,2);assert(before.candidates.every(c=>c.can_review));assert.equal(before.unresolved_facts.length,0);
 const groups=before.binary_archive.persistent_objects.formsets,classes=groups.map(f=>f.persistent_attributes.objects.find(o=>o.kind==='stored_instance_map'));
 assert(classes.every(o=>o.relocatable&&o.rows.length===3&&!o.native_current_cache_verified&&!o.native_cleanup_executed&&!o.native_14D_transfer_executed));
 const changes=[{path:[0,0],field_id:'WAGES',element:0,value:'1234.57'}],output=await ctx.taxMLImport.editBinary(before,changes,true),after=await inspect({...req,base64:output.base64});
 assert.equal(output.output_sha256,'da0b62b035b3f1332719b9f38428c98eea6d7c0fd48e6f8ee0ae4d6777711a54');assert.equal(Buffer.from(output.base64,'base64').length,8360);assert.equal(after.candidates[0].amounts.wages,'1234.57');assert.equal(output.original_program_acceptance_verified,false);assert.equal(output.full_return_recalculated,false);
 for(let i=0;i<2;i++){const a=groups[i].persistent_attributes,b=after.binary_archive.persistent_objects.formsets[i].persistent_attributes;assert.equal(a.sha256,b.sha256);assert.equal(b.source_position-a.source_position,2);assert.deepEqual(JSON.parse(JSON.stringify(a.objects.map(({source_position,...other})=>other))),JSON.parse(JSON.stringify(b.objects.map(({source_position,...other})=>other))));}
 let refused=0;const reject=async f=>{await assert.rejects(f);refused++;};await reject(()=>ctx.taxMLImport.editBinary(before,changes,false));await reject(()=>ctx.taxMLImport.editBinary({...before},changes,true));
 const name=Buffer.from('TpsInstanceToMefInstanceMapFormSetPO');function mutation(fn){const r=JSON.parse(JSON.stringify(req)),b=Buffer.from(req.base64,'base64');fn(b);r.base64=b.toString('base64');return r;}
 for(const mode of['unknown-version','zero-count','unknown-class']){
  const r=mutation(b=>{const at=b.indexOf(name);if(mode==='unknown-class')b[at]=88;else if(mode==='unknown-version')b.writeUInt16BE(2,at+name.length);else b.writeUInt32BE(0,at+name.length+2);}),view=await inspect(r);
  assert(view.candidates.every(c=>!c.can_review));assert(view.unresolved_facts.length>0);await reject(()=>ctx.taxMLImport.editBinary(view,changes,true));
 }
 for(const mode of['first-CRC','last-payload','wrong-count'])await reject(()=>inspect(mutation(b=>{const at=(mode==='last-payload'?b.lastIndexOf(name):b.indexOf(name))+name.length;if(mode==='first-CRC')b[at+16]^=1;else if(mode==='wrong-count')b.writeUInt32BE(4,at+2);else{const size=b.readUInt32BE(at+6);b[at+9+size]=0;}})));
 fs.writeFileSync(path.join(out,'instance-map-corrected.taxbin'),Buffer.from(output.base64,'base64'));
 const receipt={real_JS_and_Pyodide:true,actual_packaged_assets:!!process.env.TAX_REBORN_RUNTIME_ROOT,refusals:refused,whole_output_bytes:8360,sha256:output.output_sha256,FormSets:2,forms:8,links:8,stored_maps:2,stored_pair_rows:6,both_0F_and_F0_original_body_bytes_retained:true,all_persistent_layers_moved_by:2,unknown_versions_empty_counts_and_classes_stay_opaque:true,malformed_last_instance_refused:true,native_cleanup_executed:false,native_current_cache_verified:false,original_runtime:0,full_original_compatibility:false};
 fs.writeFileSync(path.join(out,'instance-map-worker-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(error=>{console.error(error);process.exitCode=1;});
