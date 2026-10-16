// Installed General JS/WASM and independently authored kernel fixtures.
// No original resource or original saved return is shipped with these checks.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/source-mc-runtime');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
function environment(tamper=null){
 const worker={console,URL,Uint8Array,TextDecoder,crypto:webcrypto,self:{location:{href:'http://stage.local/tax-worker.js'}},loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),fetch:async url=>{
  const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);
  if(!fs.existsSync(target))return new Response('missing',{status:404});
  let data=fs.readFileSync(target);
  if(name===tamper)data=Buffer.concat([data,Buffer.from('\nchanged installed fixture\n')]);
  return new Response(data);
 }};
 vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
 let serial=0;const command=(command,payload)=>new Promise((resolve,reject)=>{const id=++serial;worker.self.postMessage=m=>{if(m.id===id)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id,command,payload}});});
 return {worker,command};
}
(async()=>{
 fs.mkdirSync(out,{recursive:true});const {worker,command}=environment(),refusals=[];
 await assert.rejects(()=>command('source_mc_input_diagnose',{}),e=>{assert(!e.message.includes('Traceback'));refusals.push({name:'no-complete-source',error:e.message});return /Exact source/.test(e.message);});
 const fixture=JSON.parse(fs.readFileSync(path.join(root,'fixtures/binary-tax/auto-array-income-request.json')));
 const request={source:fixture,expected_source_sha256:'0'.repeat(64),summary_path:[0,0],source_formset_index:0,row_number:1,field_id:'L1',need_native_row_uuid:false,local_resource:{base64:'AA==',sha256:'5e8db09dc9c4126c0cd85fe11ee7b02965a3b9e88db1075ba32efc4269e0bc2f'}};
 await assert.rejects(()=>command('source_mc_input_diagnose',request),e=>{assert(!e.message.includes('Traceback'));refusals.push({name:'independent-invalid-resource',error:e.message});return /Local resource content/.test(e.message);});
 const py=await vm.runInContext('ready()',worker);
 const kernels=JSON.parse(await py.runPythonAsync(`from decimal import Decimal
from source_mc.numeric_current_input_reference import StoredCents
from source_mc.current_numeric_leaf_reference import _construct
from source_mc.owned_current_MC_value_reference import SourceInstance,OwnedCurrentMCReceiver,value_report,map_constructor
cases=[]
for raw,attrs in ((0,1),(-12345,9),(98765,11)):
 leaf,protocol=_construct(StoredCents(11,raw&((1<<64)-1),attrs,0,0,0,0))
 ancestor=b'/Return/ReturnData/PP1099Int'
 path=ancestor+b'[independent-owned-1]/InterestIncomeAmtPP'
 receiver=OwnedCurrentMCReceiver(ancestor+b'/InterestIncomeAmtPP',ancestor,SourceInstance(b'OWNED$SOURCE.L1',path,leaf))
 value=receiver.get_value();assert receiver.get_value()is value
 report=value_report(value);entry=report['entries'][0]
 assert len(report['entries'])==1 and entry['key']=='independent-owned-1'
 assert Decimal(entry['value']['amount'])==Decimal(raw)/100
 assert entry['value']['Overridden']==bool(attrs&8)
 assert not report['Error']and not report['top_blank']
 assert receiver.source_enumerations==receiver.typed_cache_hits==1
 cases.append({'raw_cents':raw,'source_attrs':attrs,'amount':entry['value']['amount'],'shared_owned_cache':True})
empty=value_report(map_constructor({}));assert not empty['top_blank']and not empty['Error']
json.dumps({'all_passed':True,'cases':cases,'empty_map_nonblank':True,'original_source_authentication_tested':False})`));
 assert(kernels.all_passed);
 const schema=await command('schema',{}),result=await command('calculate',schema.default_return);assert.equal(typeof result,'object');
 await assert.rejects(()=>command('unknown_source_mc_command',{}));
 for(const name of ['source-mc-runtime.json','source_mc/owned_current_MC_value_reference.py']){
  const changed=environment(name);await assert.rejects(()=>changed.command('source_mc_input_diagnose',{}),e=>{refusals.push({name:'installed-tamper-'+name,error:e.message});return /runtime.*changed|manifest changed/.test(e.message);});
 }
 const receipt={all_passed:true,actual_installed_General_JS_and_Pyodide:true,independent_kernel_fixtures:kernels,source_and_tamper_refusals:refusals,IRS_schema_and_calculation_after_invalid_data:true,original_resource_payloads_used:false,original_source_positive_not_tested:true,native_original_engine_tested:false,complete_original_compatibility:false};
 fs.writeFileSync(path.join(out,'source-mc-runtime-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(error=>{console.error(error);process.exitCode=1;});
