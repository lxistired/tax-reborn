// Actual main App, file inputs and downloads, HTTP/SQLite and 390px Pyodide/IndexedDB.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn,spawnSync}=require('node:child_process');
const {chromium}=require(process.env.TAX_REBORN_PLAYWRIGHT||'playwright');
const root=path.resolve(__dirname,'..'),scratch=fs.mkdtempSync(path.join(os.tmpdir(),'tax-date-source-')),fix=path.join(root,'fixtures/mac-date-taxml'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/mac-date-browser');fs.mkdirSync(out,{recursive:true});
const child=spawn(process.env.TAX_REBORN_TEST_PYTHON||'python3',['-u','-c',`import sys,json;sys.path.insert(0,${JSON.stringify(root)});from http.server import ThreadingHTTPServer;import server;h=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);h.store=server.Store(${JSON.stringify(scratch)});print(json.dumps({'port':h.server_port}),flush=True);h.serve_forever()`],{stdio:['ignore','pipe','pipe']});
let browser;const checks=[],errors=[];
const snapshot=page=>page.evaluate(()=>({id:currentId,data:clone(data),metadata:clone(metadata),result:clone(result),revision,calculatedRevision}));
async function inspect(page,blocked=false){
 await page.evaluate(()=>{closeDialog();showTaxMLImport();});
 await page.getByLabel('Choose plaintext TaxML or .tax container',{exact:true}).setInputFiles(path.join(fix,blocked?'owned-mac-date-blocked.zip':'owned-mac-date.zip'));
 await page.getByLabel('Choose explicit TaxML wire profile',{exact:true}).setInputFiles(path.join(fix,'profile.json'));
 await page.getByLabel('Choose caller-owned XPRF registries',{exact:true}).setInputFiles(path.join(fix,'owned-mac-date.xprf'));
 await page.getByLabel('TaxML container declaration',{exact:true}).selectOption('cleartext_persistence_container');
 await page.getByLabel('Acknowledge the selected unverified wire profile',{exact:true}).check();
 await page.getByRole('button',{name:'Inspect locally',exact:true}).click();
 await page.getByRole('button',{name:'Inspect / edit date fields',exact:true}).waitFor({timeout:120000});
 await page.getByRole('button',{name:'Inspect / edit date fields',exact:true}).click();
}
async function openDocuments(page){
 await page.evaluate(()=>closeDialog());
 if(await page.getByRole('button',{name:'Documents',exact:true}).isVisible())await page.getByRole('button',{name:'Documents',exact:true}).click();
 else{await page.getByRole('button',{name:'Open tax navigator',exact:true}).click();await page.getByRole('button',{name:'Save & export',exact:true}).click();await page.getByRole('button',{name:'Attach documents',exact:true}).click();}
 await page.getByRole('heading',{name:'Your local documents',exact:true}).waitFor();
}
(async()=>{
 const ready=await new Promise((resolve,reject)=>{let text='';child.stdout.on('data',b=>{text+=b;try{resolve(JSON.parse(text.split('\n')[0]));}catch{}});child.on('exit',code=>reject(Error('API exited '+code)));});
 const origin='http://127.0.0.1:'+ready.port;browser=await chromium.launch({headless:true,...(process.env.TAX_REBORN_BROWSER?{executablePath:process.env.TAX_REBORN_BROWSER}:{})});
 for(const offline of[false,true]){
  const mode=offline?'Pyodide-IndexedDB':'HTTP-SQLite',context=await browser.newContext({acceptDownloads:true,viewport:{width:offline?390:1280,height:900}});
  await context.route('**/*',r=>{const u=new URL(r.request().url());return u.origin===origin||['blob:','data:'].includes(u.protocol)?r.continue():r.abort();});
  const page=await context.newPage();page.setDefaultTimeout(120000);page.on('pageerror',e=>errors.push(e.message));let downloads=0;page.on('download',()=>downloads++);
  await page.goto(origin+(offline?'/?offline=1':''));await page.waitForFunction(()=>!document.querySelector('#save-button').disabled,{timeout:120000});
  await page.evaluate(async()=>{newReturn();data.name='Owned date-source retention test';data.interest.push({payer:'Existing owned bank',taxable:'30.00',tax_exempt:'0',federal_withholding:'0'});metadata.income_document_records.interest.push(window.taxIncomePreparation.newRecord());await calculate();await saveReturn();await loadReturn(currentId);});
  const before=await snapshot(page),stored=await page.evaluate(()=>api('/api/returns/'+currentId));
  await inspect(page);const select=page.getByLabel('Date source field',{exact:true}),input=page.getByLabel('Date source value',{exact:true}),confirmation=page.getByLabel('Confirm date source correction',{exact:true});
  assert.equal(await select.locator('option').count(),9);assert.equal(await input.inputValue(),'01/02/2000');assert.equal(await page.getByRole('button',{name:/Add reviewed/}).count(),0);
  await input.fill('2000-02-29');await confirmation.check();await page.getByRole('button',{name:'Download corrected container',exact:true}).click();
  await page.locator('.dialog-error').filter({hasText:'Exact MM/DD/YYYY'}).waitFor();assert.equal(downloads,0);assert.deepEqual(await snapshot(page),before);
  const readbacks=[];
  for(const[index,value]of[[0,'02/29/2000'],[4,'12-31'],[8,'2025-12']]){
   await select.selectOption(String(index));await confirmation.check();await input.fill(value);assert.equal(await confirmation.isChecked(),false);await confirmation.check();
   const wait=page.waitForEvent('download');await page.getByRole('button',{name:'Download corrected container',exact:true}).click();const dl=await wait,target=path.join(out,mode+'-'+index+'-corrected.zip');await dl.saveAs(target);
   const verify=spawnSync(process.env.TAX_REBORN_TEST_PYTHON||'python3',['-B',path.join(root,'scripts/verify_mac_date_native.py'),target,'--index',String(index),'--value',value],{cwd:root,encoding:'utf8'});assert.equal(verify.status,0,verify.stdout+'\n'+verify.stderr);readbacks.push(JSON.parse(verify.stdout));
   assert.equal(await page.locator('.dialog-error').innerText(),'');assert.deepEqual(await snapshot(page),before);assert.deepEqual(await page.evaluate(()=>api('/api/returns/'+currentId)),stored);
  }
  await page.screenshot({path:path.join(out,mode+'-date-corrected.png'),fullPage:true});
  // Hold a real Worker response, then change the input, selection, confirmation or dialog.
  for(const invalidate of['input','confirmation','selection','close']){
   await input.fill('2026-01');await confirmation.check();
   await page.evaluate(()=>{window.dateOriginalEngine=window.taxLocalEngine;window.dateHeld=false;window.dateGate=new Promise(r=>window.dateRelease=r);window.taxLocalEngine=async(command,payload)=>{const result=await window.dateOriginalEngine(command,payload);if(command==='taxml_export'&&payload.expected_date_sha256){window.dateHeld=true;await window.dateGate;}return result;};});
   const oldDownloads=downloads;await page.getByRole('button',{name:'Download corrected container',exact:true}).click();await page.waitForFunction(()=>window.dateHeld);
   if(invalidate==='input')await input.fill('2026-02');else if(invalidate==='confirmation')await confirmation.uncheck();else if(invalidate==='selection')await select.selectOption('0');else await page.getByRole('button',{name:'Close',exact:true}).click();
   await page.evaluate(()=>window.dateRelease());
   if(invalidate!=='close')await page.locator('.dialog-error').filter({hasText:'source selection or current return changed'}).waitFor();
   else await page.waitForFunction(()=>!document.querySelector('[aria-label="Date source fields"]'));
   await page.evaluate(()=>{window.taxLocalEngine=window.dateOriginalEngine;});assert.equal(downloads,oldDownloads);assert.deepEqual(await snapshot(page),before);
   if(invalidate!=='close'){await select.selectOption('8');}else await inspect(page);
  }
  await inspect(page,true);assert.equal(await input.isDisabled(),true);await page.screenshot({path:path.join(out,mode+'-date-readonly.png'),fullPage:true});
  await page.evaluate(()=>{closeDialog();showTaxMLImport();});await page.getByText('Try independently generated binary samples',{exact:true}).click();await page.getByRole('button',{name:'Load Mac date source sample',exact:true}).click();await page.getByRole('button',{name:'Inspect / edit date fields',exact:true}).waitFor();
  assert.deepEqual(await snapshot(page),before);await page.evaluate(()=>closeDialog());await page.reload();await page.waitForFunction(()=>!document.querySelector('#save-button').disabled);await page.waitForFunction(()=>result&&calculatedRevision===revision&&!calculationError);
  const reloaded=await snapshot(page);assert.deepEqual(reloaded.data,before.data);assert.deepEqual(reloaded.metadata,before.metadata);assert.deepEqual(reloaded.result,before.result);assert.deepEqual(await page.evaluate(()=>api('/api/returns/'+currentId)),stored);
  await openDocuments(page);const row=page.locator('.document-card').filter({has:page.getByText('owned-mac-date.zip',{exact:true})}).first();await row.getByRole('button',{name:'Open source',exact:true}).click();await page.getByRole('button',{name:'Inspect / correct source',exact:true}).click();await page.getByRole('button',{name:'Inspect / edit date fields',exact:true}).click();assert.equal(await input.inputValue(),'01/02/2000');assert.deepEqual(await snapshot(page),reloaded);
  checks.push({mode,real_file_inputs_and_worker:true,date_day_month_three_copies_entities:true,readbacks,invalid_ISO_date_refused:true,changed_input_clears_confirmation:true,real_late_Worker_reply_after_input_selection_revoked_confirmation_or_close_has_no_download:true,full_current_return_result_persistence_and_reload_unchanged:true,bound_source_reopened_original_values:true,unknown_manifest_readonly:true,builtin_sample:true,original_runtime:0,native_date_loading:false});console.log('PASS',mode);await context.close();
 }
 assert.deepEqual(errors,[]);const receipt={at_utc:new Date().toISOString(),all_passed:true,checks,foreground_windows:0,original_taxpayer_fixture:0,full_original_compatibility:false};fs.writeFileSync(path.join(out,'browser-acceptance.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();child.kill('SIGTERM');fs.rmSync(scratch,{recursive:true,force:true});});
