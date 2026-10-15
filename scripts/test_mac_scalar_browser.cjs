// Real headless UI; local HTTP/SQLite and browser Pyodide/IndexedDB.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn,spawnSync}=require('node:child_process');
const {chromium}=require(process.env.TAX_REBORN_PLAYWRIGHT||'playwright');
const root=path.resolve(__dirname,'..'),scratch=fs.mkdtempSync(path.join(os.tmpdir(),'tax-mac-decimal-')),fix=path.join(root,'fixtures/mac-scalar-taxml'),out=path.join(root,'qa/mac-scalar-browser');fs.mkdirSync(out,{recursive:true});
const child=spawn('python3',['-u','-c',`import sys,json;sys.path.insert(0,${JSON.stringify(root)});from http.server import ThreadingHTTPServer;import server;http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);http.store=server.Store(${JSON.stringify(scratch)});print(json.dumps({'port':http.server_port}),flush=True);http.serve_forever()`],{stdio:['ignore','pipe','pipe']});
let browser;const checks=[],errors=[];
async function inspect(page,blocked=false){
 await page.evaluate(()=>showTaxMLImport());
 await page.getByLabel('Choose plaintext TaxML or .tax container').setInputFiles(path.join(fix,blocked?'owned-mac-scalar-blocked.zip':'owned-mac-scalar.zip'));
 await page.getByLabel('Choose explicit TaxML wire profile').setInputFiles(path.join(fix,'profile.json'));
 await page.getByLabel('Choose caller-owned XPRF registries').setInputFiles(path.join(fix,'owned-mac-scalar.xprf'));
 await page.getByLabel('TaxML container declaration').selectOption('cleartext_persistence_container');
 await page.getByLabel('Acknowledge the selected unverified wire profile').check();
 await page.getByRole('button',{name:'Inspect locally',exact:true}).click();
 await page.getByRole('button',{name:'Inspect / edit decimal fields',exact:true}).waitFor({timeout:120000});
 await page.getByText('Complete cleartext container',{exact:true}).waitFor();
}
async function openDocuments(page){
 const header=page.getByRole('button',{name:'Documents',exact:true});
 if(await header.isVisible())await header.click();
 else{await page.getByRole('button',{name:'Open tax navigator',exact:true}).click();await page.getByRole('button',{name:'Save & export',exact:true}).click();await page.getByRole('button',{name:'Attach documents',exact:true}).click();}
 await page.getByRole('heading',{name:'Your local documents',exact:true}).waitFor();
}
async function snapshot(page){return page.evaluate(()=>({id:currentId,data:clone(data),metadata:clone(metadata),result:clone(result),revision,calculatedRevision}));}
(async()=>{
 const ready=await new Promise((resolve,reject)=>{let text='';child.stdout.on('data',b=>{text+=b;try{resolve(JSON.parse(text.split('\n')[0]));}catch{}});child.on('exit',code=>reject(Error('Synthetic API exited '+code)));});
 const origin='http://127.0.0.1:'+ready.port;browser=await chromium.launch({headless:true,...(process.env.TAX_REBORN_BROWSER?{executablePath:process.env.TAX_REBORN_BROWSER}:{})});
 for(const offline of [false,true]){
  const mode=offline?'Pyodide-IndexedDB':'HTTP-SQLite',context=await browser.newContext({viewport:{width:offline?390:1280,height:900},acceptDownloads:true});
  await context.route('**/*',route=>{const u=new URL(route.request().url());return u.origin===origin||['blob:','data:'].includes(u.protocol)?route.continue():route.abort();});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+(offline?'/?offline=1':''));await page.waitForFunction(()=>!document.querySelector('#save-button').disabled,{timeout:120000});
  await page.evaluate(async()=>{newReturn();data.name='Synthetic decimal source preservation';data.interest.push({payer:'Existing synthetic bank',taxable:'30.00',tax_exempt:'0',federal_withholding:'0'});metadata.income_document_records.interest.push(window.taxIncomePreparation.newRecord());await calculate();await saveReturn();await loadReturn(currentId);});
  const before=await snapshot(page),storedBefore=await page.evaluate(()=>api('/api/returns/'+currentId));
  await inspect(page);assert.equal(await page.getByRole('button',{name:/^Review (W-2|1099-INT|1099-DIV) candidate$/}).count(),7);
  await page.getByRole('button',{name:'Inspect / edit decimal fields',exact:true}).click();
  const select=page.getByLabel('Decimal source field',{exact:true}),input=page.getByLabel('Decimal source value',{exact:true}),confirmation=page.getByLabel('Confirm decimal source correction');
  assert.equal(await select.locator('option').count(),3);assert.equal(await input.inputValue(),'0.7');
  await page.getByText('Stored value 0.7 · decimal coefficient 7 · one fractional digit',{exact:true}).waitFor();
  await select.selectOption('2');assert.equal(await input.inputValue(),'-0.3');await select.selectOption('0');
  assert.equal(await page.getByRole('button',{name:/Add reviewed/}).count(),0);
  await input.fill('0.80');await confirmation.check();await page.getByRole('button',{name:'Download corrected container',exact:true}).click();
  await page.locator('.dialog-error').filter({hasText:'one fractional digit'}).waitFor({timeout:120000});
  assert.deepEqual(await snapshot(page),before);
  await input.fill('0.8');assert.equal(await confirmation.isChecked(),false);await confirmation.check();
  const wait=page.waitForEvent('download');await page.getByRole('button',{name:'Download corrected container',exact:true}).click();const download=await wait,file=path.join(out,mode+'-corrected.zip');await download.saveAs(file);
  assert.equal(await page.locator('.dialog-error').innerText(),'');
  const verify=spawnSync('python3',[path.join(root,'scripts/verify_mac_scalar_native.py'),file],{cwd:root,encoding:'utf8'});assert.equal(verify.status,0,verify.stdout+'\n'+verify.stderr);const readback=JSON.parse(verify.stdout);
  assert.deepEqual(await snapshot(page),before);assert.deepEqual(await page.evaluate(()=>api('/api/returns/'+currentId)),storedBefore);
  await page.screenshot({path:path.join(out,mode+'-decimal-corrected.png'),fullPage:true});
  await page.evaluate(()=>closeDialog());await inspect(page,true);await page.getByRole('button',{name:'Inspect / edit decimal fields',exact:true}).click();assert.equal(await page.getByLabel('Decimal source value',{exact:true}).isDisabled(),true);
  await page.screenshot({path:path.join(out,mode+'-manifest-readonly.png'),fullPage:true});
  await page.evaluate(()=>closeDialog());await page.evaluate(()=>showTaxMLImport());await page.getByText('Try independently generated binary samples',{exact:true}).click();await page.getByRole('button',{name:'Load Mac decimal source sample',exact:true}).click();await page.getByRole('button',{name:'Inspect / edit decimal fields',exact:true}).waitFor({timeout:120000});
  assert.deepEqual(await snapshot(page),before);
  await page.evaluate(()=>closeDialog());await page.reload();await page.waitForFunction(()=>!document.querySelector('#save-button').disabled,{timeout:120000});await page.waitForFunction(()=>result&&calculatedRevision===revision&&!calculationError,null,{timeout:120000});
  const reloaded=await snapshot(page);assert.deepEqual(reloaded.data,before.data);assert.deepEqual(reloaded.metadata,before.metadata);assert.deepEqual(reloaded.result,before.result);
  await openDocuments(page);
  const savedSource=page.locator('.document-card').filter({has:page.getByText('owned-mac-scalar.zip',{exact:true})});
  await savedSource.waitFor();assert.equal(await savedSource.count(),1);await savedSource.getByRole('button',{name:'Open source',exact:true}).click();
  await page.getByRole('button',{name:'Inspect / correct source',exact:true}).click();
  await page.getByRole('button',{name:'Inspect / edit decimal fields',exact:true}).click();
  assert.equal(await page.getByLabel('Decimal source value',{exact:true}).inputValue(),'0.7');
  const reopened=await snapshot(page);assert.deepEqual(reopened,reloaded);
  await page.evaluate(()=>closeDialog());await openDocuments(page);
  await page.getByLabel('Attach local documents',{exact:true}).setInputFiles(path.join(root,'web/icon-192.png'));
  const ordinary=page.locator('.document-card').filter({has:page.getByText('icon-192.png',{exact:true})});
  await ordinary.waitFor();assert.equal(await ordinary.getByRole('button',{name:'Open source',exact:true}).count(),0);
  assert.deepEqual(await snapshot(page),reloaded);await page.evaluate(()=>closeDialog());
  checks.push({mode,real_file_inputs:true,explicit_controller_profile:true,selection_across_entities_copies:true,invalid_two_fractional_digits_refused:true,retry_error_cleared:true,complete_container_system_download:true,readback,entire_current_return_and_result_unchanged:true,persisted_return_unchanged:true,reload_unchanged:true,saved_bound_source_reopened_after_reload:true,original_source_value_retained:true,ordinary_attachment_has_no_source_action:true,unknown_manifest_readonly:true,builtin_sample:true,native_runtime:0});console.log('PASS',mode);await context.close();
 }
 assert.deepEqual(errors,[]);const receipt={checked_at_utc:new Date().toISOString(),all_passed:true,checks,synthetic_only:true,all_inputs_UI:true,foreground_windows:0,whole_original_tax_compatibility:false};fs.writeFileSync(path.join(out,'browser-acceptance.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();child.kill('SIGTERM');fs.rmSync(scratch,{recursive:true,force:true});});
