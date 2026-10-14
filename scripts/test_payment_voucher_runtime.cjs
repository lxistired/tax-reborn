// Invoke the actual packaged worker using public synthetic facts and IRS oracles.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const checkout=path.resolve(__dirname,'..'),root=process.env.TAX_REBORN_RUNTIME_ROOT||checkout;
const out=process.env.TAX_REBORN_QA_ROOT||path.join(checkout,'qa/payment-voucher-20261015/worker');
const fixture=JSON.parse(fs.readFileSync(path.join(checkout,'fixtures/payment_voucher_2025.json')));
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},
 loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),
 fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
let id=0;
async function command(command,payload){return new Promise((resolve,reject)=>{const current=++id;worker.self.postMessage=m=>{if(m.id===current)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id:current,command,payload}});});}
async function main(){
 fs.mkdirSync(out,{recursive:true});const schema=await command('schema'),rows=[];
 for(const c of fixture.cases){
  const d=structuredClone(schema.default_return);d.name='Synthetic voucher worker '+c.name;
  Object.assign(d.taxpayer,{age:40,birth_date:'1985-06-01',valid_ssn:true,valid_tin:true});
  Object.assign(d.eligibility,{full_year_us_resident:true,filing_status_confirmed:true,all_income_reported:true,no_amt_preferences:true,capital_gains_eligible:true,eitc_not_applicable:true});
  Object.assign(d.niit,{eligibility_confirmed:true,deductions_confirmed:true});d.amt.eligibility_confirmed=true;
  d.w2=[{employer:'Synthetic employer',wages:String(c.wages),medicare_wages:String(c.wages),federal_withholding:String(c.withholding)}];
  d.interest=[{payer:'Synthetic bank',taxable:'1000'}];
  d.dividends=[{payer:'Synthetic fund',ordinary:'1000',capital_gain_distributions:c.capital}];
  Object.assign(d.estimated_penalty,{enabled:true,prior_year_tax:'0',prior_year_agi:'0',prior_year_full_12_months:true,prior_year_tax_verified:true,no_prior_year_tax_full_year_resident_confirmed:true,actual_payment_records_confirmed:true});
  Object.assign(d.identity,{first_name:'Synthetic',middle_initial:'A',last_name:'Taxpayer',ssn:'012345678',address:'100 Example Street',apt:'2B',city:'Example City',state:'IL',zip:'60000'});
  Object.assign(d.filing_details,{digital_asset_answer:'no',main_home_us_answer:'yes',balance_due_payment_method:'check_money_order',paper_payment_confirmed:true});
  Object.assign(d.filing_details.official_form_facts.schedule_b,{foreign_account_answer:'no',fbar_required_answer:'no',foreign_trust_answer:'no',facts_confirmed:true});
  const result=await command('calculate',d);assert.equal(result.can_prepare,true);
  assert.equal(result.lines['37'],c.owed);assert.equal(result.lines['24'],c.total_tax);
  const record={id:crypto.randomUUID(),data:d,result,updated_at:'2026-10-15T00:00:00Z'};
  let status=await command('paper_status',record);assert.equal(status.paper_preparation_complete,true);assert.equal(status.payment_voucher.amount,c.owed.toFixed(2));assert.equal(status.payment_voucher.payment_initiated,false);
  const packets=[];
  for(const [name,amount,source]of[['balance',c.owed.toFixed(2),'balance_due'],['custom','1000.25','custom']]){
   Object.assign(d.filing_details,{paper_payment_amount_source:source,paper_payment_amount:amount,paper_payment_confirmed:true});
   status=await command('paper_status',record);assert.equal(status.paper_preparation_complete,true);assert.equal(status.payment_voucher.amount,amount);
   const unchanged=await command('calculate',d);assert.equal(unchanged.lines['37'],c.owed);assert.equal(unchanged.lines['24'],c.total_tax);
   const raw=Buffer.from((await command('packet_pdf',record)).base64,'base64');assert.equal(raw.subarray(0,4).toString(),'%PDF');
   const file=c.name+'-'+name+'-worker-packet.pdf';fs.writeFileSync(path.join(out,file),raw);packets.push({file,amount,sha256:crypto.createHash('sha256').update(raw).digest('hex')});
  }
  d.filing_details.paper_payment_confirmed=false;status=await command('paper_status',record);assert.equal(status.paper_preparation_complete,false);
  d.filing_details.balance_due_payment_method='electronic';status=await command('paper_status',record);assert.equal(status.paper_preparation_complete,true);assert.equal(status.payment_voucher.requested,false);assert.equal(status.payment_voucher.payment_initiated,false);
  rows.push({name:c.name,owed:c.owed,total_tax:c.total_tax,packets,unconfirmed_blocked:true,electronic_no_voucher_or_payment:true});
 }
 const sources={};for(const name of['tax_engine.py','tax_filing.py','official_forms.py','web/tax-worker-source.js','forms/f1040v-2025.pdf'])sources[name]=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,name))).digest('hex');
 const receipt={runtime:'actual staged worker with pinned Pyodide',synthetic_only:true,cases:rows.length,passed:rows.length,packet_count:6,rows,source_sha256:sources,storage_acceptance:false,native_UI_acceptance:false,original_native_executions:0};
 fs.writeFileSync(path.join(out,'payment-voucher-worker-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify({cases:rows.length,passed:rows.length,packets:6}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
