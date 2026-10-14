// Exercise the actual staged worker, not a replacement Python harness.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const checkout=path.resolve(__dirname,'..'),root=process.env.TAX_REBORN_RUNTIME_ROOT||checkout;
const out=process.env.TAX_REBORN_QA_ROOT||path.join(checkout,'qa/niit-amt-packet-20261015/worker');
const fixture=JSON.parse(fs.readFileSync(path.join(checkout,'fixtures/capital_niit_amt_2025.json')));
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},
 loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),
 fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
let id=0;
async function command(command,payload){return new Promise((resolve,reject)=>{const current=++id;worker.self.postMessage=m=>{if(m.id===current)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id:current,command,payload}});});}
async function main(){
 fs.mkdirSync(out,{recursive:true});const schema=await command('schema'),rows=[];
 for(const [index,c] of fixture.cases.entries()){
  const d=structuredClone(schema.default_return);d.name='Synthetic worker '+c.name;
  Object.assign(d.taxpayer,{age:40,birth_date:'1985-06-01',valid_ssn:true,valid_tin:true});
  Object.assign(d.eligibility,{full_year_us_resident:true,filing_status_confirmed:true,all_income_reported:true,no_amt_preferences:true,capital_gains_eligible:true});
  Object.assign(d.eitc,{claim:true,eligibility_confirmed:true,main_home_us_half_year:true,not_qualifying_child_of_another:true,no_disallowed_claim_history:true});
  Object.assign(d.niit,{eligibility_confirmed:true,deductions_confirmed:true});d.amt.eligibility_confirmed=true;
  d.w2=[{employer:'Synthetic employer',wages:String(c.wages),medicare_wages:String(c.wages),federal_withholding:String(c.W2_withholding)}];
  d.interest=[{payer:'Synthetic bank',taxable:String(c.taxable_interest),tax_exempt:'0'}];
  d.dividends=c.capital_distributions.map((a,i)=>({payer:'Synthetic fund '+(i+1),ordinary:i===0?String(c.ordinary_dividends):'0',qualified:'0',capital_gain_distributions:a}));
  if(c.prior_zero_tax_exception_if_owed)Object.assign(d.estimated_penalty,{enabled:true,prior_year_tax:'0',prior_year_agi:'0',prior_year_full_12_months:true,prior_year_tax_verified:true,no_prior_year_tax_full_year_resident_confirmed:true,actual_payment_records_confirmed:true});
  Object.assign(d.identity,{first_name:'Synthetic',last_name:'Taxpayer',ssn:'123456789',address:'100 Example Street',city:'Example City',state:'IL',zip:'60000'});
  Object.assign(d.filing_details,{digital_asset_answer:'no',main_home_us_answer:'yes'});
  Object.assign(d.filing_details.official_form_facts.schedule_b,{foreign_account_answer:'no',fbar_required_answer:'no',foreign_trust_answer:'no',facts_confirmed:true});
  const result=await command('calculate',d);assert.equal(result.can_prepare,true);
  const actual=Object.fromEntries(Object.keys(c.expected).map(k=>[k,result.lines[k]]));assert.deepEqual(actual,c.expected,c.name);
  for(const [key,value] of Object.entries(c.IRS_detail))for(const [prefix,module] of [['AMT_','form_6251'],['NIIT_','form_8960']])if(key.startsWith(prefix))assert.equal(result.schedules[module].form_lines[key.slice(prefix.length)],value,c.name+' '+key);
  assert.equal(result.schedules.form_8960.form_lines['5a'],c.expected['7a']);
  assert.equal(result.schedules.form_8960.form_lines['9d'],0);
  let packet=null;
  if(index<2){const record={id:crypto.randomUUID(),data:d,result,updated_at:'2026-10-15T00:00:00Z'};
   const status=await command('paper_status',record);assert.equal(status.paper_preparation_complete,true);assert.equal(status.filing_packet_ready,false);assert.equal(status.missing_facts.length,0);
   const raw=Buffer.from((await command('packet_pdf',record)).base64,'base64');assert.equal(raw.subarray(0,4).toString(),'%PDF');
   const file=c.name+'-worker-packet.pdf';fs.writeFileSync(path.join(out,file),raw);packet={file,sha256:crypto.createHash('sha256').update(raw).digest('hex')};
  }
  rows.push({name:c.name,actual,passed:true,packet});
 }
 const sources={};for(const name of ['tax_engine.py','tax_extended.py','web/tax-worker-source.js'])sources[name]=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,name))).digest('hex');
 const report={runtime:'actual staged worker with pinned Pyodide',synthetic_only:true,cases:rows.length,passed:rows.length,printed_8960_components_present:true,packet_count:2,source_sha256:sources,rows,storage_acceptance:false,native_UI_acceptance:false,original_native_executions:0};
 fs.writeFileSync(path.join(out,'worker-receipt.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({cases:rows.length,passed:rows.length,packets:2}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
