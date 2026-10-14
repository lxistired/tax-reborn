// Actual staged worker source + pinned Pyodide + JS reviewed-record contracts.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..');
const fixtureRoot=process.env.TAX_REBORN_FIXTURE_ROOT||path.join(root,'fixtures/taxml');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const context={console,URL,URLSearchParams,TextEncoder,crypto:webcrypto,Response,Blob,File,Uint8Array,ArrayBuffer,
 setTimeout,clearTimeout,location:{href:'http://stage.local/',search:''},btoa:text=>Buffer.from(text,'binary').toString('base64'),atob:text=>Buffer.from(text,'base64').toString('binary')};
context.window=context;
vm.createContext(context);
for(const name of ['local-api.js','investment-corrections.js','income-preparation.js','taxml-import.js'])vm.runInContext(fs.readFileSync(path.join(root,'web',name),'utf8'),context,{filename:name});
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},
 loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),
 fetch:async url=>{const name=new URL(url).pathname.slice(1);const target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);
vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker,{filename:'tax-worker-source.js'});
let id=0;
async function command(command,payload){return new Promise((resolve,reject)=>{const current=++id;worker.self.postMessage=message=>{if(message.id!==current)return;message.error?reject(Error(message.error)):resolve(message.result);};worker.self.onmessage({data:{id:current,command,payload}});});}
async function main(){
 const request=JSON.parse(fs.readFileSync(path.join(fixtureRoot,'synthetic-caller-request.json'),'utf8'));
 const inspected=await command('taxml_inspect',request),candidate=inspected.candidates[0];
 assert.equal(candidate.employer,'Synthetic Widgets LLC');assert.equal(candidate.amounts.wages,'98231.17');
 assert.equal(candidate.amounts.social_security_tips,undefined);assert.equal(candidate.amounts.dependent_care_benefits,undefined);
 const schema=await command('schema');context.taxRecordMetadata.setDefaults(schema.capabilities.row_templates.w2);
 const values={employer:candidate.employer,owner:'taxpayer',...candidate.amounts,social_security_tips:'0',dependent_care_benefits:'0'};
 const source={document_id:webcrypto.randomUUID(),return_id:webcrypto.randomUUID(),name:'synthetic-w2.xml'};
 for(const invalid of [{...values,owner:''},{...values,social_security_tips:''},{...values,dependent_care_benefits:''},{...values,wages:''}])await assert.rejects(()=>context.taxMLImport.reviewedRecord(candidate,invalid,source,true,schema.capabilities.row_templates.w2));
 await assert.rejects(()=>context.taxMLImport.reviewedRecord(candidate,values,source,false,schema.capabilities.row_templates.w2));
 await assert.rejects(()=>context.taxMLImport.reviewedRecord({...candidate,can_review:false},values,source,true,schema.capabilities.row_templates.w2));
 const prepared=await context.taxMLImport.reviewedRecord(candidate,values,source,true,schema.capabilities.row_templates.w2);
 assert.equal(prepared.metadata.source_document.method,'taxml');assert.equal(prepared.metadata.reviewed,true);
 const data=JSON.parse(JSON.stringify(schema.default_return));data.name='Synthetic actual worker TaxML draft';data.w2.push(prepared.row);
 const metadata=context.taxRecordMetadata.empty();metadata.w2_records.push(prepared.metadata);
 const normalized=await context.taxRecordMetadata.normalize(data,metadata);
 assert.deepEqual(JSON.parse(JSON.stringify(normalized)),JSON.parse(JSON.stringify(await context.taxRecordMetadata.normalize(data,normalized))));
 const changed=JSON.parse(JSON.stringify(normalized));changed.w2_records[0].source_document.taxml_receipt.source_sha256='0'.repeat(64);
 await assert.rejects(()=>context.taxRecordMetadata.normalize(data,changed,normalized));
 const edited=JSON.parse(JSON.stringify(data));edited.w2[0].wages='98231.18';
 const metadataEdited=await context.taxRecordMetadata.normalize(edited,normalized,normalized);
 assert.equal(metadataEdited.w2_records[0].reviewed,false);
 assert.equal(metadataEdited.w2_records[0].source_document.taxml_receipt.source_sha256,normalized.w2_records[0].source_document.taxml_receipt.source_sha256);
 const result=await command('calculate',data);
 assert.equal(data.eligibility.all_income_reported,false);assert.equal(result.can_prepare,false);
 const blocked=JSON.parse(JSON.stringify(request));blocked.base64=fs.readFileSync(path.join(fixtureRoot,'synthetic-blocked-w2.xml')).toString('base64');
 const rejected=await command('taxml_inspect',blocked);assert.equal(rejected.candidates[0].can_review,false);
 const encrypted=JSON.parse(JSON.stringify(request));encrypted.container='encrypted_tax';await assert.rejects(()=>command('taxml_inspect',encrypted));
 for(const specimen of JSON.parse(fs.readFileSync(path.join(fixtureRoot,'synthetic-wrong-semantic-types.json'),'utf8'))){
  const typed=await command('taxml_inspect',specimen.request);
  assert.equal(typed.candidates[0].can_review,false);
  assert(typed.unresolved_facts.some(row=>row.code==='unsupported_w2_semantic_type'&&row.detail===specimen.field));
 }
 const receipt={runtime:'actual pinned Pyodide via integrated worker source',successful:true,assertions:25,
  federal_can_prepare:result.can_prepare,all_income_reported:data.eligibility.all_income_reported,
  no_original_tax_roundtrip_claim:true,worker_source_sha256:require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(root,'web/tax-worker-source.js'))).digest('hex')};
 fs.mkdirSync(path.join(root,'qa/taxml'),{recursive:true});fs.writeFileSync(path.join(root,'qa/taxml/runtime-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
