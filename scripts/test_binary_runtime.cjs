// Installed worker + real WebAssembly + the same reviewed-record contracts as UI.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/binary-tax');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const ctx={console,URL,URLSearchParams,TextEncoder,crypto:webcrypto,Response,Blob,File,Uint8Array,ArrayBuffer,setTimeout,clearTimeout,location:{href:'http://stage.local/',search:''},btoa:t=>Buffer.from(t,'binary').toString('base64'),atob:t=>Buffer.from(t,'base64').toString('binary')};ctx.window=ctx;vm.createContext(ctx);
for(const name of ['local-api.js','investment-corrections.js','income-preparation.js','taxml-import.js'])vm.runInContext(fs.readFileSync(path.join(root,'web',name),'utf8'),ctx,{filename:name});
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
let sequence=0;async function command(command,payload){return new Promise((resolve,reject)=>{const id=++sequence;worker.self.postMessage=m=>{if(m.id===id)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id,command,payload}});});}ctx.taxLocalEngine=command;
async function inspect(request){return ctx.taxMLImport.inspect(new File([Buffer.from(request.base64,'base64')],'synthetic.taxbin'),new File([JSON.stringify(request.profile)],'profile.json'),request.carriers.map((c,i)=>new File([Buffer.from(c.base64,'base64')],i+'.xprf')),'binary_entity',true);}
async function main(){
 fs.mkdirSync(out,{recursive:true});
 const request=JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/income-request.json'))),income=await inspect(request);
 assert.equal(income.candidates.length,3);assert(income.candidates.every(c=>c.can_review));
 const schema=await command('schema'),data=JSON.parse(JSON.stringify(schema.default_return)),metadata=ctx.taxRecordMetadata.empty();ctx.taxRecordMetadata.setDefaults(schema.capabilities.row_templates.w2);
 for(const candidate of income.candidates){
  const source={document_id:webcrypto.randomUUID(),return_id:webcrypto.randomUUID(),name:'synthetic.taxbin'};
  let prepared,collection;
  if(candidate.record_type==='w2'){collection='w2';prepared=await ctx.taxMLImport.reviewedRecord(candidate,{...candidate.amounts,owner:'taxpayer',employer:'Synthetic Binary Employer',social_security_tips:'0',dependent_care_benefits:'0'},source,true,schema.capabilities.row_templates.w2);metadata.w2_records.push(prepared.metadata);}
  else if(candidate.record_type==='interest'){collection='interest';prepared=await ctx.taxMLImport.reviewedInterest(candidate,{...candidate.amounts,payer:'Synthetic Binary Bank',supported_scope:true},source,true);metadata.income_document_records.interest.push(prepared.metadata);}
  else{collection='dividends';prepared=await ctx.taxMLImport.reviewedDividend(candidate,{...candidate.amounts,payer:'Synthetic Binary Fund',supported_scope:true,qualified_eligibility:true},source,true);metadata.income_document_records.dividends.push(prepared.metadata);}
  data[collection].push(prepared.row);assert.equal(prepared.metadata.reviewed,true);assert.equal(prepared.metadata.source_document.taxml_receipt.source_sha256,income.source_sha256);
 }
 const normalized=await ctx.taxRecordMetadata.normalize(data,metadata),calculated=await command('calculate',data);assert.equal(calculated.can_prepare,false);assert.equal(data.eligibility.all_income_reported,false);assert.equal(calculated.summary.refund,344);
 const nestedRequest=JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/nested-request.json'))),nested=await inspect(nestedRequest),forms=nested.binary_archive.forms;
 assert(forms.some(f=>f.tables>0));assert(forms.some(f=>f.children>0));assert(forms.some(f=>f.links.length>0));
 const form=forms.find(f=>f.fields.some(v=>v.editable)),field=form.fields.find(v=>v.editable),changes=[{path:form.path,ordinal:field.ordinal,element:field.element,value:'345.67'}];
 await assert.rejects(()=>ctx.taxMLImport.editBinary(nested,changes,false));await assert.rejects(()=>ctx.taxMLImport.editBinary({...nested},changes,true));
 const edited=await ctx.taxMLImport.editBinary(nested,changes,true);assert.equal(edited.changed_fields,1);assert.equal(edited.binary_roundtrip_verified,true);assert.equal(edited.all_other_parsed_facts_preserved,true);assert.equal(edited.full_return_recalculated,false);assert.equal(edited.original_program_acceptance_verified,false);
 fs.writeFileSync(path.join(out,'nested-corrected.taxbin'),Buffer.from(edited.base64,'base64'));
 const reopened=await inspect({...nestedRequest,base64:edited.base64}),a=JSON.parse(JSON.stringify(forms)),b=JSON.parse(JSON.stringify(reopened.binary_archive.forms));
 const original=a.find(f=>JSON.stringify(f.path)===JSON.stringify(form.path)).fields.find(f=>f.ordinal===field.ordinal&&f.element===field.element),updated=b.find(f=>JSON.stringify(f.path)===JSON.stringify(form.path)).fields.find(f=>f.ordinal===field.ordinal&&f.element===field.element);assert.equal(updated.text,'345.67');original.text=updated.text;original.raw64=updated.raw64;assert.deepEqual(a,b);
 const receipt={runtime_root:root,actual_packaged_assets:!!process.env.TAX_REBORN_RUNTIME_ROOT,real_pyodide:true,three_reviewed_binary_income_forms:true,actual_calculation:calculated.summary,unconfirmed_income_still_blocks_completion:true,normalized_source_records:normalized.w2_records.length+normalized.income_document_records.interest.length+normalized.income_document_records.dividends.length,nonempty_tables_children_links:true,whole_document_edit_readback:true,other_parsed_facts_preserved:true,original_tax_fixture:false,original_engine_executed:false,whole_tax_compatibility:false};fs.writeFileSync(path.join(out,'binary-runtime-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
}main().catch(error=>{console.error(error);process.exitCode=1;});
