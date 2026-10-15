// Real app UI with HTTP/SQLite and browser Pyodide/IndexedDB. Synthetic only.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const {chromium}=require(process.env.TAX_REBORN_PLAYWRIGHT||'playwright');
const root=path.resolve(__dirname,'..'),scratch=fs.mkdtempSync(path.join(os.tmpdir(),'tax-clear-container-')),fix=path.join(root,'fixtures/taxml'),out=path.join(root,'qa/cleartext-container-20261015');fs.mkdirSync(out,{recursive:true});
const child=spawn('python3',['-u','-c',`import sys,json;sys.path.insert(0,${JSON.stringify(root)});from http.server import ThreadingHTTPServer;import server;http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);http.store=server.Store(${JSON.stringify(scratch)});print(json.dumps({'port':http.server_port}),flush=True);http.serve_forever()`],{stdio:['ignore','pipe','pipe']});
let browser;const checks=[],errors=[];
async function inspect(page,blocked=false){
 await page.evaluate(()=>showTaxMLImport());
 await page.getByLabel('Choose plaintext TaxML or .tax container').setInputFiles(path.join(root,'fixtures/plaintext-container/'+(blocked?'synthetic-cleartext-container-blocked.zip':'synthetic-cleartext-container.zip')));
 await page.getByLabel('Choose explicit TaxML wire profile').setInputFiles(path.join(fix,'synthetic-mixed-income-profile.json'));
 await page.getByLabel('Choose caller-owned XPRF registries').setInputFiles(['synthetic-modern-windows-w2.xprf','synthetic-native-interest.xprf','synthetic-native-dividend.xprf'].map(n=>path.join(fix,n)));
 await page.getByLabel('TaxML container declaration').selectOption('cleartext_persistence_container');
 await page.getByLabel('Acknowledge the selected unverified wire profile').check();
 await page.getByRole('button',{name:'Inspect locally',exact:true}).click();
 try{await page.getByRole('button',{name:'Review W-2 candidate',exact:true}).waitFor({timeout:120000});}
 catch(e){await page.screenshot({path:path.join(out,'inspection-failure.png'),fullPage:true});console.error('INSPECTION FAILED',await page.locator('body').innerText());throw e;}
 await page.getByText('Complete cleartext container',{exact:true}).waitFor();
}
async function review(page,label){
 await page.getByRole('button',{name:'Review '+label+' candidate',exact:true}).click();
 if(label==='W-2'){
  await page.getByLabel('Employer name',{exact:true}).fill('Synthetic mixed employer');
  await page.getByLabel('Whose W-2 is this?',{exact:true}).selectOption('taxpayer');
  await page.getByLabel('Box 7 · Social Security tips',{exact:true}).fill('0');
  await page.getByLabel('Box 10 · Dependent-care benefits',{exact:true}).fill('0');
  await page.getByLabel('Confirm all TaxML W-2 amounts and ownership').check();
 }else{
  await page.getByLabel(label+' payer name').fill('Synthetic mixed '+label+' payer');
  await page.getByLabel('Confirm supported '+label+' situation').check();
  if(label==='1099-DIV')await page.getByLabel('Confirm qualified dividend eligibility').check();
  await page.getByLabel('Confirm all TaxML '+label+' amounts and household').check();
 }
}
(async()=>{
 const ready=await new Promise((resolve,reject)=>{let text='';child.stdout.on('data',b=>{text+=b;try{resolve(JSON.parse(text.split('\n')[0]));}catch{}});child.on('exit',code=>reject(Error('Synthetic API exited '+code)));});
 const origin='http://127.0.0.1:'+ready.port;browser=await chromium.launch({headless:true,...(process.env.TAX_REBORN_BROWSER?{executablePath:process.env.TAX_REBORN_BROWSER}:{})});
 for(const offline of [false,true]){
  const mode=offline?'Pyodide-IndexedDB':'HTTP-SQLite',context=await browser.newContext({viewport:{width:offline?390:1280,height:900},acceptDownloads:true});
  await context.route('**/*',route=>{const u=new URL(route.request().url());return u.origin===origin||['blob:','data:'].includes(u.protocol)?route.continue():route.abort();});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+(offline?'/?offline=1':''));await page.waitForFunction(()=>!document.querySelector('#save-button').disabled,{timeout:120000});
  const old=await page.evaluate(async()=>{newReturn();data.name='Synthetic complete cleartext container';data.interest.push({payer:'Existing synthetic bank',taxable:'30.00',tax_exempt:'0',federal_withholding:'0'});metadata.income_document_records.interest.push(window.taxIncomePreparation.newRecord());await calculate();await saveReturn();return clone(metadata.income_document_records.interest[0]);});
  await inspect(page);
  for(const [label,collection,expected]of [['W-2','w2',1],['1099-INT','interest',2],['1099-DIV','dividends',1]]){
   await review(page,label);await page.getByRole('button',{name:'Add reviewed '+label,exact:true}).click();
   try{await page.waitForFunction(({collection,expected})=>data[collection].length===expected,{collection,expected});}
   catch(e){await page.screenshot({path:path.join(out,mode+'-failed-'+collection+'.png'),fullPage:true});console.error(mode,label,JSON.stringify(await page.evaluate(()=>({counts:{w2:data.w2.length,interest:data.interest.length,dividends:data.dividends.length},dialogErrors:[...document.querySelectorAll('.dialog-error')].map(x=>x.textContent),revision,summary:result?.summary}))));throw e;}
   await page.getByRole('button',{name:'Review '+label+' candidate',exact:true}).waitFor();
   assert.equal(await page.getByRole('button',{name:'Review '+label+' candidate',exact:true}).isDisabled(),true);
  }
  await page.screenshot({path:path.join(out,mode+'-three-reviewed-forms.png'),fullPage:true});
  await page.evaluate(async()=>{closeDialog();await calculate();await saveReturn();await loadReturn(currentId);});
  const before=await page.evaluate(()=>({id:currentId,data:clone(data),metadata:clone(metadata),summary:clone(result.summary),lines:clone(result.lines)}));
  // Box1=100.23 + Box3=40.27 + existing30.00 =170.50 ->171 whole USD.
  assert.equal(before.lines['1a'],1235);assert.equal(before.lines['2b'],171);assert.equal(before.lines['3b'],1200);assert.equal(before.lines['7a'],1000);assert.equal(before.summary.refund,344);
  assert.deepEqual(before.metadata.income_document_records.interest[0],old);
  const entries=[before.metadata.w2_records[0],before.metadata.income_document_records.interest[1],before.metadata.income_document_records.dividends[0]];
  assert.deepEqual(entries.map(e=>e.source_document.taxml_receipt.form_path),['0/0/0','0/0/1','0/0/2']);assert.equal(new Set(entries.map(e=>e.source_document.document_id)).size,1);assert.ok(entries.every(e=>e.reviewed));
  await page.reload();await page.waitForFunction(()=>!document.querySelector('#save-button').disabled,{timeout:120000});await page.waitForFunction(()=>result&&calculatedRevision===revision&&!calculationError,null,{timeout:120000});
  const after=await page.evaluate(()=>({id:currentId,data:clone(data),metadata:clone(metadata),summary:clone(result.summary),lines:clone(result.lines)}));assert.deepEqual(after,before);
  const restored=await page.evaluate(async()=>{const backup=await api('/api/returns/'+currentId+'/export.json'),report=await restoreReturnBackup(parseReturnBackup(JSON.stringify(backup)),crypto.randomUUID());return api('/api/returns/'+report.id);});
  assert.notEqual(restored.id,before.id);assert.equal(restored.data.w2.length,1);assert.equal(restored.data.interest.length,2);assert.equal(restored.data.dividends.length,1);assert.equal(restored.result.summary.refund,344);
  await inspect(page);await review(page,'1099-INT');
  await page.getByRole('button',{name:'Add reviewed 1099-INT',exact:true}).click();await page.locator('.dialog-error').filter({hasText:'already supplied a 1099-INT'}).waitFor();
  assert.equal(await page.evaluate(()=>data.interest.length),2);
  await page.getByLabel('Box 1 · Interest income',{exact:true}).fill('101.24');
  const downloadWait=page.waitForEvent('download');await page.getByRole('button',{name:'Download corrected container',exact:true}).click();const download=await downloadWait,file=path.join(out,mode+'-corrected-container.zip');await download.saveAs(file);
  const verify=require('node:child_process').spawnSync('python3',[path.join(root,'scripts/verify_clear_container_native.py'),path.join(root,'fixtures/plaintext-container/synthetic-cleartext-container.zip'),file,'--field','interest_income','--amount','101.24'],{cwd:root,encoding:'utf8'});
  assert.equal(verify.status,0,verify.stdout+'\n'+verify.stderr);const fullReadback=JSON.parse(verify.stdout);assert.equal(fullReadback.untouched_local_records_exact,4);assert.equal(fullReadback.members,5);assert.equal(await page.evaluate(()=>data.interest[1].taxable),'140.50');
  await page.screenshot({path:path.join(out,mode+'-corrected-selected-INT.png'),fullPage:true});
  checks.push({mode,complete_container_report_rendered:true,real_UI_file_inputs:true,three_form_types_reviewed_from_one_attachment:true,copy_1_kept_distinct:true,prior_record_retained:true,reload_and_JSON_restore_passed:true,duplicate_rejected:true,selected_complete_container_system_download:true,full_readback:fullReadback,other_forms_byte_identical:true,refund:before.summary.refund,original_runtime:0});console.log('PASS',mode);await page.evaluate(()=>{closeDialog();});await page.evaluate(()=>showTaxMLImport());await page.getByText('Try independently generated binary samples',{exact:true}).click();await page.getByRole('button',{name:'Load plaintext container sample',exact:true}).click();await page.getByText('Complete cleartext container',{exact:true}).waitFor({timeout:120000});assert.equal(await page.getByRole('button',{name:/^Review (W-2|1099-INT|1099-DIV) candidate$/}).count(),3);await page.screenshot({path:path.join(out,mode+'-builtin-complete-container.png'),fullPage:true});await page.evaluate(()=>closeDialog());await inspect(page,true);for(const label of ['W-2','1099-INT','1099-DIV'])assert.equal(await page.getByRole('button',{name:'Review '+label+' candidate',exact:true}).isDisabled(),true);assert.equal(await page.getByRole('button',{name:'Download corrected container',exact:true}).count(),0);checks[checks.length-1].unmodeled_manifest_metadata_readonly_no_review_or_export=true;await page.screenshot({path:path.join(out,mode+'-unknown-manifest-review-blocked.png'),fullPage:true});await context.close();
 }
 assert.deepEqual(errors,[]);const receipt={checked_at_utc:new Date().toISOString(),all_passed:true,feature:'complete explicit cleartext container source workflow',checks,synthetic_only:true,full_original_tax_compatibility:false,physical_phone_acceptance:false};fs.writeFileSync(path.join(out,'browser-acceptance.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();child.kill('SIGTERM');fs.rmSync(scratch,{recursive:true,force:true});});
