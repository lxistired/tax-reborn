// Actual staged worker source + pinned Pyodide + JS reviewed-record contracts.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..');
const reportRoot=process.env.TAX_REBORN_QA_ROOT||root;
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
 context.taxLocalEngine=command;
 const modernRequest=JSON.parse(fs.readFileSync(path.join(fixtureRoot,'synthetic-modern-windows-request.json'),'utf8'));
 const modernFile=new File([Buffer.from(modernRequest.base64,'base64')],'synthetic-modern-windows-w2.xml',{type:'application/xml'});
 const modernProfile=new File([JSON.stringify(modernRequest.profile)],'synthetic-modern-windows-wire-profile.json',{type:'application/json'});
 const modernRegistry=new File([Buffer.from(modernRequest.carriers[0].base64,'base64')],'synthetic-modern-windows-w2.xprf');
 const modern=await context.taxMLImport.inspect(modernFile,modernProfile,[modernRegistry],'plaintext_xml',true),mc=modern.candidates[0];
 assert.equal(mc.can_review,true);assert.equal(mc.source_owner.copyNum,'0');assert.equal(mc.amounts.wages,'1234.56');
 assert.equal(mc.employer,null);assert.deepEqual(JSON.parse(JSON.stringify(mc.requires_manual_fields)),['owner','social_security_tips','dependent_care_benefits']);
 const reviewedValues={...mc.amounts,wages:'1234.57',employer:'Synthetic Widgets',owner:'taxpayer',social_security_tips:'0',dependent_care_benefits:'0'};
 await assert.rejects(()=>context.taxMLImport.correctedSource(mc,reviewedValues,false));
 await assert.rejects(()=>context.taxMLImport.correctedSource({...mc},reviewedValues,true));
 for(const wages of ['-1','1.001','1000000001',''])await assert.rejects(()=>context.taxMLImport.correctedSource(mc,{...reviewedValues,wages},true));
 const corrected=await context.taxMLImport.correctedSource(mc,reviewedValues,true);
 const correctedBytes=Buffer.from(corrected.base64,'base64'),originalBytes=Buffer.from(modernRequest.base64,'base64');
 assert.equal(corrected.mime,'application/xml');assert.equal(corrected.full_return_recalculated,false);assert.equal(corrected.original_program_acceptance_verified,false);
 assert.equal(corrected.source_sha256,modern.source_sha256);assert.equal(corrected.output_sha256,require('node:crypto').createHash('sha256').update(correctedBytes).digest('hex'));
 // The original integer FEDTAX is normalized to a two-place dollar string;
 // only those two value spans differ from the independently authored source.
 assert.equal(correctedBytes.toString(),originalBytes.toString().replace('>1234.56</td:value>','>1234.57</td:value>').replace('>123</td:value>','>123.00</td:value>'));
 const modernReadback=await command('taxml_inspect',{...modernRequest,base64:corrected.base64});
 assert.equal(modernReadback.candidates[0].amounts.wages,'1234.57');
 const nativePrepared=await context.taxMLImport.reviewedRecord(mc,reviewedValues,source,true,schema.capabilities.row_templates.w2);
 const nativeData=JSON.parse(JSON.stringify(schema.default_return));nativeData.w2.push(nativePrepared.row);
 const nativeResult=await command('calculate',nativeData);
 assert.equal(nativeResult.summary.refund,123);assert.equal(nativeData.eligibility.all_income_reported,false);
 const unsupported={...modernRequest,base64:Buffer.from(originalBytes.toString().replace('</FW2>','<UNKNOWN/></FW2>')).toString('base64')};
 assert.equal((await command('taxml_inspect',unsupported)).candidates[0].can_review,false);
 for(const specimen of JSON.parse(fs.readFileSync(path.join(fixtureRoot,'synthetic-wrong-semantic-types.json'),'utf8'))){
  const typed=await command('taxml_inspect',specimen.request);
  assert.equal(typed.candidates[0].can_review,false);
  assert(typed.unresolved_facts.some(row=>row.code==='unsupported_w2_semantic_type'&&row.detail===specimen.field));
 }
 const encodingCases=JSON.parse(fs.readFileSync(path.join(fixtureRoot,'synthetic-encoding-boundaries.json'),'utf8'));
 for(const specimen of encodingCases){
  if(specimen.expected==='reject')await assert.rejects(()=>command('taxml_inspect',specimen.request));
  else{
   const accepted=await command('taxml_inspect',specimen.request);
   assert.equal(accepted.candidates[0].employer,candidate.employer);
   const exact=Buffer.from(specimen.request.base64,'base64');
   assert.equal(accepted.source_sha256,require('node:crypto').createHash('sha256').update(exact).digest('hex'));
  }
 }
 const receipt={runtime:'actual pinned Pyodide via integrated worker source',successful:true,assertions:25,
  current_windows_native_shape_and_corrected_source_verified:true,corrected_XML_outside_value_spans_byte_identical:true,
  additional_encoding_input_probes:encodingCases.length,
  federal_can_prepare:result.can_prepare,all_income_reported:data.eligibility.all_income_reported,
  no_original_tax_roundtrip_claim:true,worker_source_sha256:require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(root,'web/tax-worker-source.js'))).digest('hex')};
 fs.mkdirSync(path.join(reportRoot,'qa/taxml'),{recursive:true});fs.writeFileSync(path.join(reportRoot,'qa/taxml/runtime-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
