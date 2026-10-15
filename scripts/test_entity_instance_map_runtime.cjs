// Installed JS and actual Pyodide with wholly owned complete binary sources.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/entity-instance-map-worker');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const ctx={console,URL,URLSearchParams,TextEncoder,crypto:webcrypto,Response,Blob,File,Uint8Array,ArrayBuffer,setTimeout,clearTimeout,location:{href:'http://stage.local/',search:''},btoa:t=>Buffer.from(t,'binary').toString('base64'),atob:t=>Buffer.from(t,'base64').toString('binary')};ctx.window=ctx;vm.createContext(ctx);
for(const name of['local-api.js','investment-corrections.js','income-preparation.js','taxml-import.js'])vm.runInContext(fs.readFileSync(path.join(root,'web',name),'utf8'),ctx,{filename:name});
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
let sequence=0;async function command(command,payload){return new Promise((resolve,reject)=>{const id=++sequence;worker.self.postMessage=m=>{if(m.id===id)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id,command,payload}});});}ctx.taxLocalEngine=command;
async function inspect(req){return ctx.taxMLImport.inspect(new File([Buffer.from(req.base64,'base64')],'owned-instance-maps.taxbin'),new File([JSON.stringify(req.profile)],'profile.json'),req.carriers.map((c,i)=>new File([Buffer.from(c.base64,'base64')],i+'.xprf')),'binary_entity',true);}
(async()=>{
 fs.mkdirSync(out,{recursive:true});const outputs=[],negative=[];
 const expected={1:[8475,'dbfa1b3b4553d9a0787e4c9af0cfd188494f88450758d4325f8052ccb4ba4094'],2:[8460,'496b33a4920a2b19f226130a7ee54b5c44a02075f271221b9810494c085f587a'],3:[8401,'c54d29836fc7f22f03b02d11d8ddac5274815f01bdbe882aeee9b5e13eba171c']};
 const load=v=>JSON.parse(fs.readFileSync(path.join(root,`fixtures/binary-tax/entity-instance-map-v${v}-income-request.json`)));
 for(const v of[1,2,3]){
  const req=load(v),kept=JSON.stringify(req),before=await inspect(req);
  assert.equal(before.binary_archive.forms.length,8);assert.equal(before.binary_archive.formsets,2);assert(before.candidates.every(c=>c.can_review));assert.equal(before.unresolved_facts.length,0);
  const map=before.binary_archive.persistent_objects.entity.objects.find(o=>o.class_id===333);
  assert.equal(map.version,v);assert.equal(map.stored_no_payload,v===3);assert.equal(map.active_native_cache_empty_verified,false);assert.equal(map.native_Load_executed,false);assert.equal(map.native_inventory_verified,false);assert.equal(map.row_editing_supported,false);
  const changes=[{path:[0,0],field_id:'WAGES',element:0,value:'1234.57'}],output=await ctx.taxMLImport.editBinary(before,changes,true),raw=Buffer.from(output.base64,'base64');
  assert.equal(raw.length,expected[v][0]);assert.equal(output.output_sha256,expected[v][1]);assert.equal(JSON.stringify(req),kept);
  const after=await inspect({...req,base64:output.base64});assert.equal(after.candidates[0].amounts.wages,'1234.57');
  assert.equal(output.full_return_recalculated,false);assert.equal(output.original_program_acceptance_verified,false);
  for(const level of['entity',...before.binary_archive.persistent_objects.formsets.map((_,i)=>i)]){
   const a=level==='entity'?before.binary_archive.persistent_objects.entity:before.binary_archive.persistent_objects.formsets[level].persistent_attributes;
   const b=level==='entity'?after.binary_archive.persistent_objects.entity:after.binary_archive.persistent_objects.formsets[level].persistent_attributes;
   assert.equal(a.sha256,b.sha256);assert.equal(b.source_position-a.source_position,2);
   assert.deepEqual(JSON.parse(JSON.stringify(a.objects.map(({source_position,...other})=>other))),JSON.parse(JSON.stringify(b.objects.map(({source_position,...other})=>other))));
  }
  fs.writeFileSync(path.join(out,`entity-instance-map-v${v}-corrected.taxbin`),raw);
  outputs.push({version:v,bytes:raw.length,sha256:output.output_sha256,all_three_persistent_layers_moved_by:2});
  await assert.rejects(()=>ctx.taxMLImport.editBinary({...before},changes,true));negative.push('detached-receipt-v'+v);
  await assert.rejects(()=>ctx.taxMLImport.editBinary(before,changes,false));negative.push('unconfirmed-v'+v);
 }
 const name=Buffer.from('TpsInstanceToMefInstanceMapPO');
 const mutate=(v,fn)=>{const r=load(v),b=Buffer.from(r.base64,'base64'),at=b.indexOf(name)+name.length;assert(at>=name.length);fn(b,at);r.base64=b.toString('base64');return r;};
 for(const mode of['unknown-version','compressed-count0','wrong-class']){
  const req=mutate(2,(b,at)=>{if(mode==='unknown-version')b.writeUInt16BE(4,at);else if(mode==='compressed-count0')b.writeUInt32BE(0,at+2);else b[at-name.length]=88;}),view=await inspect(req);
  assert(view.candidates.every(c=>!c.can_review));assert(view.unresolved_facts.length>0);await assert.rejects(()=>ctx.taxMLImport.editBinary(view,[{path:[0,0],field_id:'WAGES',element:0,value:'1234.57'}],true));negative.push(mode);
 }
 for(const [v,mode]of[[1,'legacy-count'],[1,'legacy-final-NUL'],[2,'compressed-count'],[2,'compressed-CRC']]){
  await assert.rejects(()=>inspect(mutate(v,(b,at)=>{if(mode.endsWith('count'))b.writeUInt32BE(9,at+2);else if(v===1){const req=load(v);const original=Buffer.from(req.base64,'base64');const oldbody=original.subarray(at);const end=oldbody.indexOf(Buffer.from('/OWNED/MEF/v1/B'))+'/OWNED/MEF/v1/B'.length;b[at+end]=88;}else b[at+16]^=1;})));negative.push(mode);
 }
 const receipt={real_JS_and_Pyodide:true,actual_WeakMap_receipts:true,whole_owned_source_read_modify_read:true,outputs,refusals:negative.length,refusal_cases:negative,source_profiles_and_carriers_unchanged:true,Entity_FormSet_and_ValueForm_raw_objects_retained:true,full32ID_and_currentordinal_binding_preserved:true,v3_stored_no_payload_not_active_empty:true,native_Load_executed:false,native_cleanup_executed:false,native_14F_transfer_executed:false,native_current_cache_verified:false,native_inventory_verified:false,original_taxpayer_fixture_count:0};
 fs.writeFileSync(path.join(out,'entity-instance-map-worker-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(error=>{console.error(error);process.exitCode=1;});
