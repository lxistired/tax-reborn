// Real main App, native-style file inputs and full downloads in both storage modes.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn,spawnSync}=require('node:child_process');
const {chromium}=require(process.env.TAX_REBORN_PLAYWRIGHT||'playwright');
const root=path.resolve(__dirname,'..'),scratch=fs.mkdtempSync(path.join(os.tmpdir(),'tax-instance-map-')),fix=path.join(root,'fixtures/binary-tax'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/instance-map-browser');fs.mkdirSync(out,{recursive:true});
const child=spawn(process.env.TAX_REBORN_TEST_PYTHON||'python3',['-u','-c',`import sys,json;sys.path.insert(0,${JSON.stringify(root)});from http.server import ThreadingHTTPServer;import server;h=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);h.store=server.Store(${JSON.stringify(scratch)});print(json.dumps({'port':h.server_port}),flush=True);h.serve_forever()`],{stdio:['ignore','pipe','pipe']});
let browser;const checks=[],errors=[];
const snapshot=page=>page.evaluate(()=>({id:currentId,data:clone(data),metadata:clone(metadata),result:clone(result),revision,calculatedRevision}));
(async()=>{
 const ready=await new Promise((resolve,reject)=>{let text='';child.stdout.on('data',b=>{text+=b;try{resolve(JSON.parse(text.split('\n')[0]));}catch{}});child.on('exit',code=>reject(Error('API exited '+code)));});
 const origin='http://127.0.0.1:'+ready.port;browser=await chromium.launch({headless:true,...(process.env.TAX_REBORN_BROWSER?{executablePath:process.env.TAX_REBORN_BROWSER}:{})});
 for(const offline of[false,true]){
  const mode=offline?'Pyodide-IndexedDB':'HTTP-SQLite',context=await browser.newContext({acceptDownloads:true,viewport:{width:offline?390:1280,height:900}});
  await context.route('**/*',r=>{const u=new URL(r.request().url());return u.origin===origin||['blob:','data:'].includes(u.protocol)?r.continue():r.abort();});
  const page=await context.newPage();page.setDefaultTimeout(120000);page.on('pageerror',e=>errors.push(e.message));let downloads=0;page.on('download',()=>downloads++);
  await page.goto(origin+(offline?'/?offline=1':''));await page.waitForFunction(()=>!document.querySelector('#save-button').disabled);
  await page.evaluate(async()=>{newReturn();data.name='Owned instance-map source preservation';data.interest.push({payer:'Existing owned bank',taxable:'30.00',tax_exempt:'0',federal_withholding:'0'});metadata.income_document_records.interest.push(window.taxIncomePreparation.newRecord());await calculate();await saveReturn();await loadReturn(currentId);});
  const before=await snapshot(page),stored=await page.evaluate(()=>api('/api/returns/'+currentId));
  await page.evaluate(()=>showTaxMLImport());await page.getByLabel('Choose plaintext TaxML or .tax container',{exact:true}).setInputFiles(path.join(fix,'instance-map-income.taxbin'));
  await page.getByLabel('Choose explicit TaxML wire profile',{exact:true}).setInputFiles(path.join(fix,'instance-map-profile.json'));
  const req=JSON.parse(fs.readFileSync(path.join(fix,'instance-map-income-request.json')));
  await page.getByLabel('Choose caller-owned XPRF registries',{exact:true}).setInputFiles(req.carriers.map((_,i)=>path.join(fix,'instance-map-registry-'+i+'.xprf')));
  await page.getByLabel('TaxML container declaration',{exact:true}).selectOption('binary_entity');await page.getByLabel('Acknowledge the selected unverified wire profile',{exact:true}).check();await page.getByRole('button',{name:'Inspect locally',exact:true}).click();
  await page.getByRole('button',{name:'Inspect / edit binary fields',exact:true}).click();const select=page.getByLabel('Binary form',{exact:true});assert.equal(await select.locator('option').count(),8);
  await page.locator('summary').filter({hasText:/^Saved FormSet /}).click();await page.getByText('Stored instance-address map · 3 byte pairs. Active cache and original cleanup have not run.',{exact:true}).waitFor();
  await select.selectOption('4');await page.locator('summary').filter({hasText:/^Saved FormSet /}).click();await page.getByText('Stored instance-address map · 3 byte pairs. Active cache and original cleanup have not run.',{exact:true}).waitFor();await select.selectOption('0');
  await page.getByLabel('Binary WAGES [0]',{exact:true}).fill('1234.57');await page.getByRole('button',{name:'Download corrected binary',exact:true}).click();await page.locator('.dialog-error').filter({hasText:'confirm all source corrections'}).waitFor();
  await page.getByLabel('Confirm binary source corrections',{exact:true}).check();const wait=page.waitForEvent('download');await page.getByRole('button',{name:'Download corrected binary',exact:true}).click();const dl=await wait,target=path.join(out,mode+'-instance-map-corrected.taxbin');await dl.saveAs(target);
  const c=spawnSync(process.env.TAX_REBORN_TEST_PYTHON||'python3',['-B',path.join(root,'scripts/verify_instance_map_native.py'),target],{cwd:root,encoding:'utf8'});assert.equal(c.status,0,c.stdout+'\n'+c.stderr);const readback=JSON.parse(c.stdout);
  assert.deepEqual(await snapshot(page),before);assert.deepEqual(await page.evaluate(()=>api('/api/returns/'+currentId)),stored);await page.screenshot({path:path.join(out,mode+'-instance-map-source.png'),fullPage:true});
  for(const invalidate of['input','confirmation','selection','close']){
   await page.getByLabel('Binary WAGES [0]',{exact:true}).fill('1234.58');await page.getByLabel('Confirm binary source corrections',{exact:true}).check();
   await page.evaluate(()=>{window.mapOriginalEngine=window.taxLocalEngine;window.mapHeld=false;window.mapGate=new Promise(r=>window.mapRelease=r);window.taxLocalEngine=async(command,payload)=>{const result=await window.mapOriginalEngine(command,payload);if(command==='binary_tax_edit'){window.mapHeld=true;await window.mapGate;}return result;};});
   const oldDownloads=downloads;await page.getByRole('button',{name:'Download corrected binary',exact:true}).click();await page.waitForFunction(()=>window.mapHeld);
   if(invalidate==='input')await page.getByLabel('Binary WAGES [0]',{exact:true}).fill('1234.59');else if(invalidate==='confirmation')await page.getByLabel('Confirm binary source corrections',{exact:true}).uncheck();else if(invalidate==='selection')await select.selectOption('4');else await page.getByRole('button',{name:'Close',exact:true}).click();
   await page.evaluate(()=>window.mapRelease());
   if(invalidate!=='close')await page.locator('.dialog-error').filter({hasText:'source selection or current return changed'}).waitFor();
   await page.evaluate(()=>{window.taxLocalEngine=window.mapOriginalEngine;});assert.equal(downloads,oldDownloads);assert.deepEqual(await snapshot(page),before);
   if(invalidate!=='close')await select.selectOption('0');
  }
  await page.evaluate(()=>{closeDialog();showTaxMLImport();});await page.getByText('Try independently generated binary samples',{exact:true}).click();await page.getByRole('button',{name:'Load stored instance-map sample',exact:true}).click();await page.getByRole('button',{name:'Inspect / edit binary fields',exact:true}).waitFor();assert.deepEqual(await snapshot(page),before);
  await page.evaluate(()=>closeDialog());await page.reload();await page.waitForFunction(()=>!document.querySelector('#save-button').disabled);await page.waitForFunction(()=>result&&calculatedRevision===revision&&!calculationError);const reloaded=await snapshot(page);assert.deepEqual(reloaded.data,before.data);assert.deepEqual(reloaded.metadata,before.metadata);assert.deepEqual(reloaded.result,before.result);assert.deepEqual(await page.evaluate(()=>api('/api/returns/'+currentId)),stored);
  checks.push({mode,real_file_inputs_and_worker:true,two_FormSet_maps_visible:true,full_8360_byte_download_and_readback:readback,source_confirmation_required:true,real_late_Worker_reply_after_input_selection_revoked_confirmation_or_close_has_no_download:true,builtin_sample:true,complete_current_return_and_result_persistence_reload_unchanged:true,original_runtime:0,full_original_compatibility:false});console.log('PASS',mode);await context.close();
 }
 assert.deepEqual(errors,[]);const receipt={at_utc:new Date().toISOString(),all_passed:true,checks,foreground_windows:0};fs.writeFileSync(path.join(out,'browser-acceptance.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();child.kill('SIGTERM');fs.rmSync(scratch,{recursive:true,force:true});});
