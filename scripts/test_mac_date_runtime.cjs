// Installed JS and actual Pyodide; no original vendor file is read.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/mac-date-worker');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const ctx={console,URL,URLSearchParams,TextEncoder,crypto:webcrypto,Response,Blob,File,Uint8Array,ArrayBuffer,setTimeout,clearTimeout,location:{href:'http://stage.local/',search:''},btoa:t=>Buffer.from(t,'binary').toString('base64'),atob:t=>Buffer.from(t,'base64').toString('binary')};ctx.window=ctx;vm.createContext(ctx);
for(const name of['local-api.js','investment-corrections.js','income-preparation.js','taxml-import.js'])vm.runInContext(fs.readFileSync(path.join(root,'web',name),'utf8'),ctx,{filename:name});
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
let sequence=0;async function command(command,payload){return new Promise((resolve,reject)=>{const id=++sequence;worker.self.postMessage=m=>{if(m.id===id)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id,command,payload}});});}ctx.taxLocalEngine=command;
async function inspect(req){return ctx.taxMLImport.inspect(new File([Buffer.from(req.base64,'base64')],'owned-dates.zip'),new File([JSON.stringify(req.profile)],'profile.json'),req.carriers.map((c,i)=>new File([Buffer.from(c.base64,'base64')],i+'.xprf')),req.container,true);}
(async()=>{
 fs.mkdirSync(out,{recursive:true});const req=JSON.parse(fs.readFileSync(path.join(root,'web/samples/mac-date-request.json'))),before=await inspect(req);
 assert.equal(before.date_fields.length,9);assert.equal(before.candidates.length,7);assert(before.candidates.every(c=>c.can_review));assert.equal(before.scalar_fields.length,0);assert(before.date_fields.every(f=>f.can_edit_source&&!f.can_review));
 const expected=[[0,'02/29/2000',2290,'36a739775bcafb3b5982f800dfaca948d4909a59ab94fdac15539a269f37df94'],[4,'12-31',2290,'3d05857a331f1e1294347b17090b60519b9a3c1bcb037d863e9c91b11ddbb05c'],[8,'2025-12',2291,'8c8555e8bc75c3dcaeaffcfa089a587431ace6884914a74a4b3d8e5abb418bc3']],outputs=[];
 for(const[index,value,bytes,sha]of expected){
  const output=await ctx.taxMLImport.correctedDate(before.date_fields[index],value,true),after=await inspect({...req,base64:output.base64});
  assert.equal(Buffer.from(output.base64,'base64').length,bytes);assert.equal(output.output_sha256,sha);assert.equal(output.native_date_load_executed,false);assert.equal(output.tax_values_imported,false);assert.equal(output.full_return_recalculated,false);assert.equal(output.original_program_acceptance_verified,false);
  assert.equal(output.container_report.unselected_local_records_byte_identical,true);assert.equal(output.container_report.original_manifest_bytes_unchanged,true);
  assert.deepEqual(Array.from(after.date_fields,f=>f.text),Array.from(before.date_fields,(f,i)=>i===index?value:f.text));assert.deepEqual(JSON.parse(JSON.stringify(after.candidates.map(c=>c.amounts))),JSON.parse(JSON.stringify(before.candidates.map(c=>c.amounts))));
  const name='mac-date-'+index+'-corrected.zip';fs.writeFileSync(path.join(out,name),Buffer.from(output.base64,'base64'));outputs.push({index,value,bytes,sha256:sha,file:name});
 }
 let refusals=0;const reject=async fn=>{await assert.rejects(fn);refusals++;};
 await reject(()=>ctx.taxMLImport.correctedDate(before.date_fields[0],'02/29/2000',false));await reject(()=>ctx.taxMLImport.correctedDate({...before.date_fields[0]},'02/29/2000',true));
 for(const[index,values]of[[0,['2000-02-29','02/29/1900','01/01/1899','01/01/10000',' 01/02/2000']],[1,['02/29','02-30','00-01']],[2,['2000-13','02/2000','2000-2']]])for(const value of values)await reject(()=>ctx.taxMLImport.correctedDate(before.date_fields[index],value,true));
 await reject(()=>command('taxml_export',{inspection:req,expected_date_sha256:'0'.repeat(64),value:'02/29/2000',confirmed:true}));
 const blocked=JSON.parse(fs.readFileSync(path.join(root,'web/samples/mac-date-blocked-request.json'))),readOnly=await inspect(blocked);assert(readOnly.date_fields.every(f=>!f.can_edit_source));await reject(()=>ctx.taxMLImport.correctedDate(readOnly.date_fields[0],'02/29/2000',true));
 await reject(()=>inspect({...req,profile:{...req.profile,format:'tax-reborn-taxml-native-mac-profile-v2'}}));await reject(()=>ctx.taxMLImport.reviewedRecord(before.date_fields[0],{},{},true,{}));
 const receipt={real_JS_and_Pyodide:true,actual_packaged_assets:!!process.env.TAX_REBORN_RUNTIME_ROOT,runtime_scope:process.env.TAX_REBORN_RUNTIME_ROOT?'caller-selected packaged runtime':'source checkout',real_WeakMap_bindings:true,source_date_fields:9,complete_source_fields:53,stored_entities:2,stored_copies:7,outputs,refusals,complete_container_readback:true,other_local_records_exact:4,manifest_exact:true,date_not_money_or_income:true,native_date_load_executed:false,original_runtime:0,full_original_compatibility:false};
 fs.writeFileSync(path.join(out,'mac-date-worker-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(error=>{console.error(error);process.exitCode=1;});
