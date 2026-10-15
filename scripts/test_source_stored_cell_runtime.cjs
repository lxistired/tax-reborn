// Installed JS and actual Pyodide with wholly owned complete binary sources.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/source-stored-cell-worker');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const ctx={console,URL,URLSearchParams,TextEncoder,crypto:webcrypto,Response,Blob,File,Uint8Array,ArrayBuffer,setTimeout,clearTimeout,location:{href:'http://stage.local/',search:''},btoa:t=>Buffer.from(t,'binary').toString('base64'),atob:t=>Buffer.from(t,'base64').toString('binary')};ctx.window=ctx;vm.createContext(ctx);
for(const name of['local-api.js','investment-corrections.js','income-preparation.js','taxml-import.js'])vm.runInContext(fs.readFileSync(path.join(root,'web',name),'utf8'),ctx,{filename:name});
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
let sequence=0;async function command(command,payload){return new Promise((resolve,reject)=>{const id=++sequence;worker.self.postMessage=m=>{if(m.id===id)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id,command,payload}});});}ctx.taxLocalEngine=command;
async function inspect(req){return ctx.taxMLImport.inspect(new File([Buffer.from(req.base64,'base64')],'independent-stored-cell.taxbin'),new File([JSON.stringify(req.profile)],'profile.json'),req.carriers.map((c,i)=>new File([Buffer.from(c.base64,'base64')],i+'.xprf')),'binary_entity',true);}
(async()=>{
 fs.mkdirSync(out,{recursive:true});const req=JSON.parse(fs.readFileSync(path.join(root,'fixtures/source-cell/request.json'))),kept=JSON.stringify(req),before=await inspect(req),cells=before.source_stored_amount_cells;
 assert.deepEqual(JSON.parse(JSON.stringify(cells.map(c=>c.element))),[1,3]);assert(cells.every(c=>c.independent_synthetic_example&&c.policy_kind==='independent_synthetic'&&!c.can_review&&!c.native_propagation));
 assert.equal(before.binary_archive.forms.length,8);assert.equal(before.binary_archive.formsets,2);const outputs=[],refusals=[];
 for(const[element,value]of[[1,'1234.57'],[3,'12.34']]){
  const cell=cells.find(c=>c.element===element);const output=await ctx.taxMLImport.correctedStoredCell(cell,value,true),raw=Buffer.from(output.base64,'base64');
  assert.equal(output.policy_kind,'independent_synthetic');assert.equal(output.native_propagation,false);assert.equal(output.tax_recalculated,false);assert.equal(JSON.stringify(req),kept);
  const reopened=await inspect({...req,base64:output.base64});assert.equal(reopened.source_stored_amount_cells.find(c=>c.element===element).text,value);
  const name='source-stored-cell-element'+element+'-corrected.taxbin';fs.writeFileSync(path.join(out,name),raw);outputs.push({element,value,bytes:raw.length,sha256:output.output_sha256,filename:name});
 }
 for(const mode of['detached','unconfirmed','precision','nochange']){
  const cell=cells[0];await assert.rejects(()=>ctx.taxMLImport.correctedStoredCell(mode==='detached'?{...cell}:cell,mode==='precision'?'1.234':mode==='nochange'?'25.00':'1234.57',mode!=='unconfirmed'));refusals.push(mode);
 }
 for(const key of['trusted','policy_kind','approved_profile','prepared_amount']){
  await assert.rejects(()=>command('source_stored_cell_correct',{inspection:req,expected_source_sha256:cells[0].receipt.source_sha256,expected_cell_sha256:cells[0].receipt.cell_sha256,path:[0,0],field_id:'SYNTHETIC_AMOUNT',element:1,value:'1234.57',confirmed:true,[key]:true}));refusals.push(key);
 }
 const receipt={all_passed:true,real_JS_and_Pyodide:true,actual_WeakMap_receipts:true,complete_owned_source_read_modify_read:true,independently_generated:true,original_resource_payload:false,original_taxpayer_fixture:false,outputs,refusal_cases:refusals,source_profiles_carriers_unchanged:true,native_propagation:false,native_inventory_verified:false,tax_recalculated:false};
 fs.writeFileSync(path.join(out,'source-stored-cell-worker-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(error=>{console.error(error);process.exitCode=1;});
