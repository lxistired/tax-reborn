// Run the actual staged worker. All people and addresses are synthetic.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const checkout=path.resolve(__dirname,'..'),root=process.env.TAX_REBORN_RUNTIME_ROOT||checkout;
const out=process.env.TAX_REBORN_QA_ROOT||path.join(checkout,'qa/foreign-address-20261015/worker');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},
 loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),
 fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
let id=0;
async function command(command,payload){return new Promise((resolve,reject)=>{const current=++id;worker.self.postMessage=m=>{if(m.id===current)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id:current,command,payload}});});}
async function main(){
 fs.mkdirSync(out,{recursive:true});const schema=await command('schema'),rows=[];
 const d=structuredClone(schema.default_return);d.name='Synthetic foreign mailing address';
 Object.assign(d.taxpayer,{age:40,birth_date:'1985-06-01',valid_ssn:true,valid_tin:true});
 Object.assign(d.eligibility,{full_year_us_resident:true,filing_status_confirmed:true,all_income_reported:true,no_amt_preferences:true,capital_gains_eligible:true,eitc_not_applicable:true});
 Object.assign(d.niit,{eligibility_confirmed:true,deductions_confirmed:true});d.amt.eligibility_confirmed=true;
 d.w2=[{employer:'Synthetic employer',federal_withholding:'1000'}];
 // Load the independent IRS voucher fixture facts and fixed2435 oracle.
 const c=JSON.parse(fs.readFileSync(path.join(checkout,'fixtures/payment_voucher_2025.json'))).cases[0];
 d.w2[0].wages=String(c.wages);d.w2[0].medicare_wages=String(c.wages);
 d.interest=[{payer:'Synthetic bank',taxable:'1000'}];d.dividends=[{payer:'Synthetic fund',ordinary:'1000',capital_gain_distributions:c.capital}];
 Object.assign(d.estimated_penalty,{enabled:true,prior_year_tax:'0',prior_year_agi:'0',prior_year_full_12_months:true,prior_year_tax_verified:true,no_prior_year_tax_full_year_resident_confirmed:true,actual_payment_records_confirmed:true});
 Object.assign(d.identity,{first_name:'Synthetic',middle_initial:'A',last_name:'Taxpayer',ssn:'012345678',address:'100 Example Street',apt:'2B',city:'Example City',state:'IL',zip:'60000'});
 Object.assign(d.filing_details,{digital_asset_answer:'no',main_home_us_answer:'yes',balance_due_payment_method:'check_money_order',paper_payment_confirmed:true});
 Object.assign(d.filing_details.official_form_facts.schedule_b,{foreign_account_answer:'no',fbar_required_answer:'no',foreign_trust_answer:'no',facts_confirmed:true});
 const before=await command('calculate',d);assert.equal(before.lines['37'],2435);
 for(const c of[{name:'germany',city:'Berlin',country:'Germany',province:'Berlin',postal:'10115'}, {name:'canada',city:'Ottawa',country:'Canada',province:'Ontario',postal:'K1A 0B1'}]){
  Object.assign(d.identity,{city:c.city,foreign_country:c.country,foreign_province:c.province,foreign_postal_code:c.postal});d.filing_details.mailing_address_type='foreign';
  const result=await command('calculate',d);assert.deepEqual(result.lines,before.lines);assert.equal(result.form_readiness.missing_identity.length,0);
  const record={id:crypto.randomUUID(),data:d,result,updated_at:'2026-10-15T00:00:00Z'};
  const status=await command('paper_status',record);assert.equal(status.paper_preparation_complete,true);
  const raw=Buffer.from((await command('packet_pdf',record)).base64,'base64'),file=c.name+'-worker-packet.pdf';assert.equal(raw.subarray(0,4).toString(),'%PDF');fs.writeFileSync(path.join(out,file),raw);
  rows.push({...c,file,sha256:crypto.createHash('sha256').update(raw).digest('hex'),owed:2435});
 }
 d.identity.foreign_country='DE';let result=await command('calculate',d);assert.equal(result.can_prepare,true);assert.equal(result.lines['37'],2435);
 let status=await command('paper_status',{data:d,result});assert.equal(status.paper_preparation_complete,false);
 d.identity.foreign_country='Canada';d.eligibility.full_year_us_resident=false;result=await command('calculate',d);assert.equal(result.can_prepare,false);
 const hashes={};for(const n of['tax_engine.py','tax_filing.py','forms.py','official_forms.py','web/app.js','web/tax-worker-source.js'])hashes[n]=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,n))).digest('hex');
 const receipt={runtime:'actual staged worker with pinned Pyodide',synthetic_only:true,passed:2,rows,incomplete_country_blocks_paper:true,tax_eligibility_not_expanded:true,source_sha256:hashes,storage_acceptance:false,native_UI_acceptance:false,original_native_executions:0};
 fs.writeFileSync(path.join(out,'foreign-address-worker-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify({passed:2,packets:2,incomplete_country_blocks_paper:true}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
