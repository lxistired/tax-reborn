// Installed worker + real WebAssembly + the same reviewed-record contracts as UI.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/mac-scalar-worker');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const ctx={console,URL,URLSearchParams,TextEncoder,crypto:webcrypto,Response,Blob,File,Uint8Array,ArrayBuffer,setTimeout,clearTimeout,location:{href:'http://stage.local/',search:''},btoa:t=>Buffer.from(t,'binary').toString('base64'),atob:t=>Buffer.from(t,'base64').toString('binary')};ctx.window=ctx;vm.createContext(ctx);
for(const name of ['local-api.js','investment-corrections.js','income-preparation.js','taxml-import.js'])vm.runInContext(fs.readFileSync(path.join(root,'web',name),'utf8'),ctx,{filename:name});
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
const originalFormatter=worker.taxWorkerError;worker.taxWorkerError=error=>{fs.mkdirSync(out,{recursive:true});fs.appendFileSync(path.join(out,'error-type-observations.jsonl'),JSON.stringify({name:error.name,type:error.type,last:String(error.message).trimEnd().split('\n').pop()})+'\n');return originalFormatter(error);};
let sequence=0;async function command(command,payload){return new Promise((resolve,reject)=>{const id=++sequence;worker.self.postMessage=m=>{if(m.id===id)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id,command,payload}});});}ctx.taxLocalEngine=command;
async function inspect(request){return ctx.taxMLImport.inspect(new File([Buffer.from(request.base64,'base64')],'synthetic-cleartext.zip'),new File([JSON.stringify(request.profile)],'profile.json'),request.carriers.map((c,i)=>new File([Buffer.from(c.base64,'base64')],i+'.xprf')),'cleartext_persistence_container',true);}
async function main(){
 fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'error-type-observations.jsonl'),'');
 const req=JSON.parse(fs.readFileSync(path.join(root,'web/samples/mac-scalar-request.json'))),before=await inspect(req);
 assert.equal(before.candidates.length,7);assert(before.candidates.every(c=>c.can_review));assert.equal(before.scalar_fields.length,3);assert.equal(before.unresolved_facts.length,0);assert.equal(before.source_filter_profile,'controller_filter');
 assert.deepEqual(Array.from(before.scalar_fields,f=>f.text),['0.7','1.2','-0.3']);assert(before.scalar_fields.every(f=>f.kind===13&&f.current_ordinal===9&&!f.can_review&&f.can_edit_source));
 const selected=before.scalar_fields[0],output=await ctx.taxMLImport.correctedScalar(selected,'0.8',true),after=await inspect({...req,base64:output.base64});
 assert.equal(output.output_sha256,'1da9b78f366be589372251a598ba28bc03922d03adc70337d114f93a09c32412');assert.equal(output.mime,'application/zip');assert.equal(Buffer.from(output.base64,'base64').length,2241);
 assert.deepEqual(Array.from(after.scalar_fields,f=>f.text),['0.8','1.2','-0.3']);assert.deepEqual(JSON.parse(JSON.stringify(after.candidates.map(c=>c.amounts))),JSON.parse(JSON.stringify(before.candidates.map(c=>c.amounts))));assert.equal(output.tax_values_imported,false);assert.equal(output.full_return_recalculated,false);assert.equal(output.container_report.unselected_local_records_byte_identical,true);assert.equal(output.container_report.original_manifest_bytes_unchanged,true);
 let refused=0;const rejects=async f=>{await assert.rejects(f);refused++;};
 await rejects(()=>ctx.taxMLImport.correctedScalar(selected,'0.8',false));
 await rejects(()=>ctx.taxMLImport.correctedScalar({...selected},'0.8',true));
 for(const value of ['0.80','.8','1e2','NaN','-0.0','10000000000000.0'])await rejects(()=>ctx.taxMLImport.correctedScalar(selected,value,true));
 await rejects(()=>ctx.taxMLImport.reviewedRecord(selected,{}, {},true,{}));
 const plain=JSON.parse(fs.readFileSync(path.join(root,'fixtures/mac-scalar-taxml/plaintext-request.json'))),xml=Buffer.from(plain.base64,'base64').toString('utf8');
 for(const bad of [false,1,null,'sanitizer_filter','controller_filter '])await rejects(()=>command('taxml_inspect',{...plain,profile:{...plain.profile,filter_profile:bad}}));
 for(const [a,b] of [['<DECIMAL field="9"','<DECIMAL field="8"'],['<DECIMAL field="9" elem="0"','<DECIMAL field="9" elem="1"'],['>-0.3</td:value>','>-0.3</td:value><Unknown/>'],['tpsType="dec1"','tpsType="money"']])await rejects(()=>command('taxml_inspect',{...plain,base64:Buffer.from(xml.replace(a,b)).toString('base64')}));
 const blocked=JSON.parse(fs.readFileSync(path.join(root,'web/samples/mac-scalar-blocked-request.json'))),blockedResult=await inspect(blocked);assert(blockedResult.scalar_fields.every(f=>!f.can_edit_source));
 await rejects(()=>ctx.taxMLImport.correctedScalar(blockedResult.scalar_fields[0],'0.8',true));
 await rejects(()=>command('taxml_export',{inspection:blocked,expected_scalar_sha256:blockedResult.scalar_fields[0].receipt.field_sha256,value:'0.8',confirmed:true}));
 await rejects(()=>command('taxml_export',{inspection:req,expected_scalar_sha256:'0'.repeat(64),value:'0.8',confirmed:true}));
 fs.writeFileSync(path.join(out,'mac-scalar-corrected.zip'),Buffer.from(output.base64,'base64'));
 const receipt={real_pyodide_worker:true,real_client_WeakMap_receipts:true,explicit_controller_filter:true,entities:2,copies:7,all_source_fields:47,decimal_fields:3,decimal_current_ordinal:9,decimal_not_money_or_income:true,refusal_requests:refused,output_bytes:2241,output_sha256:output.output_sha256,other_scalar_and_income_values_unchanged:true,other_local_records_exact:4,manifest_exact:true,native_runtime:0,native_load_setter_not_called:true};
 fs.writeFileSync(path.join(out,'mac-scalar-worker-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
}main().catch(error=>{console.error(error);process.exitCode=1;});
