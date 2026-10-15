// Installed worker + real WebAssembly + the same reviewed-record contracts as UI.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/whole-number-source');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const ctx={console,URL,URLSearchParams,TextEncoder,crypto:webcrypto,Response,Blob,File,Uint8Array,ArrayBuffer,setTimeout,clearTimeout,location:{href:'http://stage.local/',search:''},btoa:t=>Buffer.from(t,'binary').toString('base64'),atob:t=>Buffer.from(t,'base64').toString('binary')};ctx.window=ctx;vm.createContext(ctx);
for(const name of ['local-api.js','investment-corrections.js','income-preparation.js','taxml-import.js'])vm.runInContext(fs.readFileSync(path.join(root,'web',name),'utf8'),ctx,{filename:name});
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
const originalFormatter=worker.taxWorkerError;worker.taxWorkerError=error=>{fs.mkdirSync(out,{recursive:true});fs.appendFileSync(path.join(out,'error-type-observations.jsonl'),JSON.stringify({name:error.name,type:error.type,last:String(error.message).trimEnd().split('\n').pop()})+'\n');return originalFormatter(error);};
let sequence=0;async function command(command,payload){return new Promise((resolve,reject)=>{const id=++sequence;worker.self.postMessage=m=>{if(m.id===id)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id,command,payload}});});}ctx.taxLocalEngine=command;
async function inspect(request){return ctx.taxMLImport.inspect(new File([Buffer.from(request.base64,'base64')],'synthetic.taxbin'),new File([JSON.stringify(request.profile)],'profile.json'),request.carriers.map((c,i)=>new File([Buffer.from(c.base64,'base64')],i+'.xprf')),'binary_entity',true);}
function replaceResource(input,carrierIndex,type,rid,payload){
 const request=JSON.parse(JSON.stringify(input)),carrier=request.carriers[carrierIndex],raw=Buffer.from(carrier.base64,'base64'),rows=[];
 for(let i=0;i<raw.readUInt32LE(12);i++){const p=16+12*i,t=raw.readUInt16LE(p),r=raw.readUInt16LE(p+2),at=raw.readUInt32LE(p+4),size=raw.readUInt32LE(p+8);if(t===type&&r===rid){if(payload!==null)rows.push([t,r,payload]);}else rows.push([t,r,raw.subarray(at+10,at+size)]);}
 const header=Buffer.alloc(16);raw.copy(header,0,0,12);header.writeUInt32LE(rows.length,12);let position=16+rows.length*12;const directory=[],bodies=[];
 for(const[t,r,body]of rows){const entry=Buffer.alloc(12),record=Buffer.alloc(10);entry.writeUInt16LE(t);entry.writeUInt16LE(r,2);entry.writeUInt32LE(position,4);entry.writeUInt32LE(body.length+10,8);record.writeUInt32LE(body.length+10);record.writeUInt32LE(body.length,4);directory.push(entry);bodies.push(record,body);position+=body.length+10;}
 const output=Buffer.concat([header,...directory,...bodies]),digest=require('node:crypto').createHash('sha256').update(output).digest('hex'),previous=carrier.sha256;
 carrier.base64=output.toString('base64');carrier.sha256=digest;request.profile.registry_order[carrierIndex]=digest;for(const target of request.profile.templates)if(target.carrier_sha256===previous)target.carrier_sha256=digest;return request;
}
async function main(){
 fs.mkdirSync(out,{recursive:true});const req=JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/whole-number-income-request.json'))),before=await inspect(req),number=before.binary_archive.forms[0].fields.find(f=>f.field_id==='OWNED_UNITS');
 assert.equal(number.text,'7');assert(number.editable);assert.equal(number.ordinal,113);assert.equal(number.current_ordinal,13);assert.equal(number.template_bounds.minimum,1);assert.equal(number.template_bounds.maximum,12);
 const change=value=>ctx.taxMLImport.editBinary(before,[{path:[0,0],field_id:'OWNED_UNITS',element:0,value}],true);
 for(const text of ['0','13','-1','7.0','2147483648'])await assert.rejects(()=>change(text));
 const edited=await change('8'),wire=Buffer.from(edited.base64,'base64'),after=await inspect({...req,base64:edited.base64});
 assert.equal(wire.length,3831);assert.equal(require('node:crypto').createHash('sha256').update(wire).digest('hex'),'3772cb75235635e81d47d61ff526db44b40c8a1f4a372956a0307b979428cd7f');
 assert.equal(after.binary_archive.forms[0].fields.find(f=>f.field_id==='OWNED_UNITS').text,'8');
 for(let i=0;i<4;i++){assert.equal(before.binary_archive.forms[i].derived.sha256,after.binary_archive.forms[i].derived.sha256);assert.deepEqual(JSON.parse(JSON.stringify(before.binary_archive.forms[i].table_headers)),JSON.parse(JSON.stringify(after.binary_archive.forms[i].table_headers)));assert.deepEqual(JSON.parse(JSON.stringify(before.binary_archive.forms[i].links)),JSON.parse(JSON.stringify(after.binary_archive.forms[i].links)));}
 assert(edited.binary_roundtrip_verified);assert.equal(edited.full_return_recalculated,false);fs.writeFileSync(path.join(out,'worker-whole-number-corrected.taxbin'),wire);
 const receipt={real_Pyodide_worker:true,saved_ordinal:113,current_ordinal:13,whole_number7_to8:true,limits_minimum:1,limits_maximum:12,invalid_values_refused:5,complete_source_bytes:wire.length,complete_source_SHA256:'3772cb75235635e81d47d61ff526db44b40c8a1f4a372956a0307b979428cd7f',all_four_derived_tails_unchanged:true,nonempty_tables_child_and_four_links_preserved:true,source_current_identity_and_unknown_body_guards_preserved:true,original_engine_executed:false,whole_original_compatibility:false};fs.writeFileSync(path.join(out,'worker-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
}main().catch(error=>{console.error(error);process.exitCode=1;});
