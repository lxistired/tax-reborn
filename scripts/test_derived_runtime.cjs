// Installed worker + real WebAssembly + the same reviewed-record contracts as UI.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/binary-derived');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const ctx={console,URL,URLSearchParams,TextEncoder,crypto:webcrypto,Response,Blob,File,Uint8Array,ArrayBuffer,setTimeout,clearTimeout,location:{href:'http://stage.local/',search:''},btoa:t=>Buffer.from(t,'binary').toString('base64'),atob:t=>Buffer.from(t,'base64').toString('binary')};ctx.window=ctx;vm.createContext(ctx);
for(const name of ['local-api.js','investment-corrections.js','income-preparation.js','taxml-import.js'])vm.runInContext(fs.readFileSync(path.join(root,'web',name),'utf8'),ctx,{filename:name});
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
let sequence=0;async function command(command,payload){return new Promise((resolve,reject)=>{const id=++sequence;worker.self.postMessage=m=>{if(m.id===id)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id,command,payload}});});}ctx.taxLocalEngine=command;
async function inspect(request){return ctx.taxMLImport.inspect(new File([Buffer.from(request.base64,'base64')],'synthetic.taxbin'),new File([JSON.stringify(request.profile)],'profile.json'),request.carriers.map((c,i)=>new File([Buffer.from(c.base64,'base64')],i+'.xprf')),'binary_entity',true);}
async function main(){
 fs.mkdirSync(out,{recursive:true});const req=JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/derived-income-request.json'))),before=await inspect(req);
 assert.equal(before.candidates.length,4);assert(before.candidates.every(c=>c.can_review));assert.equal(before.unresolved_facts.length,0);
 const forms=before.binary_archive.forms,wages=forms[0].fields.find(f=>f.field_id==='WAGES');assert.equal(wages.ordinal,104);assert.equal(wages.current_ordinal,4);
 assert.equal(forms[0].table_headers[0].table_kind,'value_table');assert.equal(forms.reduce((n,f)=>n+f.links.length,0),4);assert(forms.every(f=>f.derived.groups.length===3));
 const schema=await command('schema'),data=JSON.parse(JSON.stringify(schema.default_return)),metadata=ctx.taxRecordMetadata.empty();ctx.taxRecordMetadata.setDefaults(schema.capabilities.row_templates.w2);
 for(const candidate of before.candidates){let collection,prepared;const source={document_id:webcrypto.randomUUID(),return_id:webcrypto.randomUUID(),name:'owned-derived.taxbin'};
  if(candidate.record_type==='w2'){collection='w2';prepared=await ctx.taxMLImport.reviewedRecord(candidate,{...candidate.amounts,owner:'taxpayer',employer:'Owned Derived Employer',social_security_tips:'0',dependent_care_benefits:'0'},source,true,schema.capabilities.row_templates.w2);metadata.w2_records.push(prepared.metadata);}
  else if(candidate.record_type==='interest'){collection='interest';prepared=await ctx.taxMLImport.reviewedInterest(candidate,{...candidate.amounts,payer:'Owned Bank',supported_scope:true},source,true);metadata.income_document_records.interest.push(prepared.metadata);}
  else{collection='dividends';prepared=await ctx.taxMLImport.reviewedDividend(candidate,{...candidate.amounts,payer:'Owned Fund',supported_scope:true,qualified_eligibility:true},source,true);metadata.income_document_records.dividends.push(prepared.metadata);}
  data[collection].push(prepared.row);
 }
 const normalized=await ctx.taxRecordMetadata.normalize(data,metadata),calculation=await command('calculate',data);assert.equal(calculation.summary.refund,344);assert.equal(calculation.can_prepare,false);
 const changes=[{path:[0,0],field_id:'WAGES',element:0,value:'1234567.89'}];await assert.rejects(()=>ctx.taxMLImport.editBinary(before,changes,false));
 const output=await ctx.taxMLImport.editBinary(before,changes,true),after=await inspect({...req,base64:output.base64});
 assert.equal(after.candidates[0].amounts.wages,'1234567.89');assert(output.binary_roundtrip_verified);assert.equal(output.full_return_recalculated,false);
 assert.notEqual(Buffer.from(req.base64,'base64').length,Buffer.from(output.base64,'base64').length);
 for(let i=0;i<forms.length;i++){assert.equal(forms[i].derived.sha256,after.binary_archive.forms[i].derived.sha256);assert.notEqual(forms[i].derived.source_position,after.binary_archive.forms[i].derived.source_position);assert.deepEqual(JSON.parse(JSON.stringify(forms[i].table_headers)),JSON.parse(JSON.stringify(after.binary_archive.forms[i].table_headers)));}
 const array=await inspect(JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/derived-array-request.json'))));assert(array.candidates.every(c=>!c.can_review));assert.equal(array.unresolved_facts.length,2);
 const opaque=await inspect(JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/derived-opaque-request.json'))));assert.deepEqual(Array.from(opaque.binary_archive.forms[0].derived.groups,g=>g.objects.length),[2,1,1]);assert(opaque.candidates.every(c=>!c.can_review));await assert.rejects(()=>ctx.taxMLImport.editBinary(opaque,changes,true));
 fs.writeFileSync(path.join(out,'derived-corrected.taxbin'),Buffer.from(output.base64,'base64'));
 const receipt={real_pyodide_worker:true,source_ordinal:104,current_ordinal:4,three_income_types_reviewed:true,actual_refund:calculation.summary.refund,complete_derived_forms:forms.length,nonempty_table_child_links:true,D2_and_three_groups_inspected:true,four_typed_UUID_tails_moved:true,unknown_opaque_movement_refused:true,unknown_arrays_block_income:true,complete_export_readback:true,source_receipts_retained:normalized.w2_records.length+normalized.income_document_records.interest.length+normalized.income_document_records.dividends.length,original_engine_executed:false,whole_tax_compatibility:false};fs.writeFileSync(path.join(out,'derived-worker-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
}main().catch(error=>{console.error(error);process.exitCode=1;});
