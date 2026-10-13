// Isolated headless app test with a synthetic temporary SQLite/IndexedDB store.
// OCR extraction is stubbed only to verify the reviewed-candidate UI contract.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),scratch=fs.mkdtempSync(path.join(os.tmpdir(),'tax-w2-review-'));
const child=spawn('python3',['-u','-c',`import sys,json;sys.path.insert(0,${JSON.stringify(root)});from http.server import ThreadingHTTPServer;import server;http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);http.store=server.Store(${JSON.stringify(scratch)});print(json.dumps({'port':http.server_port}),flush=True);http.serve_forever()`],{stdio:['ignore','pipe','pipe']});
const checks=[],errors=[];let browser;
async function test(name,f){await f();checks.push(name);console.log('PASS',name);}
(async()=>{
 const ready=await new Promise((resolve,reject)=>{let text='';child.stdout.on('data',buffer=>{text+=buffer;const line=text.split('\n')[0];try{resolve(JSON.parse(line));}catch{}});child.on('exit',code=>reject(Error('Test API exited '+code)));});
 const origin='http://127.0.0.1:'+ready.port;browser=await chromium.launch({headless:true});const context=await browser.newContext();
 await context.route('**/*',route=>{const url=new URL(route.request().url());return url.origin===origin||url.protocol==='blob:'||url.protocol==='data:'?route.continue():route.abort();});
 const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
 await page.goto(origin);await page.waitForFunction(()=>!document.querySelector('#save-button').disabled);
 let record;
 await test('Real API returns independent unreviewed W2 identities; frontend loads owner correctly',async()=>{
  record=await page.evaluate(async()=>{const s=await api('/api/schema'),input=clone(s.default_return),t=s.capabilities.row_templates.w2;input.name='Synthetic W2 UI review';input.filing_status='mfj';input.w2=[{...t,employer:'Synthetic A',owner:'taxpayer',wages:'60000',social_security_wages:'60000',medicare_wages:'60000'},{...t,employer:'Synthetic B',owner:'spouse',wages:'25000',social_security_wages:'25000',medicare_wages:'25000'}];const saved=await api('/api/returns',{method:'POST',body:JSON.stringify({data:input})});await loadReturn(saved.id);navigate('w2');return saved;});
  assert.equal(record.metadata.w2_records.length,2);assert.equal(new Set(record.metadata.w2_records.map(x=>x.record_id)).size,2);assert.ok(record.metadata.w2_records.every(x=>!x.reviewed));
  await page.locator('.record-header-button').nth(0).click();await page.locator('.record-header-button').nth(1).click();
  assert.equal(await page.locator('.record').nth(1).getByLabel('Whose W-2 is this?').inputValue(),'spouse');
 });
 await test('Manual checkbox marks each specific W2; review stays outside federal data',async()=>{
  for(let n=0;n<2;n++){await page.locator('[data-w2-review-control]').nth(n).check();await page.waitForFunction(n=>metadata.w2_records[n].reviewed,n);}
  const state=await page.evaluate(()=>({metadata:clone(metadata),data:clone(data)}));assert.ok(state.metadata.w2_records.every(x=>x.reviewed));assert.equal(state.data.metadata,undefined);
  await page.evaluate(()=>saveReturn());
 });
 await test('Cent-equivalent formatting retains review; actual amount and owner edits clear only selected W2',async()=>{
  const wage=page.locator('.record').nth(0).getByLabel('Box 1 · Wages, tips, other compensation');
  await wage.fill('60000.00');assert.deepEqual(await page.evaluate(()=>metadata.w2_records.map(x=>x.reviewed)),[true,true]);
  await wage.fill('60000.01');assert.deepEqual(await page.evaluate(()=>metadata.w2_records.map(x=>x.reviewed)),[false,true]);
  await page.locator('[data-w2-review-control]').nth(0).check();await page.waitForFunction(()=>metadata.w2_records[0].reviewed);
  await page.locator('.record').nth(0).getByLabel('Whose W-2 is this?').selectOption('spouse');assert.deepEqual(await page.evaluate(()=>metadata.w2_records.map(x=>x.reviewed)),[false,true]);
 });
 await test('Delete first W2 preserves survivor stable identity, owner and review; addition is a new unreviewed identity',async()=>{
  const survivor=record.metadata.w2_records[1].record_id;await page.getByRole('button',{name:'Remove W-2 1',exact:true}).click();
  assert.equal(await page.evaluate(()=>metadata.w2_records[0].record_id),survivor);assert.equal(await page.evaluate(()=>data.w2[0].owner),'spouse');assert.equal(await page.evaluate(()=>metadata.w2_records[0].reviewed),true);
  await page.getByRole('button',{name:'+ Add another W-2',exact:true}).click();
  assert.notEqual(await page.evaluate(()=>metadata.w2_records[1].record_id),survivor);assert.equal(await page.evaluate(()=>metadata.w2_records[1].reviewed),false);
  const row=page.locator('.record').nth(1);await row.getByLabel('Employer name').fill('Synthetic C');await row.getByLabel('Box 1 · Wages, tips, other compensation').fill('500');
  await row.locator('[data-w2-review-control]').check();await page.waitForFunction(()=>metadata.w2_records[1].reviewed);await page.evaluate(()=>saveReturn());
 });
 let before;
 await test('Actual reload checkpoint and SQLite reopen preserve IDs/review/ownership',async()=>{
  before=await page.evaluate(()=>({id:currentId,metadata:clone(metadata),owners:data.w2.map(x=>x.owner)}));await page.reload();await page.waitForFunction(()=>!document.querySelector('#save-button').disabled);
  const after=await page.evaluate(()=>({id:currentId,metadata:clone(metadata),owners:data.w2.map(x=>x.owner)}));assert.deepEqual(after,before);
  const body=await page.locator('body').innerText();for(const entry of before.metadata.w2_records)assert.ok(!body.includes(entry.record_id));
 });
 await test('OCR candidate confirmation links only its local source and marks imported record reviewed',async()=>{
  await page.evaluate(()=>{window.extractTaxDocument=async()=>({form_type:'w2',candidates:{employer:{value:'Synthetic D'},owner:{value:'spouse'},wages:{value:'1000'},federal_withholding:{value:'100'},social_security_wages:{value:'1000'},medicare_wages:{value:'1000'}},warnings:[],text:'Synthetic OCR fixture; not OCR accuracy evidence'});});
  await page.getByRole('button',{name:'Documents',exact:true}).click();
  await page.getByLabel('Attach local documents').setInputFiles({name:'Synthetic-D.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')});
  await page.getByRole('button',{name:'Extract W-2 fields',exact:true}).click();
  await page.getByLabel('I verified this is a 2025 W-2 and checked each imported amount against the document.').check();
  await page.getByRole('button',{name:'Add reviewed W-2',exact:true}).click();await page.waitForFunction(()=>data.w2.length===3);
  const item=await page.evaluate(()=>metadata.w2_records[2]);assert.equal(item.reviewed,true);assert.equal(item.source_document.return_id,before.id);assert.equal(item.source_document.name,'Synthetic-D.png');assert.equal(await page.evaluate(()=>data.w2[2].owner),'spouse');
  await page.getByRole('button',{name:'View source document',exact:true}).click();await page.getByRole('dialog',{name:'Your W-2 source document'}).waitFor();assert.equal(await page.locator('[alt="Original W-2 source document"]').count(),1);await page.getByRole('button',{name:'Close',exact:true}).click();
 });
 await test('Actual JSON export + restore as new draft retain record state without linking old attachments into new return',async()=>{
  const restored=await page.evaluate(async()=>{await saveReturn();const backup=await api('/api/returns/'+currentId+'/export.json'),newId=crypto.randomUUID(),parsed=parseReturnBackup(JSON.stringify(backup)),report=await restoreReturnBackup(parsed,newId);await loadReturn(report.id);navigate('w2');return {backup,report,current:currentId,metadata:clone(metadata),documents:(await documentsForReturn(currentId)).length};});
  assert.notEqual(restored.current,restored.backup.id);assert.equal(restored.documents,0);assert.deepEqual(restored.metadata,restored.backup.metadata);assert.ok((await page.locator('body').innerText()).includes('Source attachment not restored'));
  const source=restored.metadata.w2_records[2].source_document;const message=await page.evaluate(async source=>{try{await showW2Source(source);return '';}catch(error){return error.message;}},source);assert.ok(message.includes('not restored'));
 });
 await test('Frontend and Python cent-normalized fingerprint agree for Unicode/leading zeros/negative zero',async()=>{
  const probes=[{employer:'Synthetic 基金𝟚',owner:'taxpayer',wages:'060000.00'},{employer:'Synthetic zero',owner:'spouse',wages:'-0.00'}];
  for(const row of probes){const actual=await page.evaluate(row=>window.taxRecordMetadata.fingerprint(row),row);const {spawnSync}=require('node:child_process'),python=spawnSync('python3',['-c',`import sys,json;sys.path.insert(0,${JSON.stringify(root)});import return_metadata,tax_engine;print(return_metadata.fingerprint(json.loads(sys.argv[1]),tax_engine.ROW_DEFAULTS['w2']))`,JSON.stringify(row)],{encoding:'utf8'});assert.equal(python.status,0,python.stderr);assert.equal(actual,python.stdout.trim());}
 });
 await test('Actual offline worker + IndexedDB API save/reopen/export retain per-W2 metadata',async()=>{
  const offlineContext=await browser.newContext({viewport:{width:390,height:844}}),offlinePage=await offlineContext.newPage();
  await offlineContext.route('**/*',route=>{const url=new URL(route.request().url());return url.origin===origin||url.protocol==='blob:'||url.protocol==='data:'?route.continue():route.abort();});
  await offlinePage.goto(origin+'/?offline=1');await offlinePage.waitForFunction(()=>!document.querySelector('#save-button').disabled,{timeout:120000});
  const roundtrip=await offlinePage.evaluate(async()=>{const s=await api('/api/schema'),input=clone(s.default_return),template=s.capabilities.row_templates.w2;input.name='Synthetic offline W2 review';input.filing_status='mfj';input.w2=[{...template,employer:'Offline A',owner:'taxpayer',wages:'60000'},{...template,employer:'Offline B',owner:'spouse',wages:'25000'}];let saved=await api('/api/returns',{method:'POST',body:JSON.stringify({data:input})});await loadReturn(saved.id);navigate('w2');await markW2Reviewed(metadata.w2_records[1].record_id,true);await saveReturn();const exported=await api('/api/returns/'+currentId+'/export.json');const reopened=await api('/api/returns/'+currentId);return {exported,reopened};});
  assert.deepEqual(roundtrip.exported.metadata,roundtrip.reopened.metadata);assert.deepEqual(roundtrip.reopened.metadata.w2_records.map(row=>row.reviewed),[false,true]);assert.equal(roundtrip.reopened.data.w2[1].owner,'spouse');
  await offlinePage.reload();await offlinePage.waitForFunction(()=>!document.querySelector('#save-button').disabled,{timeout:120000});assert.equal(await offlinePage.evaluate(()=>metadata.w2_records[1].record_id),roundtrip.reopened.metadata.w2_records[1].record_id);
  await offlinePage.screenshot({path:path.join(root,'qa/w2-review-mobile.png'),fullPage:true});await offlineContext.close();
 });
 await page.screenshot({path:path.join(root,'qa/w2-review-desktop.png'),fullPage:true});
 assert.deepEqual(errors,[]);
 const report={date:new Date().toISOString(),all_passed:true,checks,tests:checks.length,backend:'real isolated loopback API + SQLite; real browser IndexedDB workspace',ocr_scope:'Synthetic extractor stub verifies review/source UI only; no camera or OCR accuracy claim',original_vendor_executed:false,tax_oracles_modified:false};
 fs.writeFileSync(path.join(root,'qa/w2-review-browser-tests.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();child.kill('SIGTERM');fs.rmSync(scratch,{recursive:true,force:true});});
