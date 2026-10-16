const fs=require('node:fs'),crypto=require('node:crypto'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require(process.env.TAX_REBORN_PLAYWRIGHT||'playwright');
const root=path.resolve(__dirname,'..'),fixtureDir=path.join(root,'web/samples/default-encrypted'),sourceHash=crypto.createHash('sha256').update(Buffer.from(JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/auto-array-income-request.json'),'utf8')).base64,'base64')).digest('hex');
async function startServer(scratch){
  const py=process.env.TAX_REBORN_TEST_PYTHON||'python3';
  const child=spawn(py,['-B','-u','-c',`import json,sys;sys.path.insert(0,${JSON.stringify(root)});from http.server import ThreadingHTTPServer;import server;h=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);h.store=server.Store(${JSON.stringify(scratch)});print(json.dumps({'port':h.server_port}),flush=True);h.serve_forever()`],{stdio:['ignore','pipe','pipe']});
  const ready=await new Promise((resolve,reject)=>{let text='';child.stdout.on('data',chunk=>{text+=chunk;try{resolve(JSON.parse(text.split('\n')[0]));}catch{}});child.on('exit',code=>reject(Error('server exit '+code)));});
  return {child,port:ready.port};
}
async function openReturn(page){
  await page.locator('#save-button:not([disabled])').waitFor();
  return page.evaluate(async()=>{newReturn();data.name='Default encrypted owned import';await calculate();await saveReturn();return currentId;});
}
async function inspectInventory(page,returnId,archive){
  await page.locator('#documents-button').click();
  await page.getByRole('button',{name:'Open TaxML / binary .tax',exact:true}).click();
  await page.locator('select[aria-label="TaxML container declaration"]').selectOption('default_encrypted_tax');
  await page.locator('input[aria-label="Choose plaintext TaxML or .tax container"]').setInputFiles(path.join(fixtureDir,archive));
  await page.locator('input[aria-label="Choose local default encrypted compatibility configuration"]').setInputFiles(path.join(fixtureDir,'public-test-compatibility.json'));
  await page.getByRole('button',{name:'Inspect locally',exact:true}).click();
  await page.getByRole('heading',{name:'Default encrypted source inventory'}).waitFor();
  const body=await page.locator('[role="dialog"]').textContent();
  assert.match(body,/main\.entity/);assert.match(body,/profile\.entity/);assert.match(body,/unrecognized\.member|retained\.opaque/);
  assert.match(body,/Original-compatible writing and engine execution are not claimed/);
  const persisted=await page.evaluate(async id=>documentsForReturn(id),returnId);
  const archiveRow=persisted.find(row=>row.name===archive&&row.default_encrypted?.branch==='current');
  assert.ok(archiveRow,'encrypted archive was not persisted');
  const inventory=archiveRow.default_encrypted.inventory||[];
  const entityCount=inventory.filter(item=>item.role==='manifest_entity').length;
  assert.equal(inventory.length,6);assert.equal(entityCount,4);assert.equal(new Set(inventory.map(item=>item.member_name)).size,6);
  return {body,persisted,inventory,entityCount};
}
async function inspectBinaryEntity(page){
  await page.locator('select[aria-label="Choose decrypted entity member"]').evaluate(select=>{const option=[...select.options].find(item=>item.textContent.includes('main.entity'));if(!option)throw new Error('main.entity option missing');select.value=option.value;select.dispatchEvent(new Event('change',{bubbles:true}));});
  await page.locator('input[aria-label="Choose entity wire profile"]').setInputFiles(path.join(fixtureDir,'synthetic-default-binary-profile.json'));
  await page.locator('input[aria-label="Choose ordered entity registries"]').setInputFiles([
    path.join(fixtureDir,'synthetic-default-binary-carrier-0.xprf'),
    path.join(fixtureDir,'synthetic-default-binary-carrier-1.xprf'),
  ]);
  await page.getByRole('button',{name:'Inspect selected entity locally',exact:true}).click();
  await page.getByRole('heading',{name:'TaxML inspection results'}).waitFor();
  const body=await page.locator('[role="dialog"]').textContent();
  assert.match(body,/Source SHA-256/);assert.match(body,/Binary source fields/);assert.match(body,/nonempty supported structures/);
  assert.doesNotMatch(body,/No supported W-2, 1099-DIV or 1099-INT candidates were found/);
  assert.match(body,/Reader structure: (\d+) forms · (\d+) fields · (\d+) tables · (\d+) child forms · (\d+) saved links/);
  const structure=[...body.match(/Reader structure: (\d+) forms · (\d+) fields · (\d+) tables · (\d+) child forms · (\d+) saved links/)].slice(1).map(Number);
  assert.ok(structure.every(value=>value>0),'reader returned no nonempty row/child/link structure');
  assert.match(body,/Review (1099-INT|1099-DIV|W-2) candidate/);
  const candidateButtons=await page.getByRole('button',{name:/Review (1099-INT|1099-DIV|W-2) candidate/}).allTextContents();
  return {body,candidateButtons,structure};
}
async function negativeImport(page,returnId,archive,expected,configInput){
  const baseline=await page.evaluate(async id=>({data:{w2:data.w2.length,interest:data.interest.length,dividends:data.dividends.length},docs:(await documentsForReturn(id)).map(row=>({name:row.name,sha:row.default_encrypted?.encrypted_source_sha256||null})).sort((a,b)=>a.name.localeCompare(b.name))}),returnId);
  if(await page.getByRole('heading',{name:'Default encrypted source inventory'}).count())await page.getByRole('button',{name:'Close',exact:true}).click();
  await page.locator('#documents-button').click();
  await page.getByRole('button',{name:'Open TaxML / binary .tax',exact:true}).click();
  await page.locator('select[aria-label="TaxML container declaration"]').selectOption('default_encrypted_tax');
  let bytes=fs.readFileSync(path.join(fixtureDir,archive==='corrupt.tax'?'synthetic-default-binary-array.tax':archive));
  if(archive==='corrupt.tax')bytes=Buffer.from(bytes.map((value,index)=>index===bytes.length-1?value^255:value));
  await page.locator('input[aria-label="Choose plaintext TaxML or .tax container"]').setInputFiles({name:archive,mimeType:'application/octet-stream',buffer:bytes});
  if(configInput?.buffer)await page.locator('input[aria-label="Choose local default encrypted compatibility configuration"]').setInputFiles(configInput);
  else await page.locator('input[aria-label="Choose local default encrypted compatibility configuration"]').setInputFiles(path.join(fixtureDir,'public-test-compatibility.json'));
  await page.getByRole('button',{name:'Inspect locally',exact:true}).click();
  await page.waitForTimeout(500);
  const state=await page.evaluate(()=>({toast:document.querySelector('#toast')?.textContent,dialogError:[...document.querySelectorAll('.dialog-error')].map(node=>node.textContent)}));
  const message=state.dialogError.find(Boolean)||state.toast||'';assert.match(message,expected);
  const after=await page.evaluate(async id=>({data:{w2:data.w2.length,interest:data.interest.length,dividends:data.dividends.length},docs:(await documentsForReturn(id)).map(row=>({name:row.name,sha:row.default_encrypted?.encrypted_source_sha256||null})).sort((a,b)=>a.name.localeCompare(b.name))}),returnId);assert.deepEqual(after,baseline);
  await page.getByRole('button',{name:'Close',exact:true}).click();
  return message;
}
async function runNegativeChecks(page,returnId){
  const config=Buffer.from('{"format":"tax-reborn-default-tax-crypto-v1",');
  const wrong=await negativeImport(page,returnId,'synthetic-default-binary-array.tax',/compatibility|JSON/i,{name:'wrong-config.json',mimeType:'application/json',buffer:config});
  const corrupt=await negativeImport(page,returnId,'corrupt.tax',/archive|zip|member|corrupt|invalid|local processing/i);
  const type1=await negativeImport(page,returnId,'synthetic-identity-protected.tax',/identity|unsupported|protected|local processing/i);
  const type2=await negativeImport(page,returnId,'synthetic-password-protected.tax',/security|password|unsupported|protected|local processing/i);
  await page.locator('#documents-button').click();await page.getByRole('button',{name:'Reopen encrypted source',exact:true}).click();await page.locator('input[aria-label="Choose local default encrypted compatibility configuration"]').setInputFiles(path.join(fixtureDir,'public-test-compatibility.json'));await page.getByRole('button',{name:'Inspect saved archive',exact:true}).click();await page.getByRole('heading',{name:'Default encrypted source inventory'}).waitFor();
  return {all_passed:true,wrong_config:wrong,corrupt_archive:corrupt,type1_identity:type1,type2_security:type2};
}
async function reopenEncryptedSource(page,returnId){
  await page.getByRole('button',{name:'Close',exact:true}).click();
  await page.locator('#documents-button').click();
  await page.getByRole('button',{name:'Reopen encrypted source',exact:true}).click();
  await page.locator('input[aria-label="Choose local default encrypted compatibility configuration"]').setInputFiles(path.join(fixtureDir,'public-test-compatibility.json'));
  await page.getByRole('button',{name:'Inspect saved archive',exact:true}).click();
  await page.getByRole('heading',{name:'Default encrypted source inventory'}).waitFor();
  const body=await page.locator('[role="dialog"]').textContent();assert.match(body,/main\.entity/);assert.match(body,/encrypted source SHA-256/);
  await page.getByRole('button',{name:'Close',exact:true}).click();
}
async function reopenDecodedSource(page){
  await page.evaluate(()=>{if(typeof closeDialog==='function')closeDialog();});
  await page.locator('#documents-button').click();
  await page.getByRole('button',{name:'Open source',exact:true}).click();
  await page.getByRole('button',{name:'Inspect / correct source',exact:true}).click();
  await page.getByRole('heading',{name:'TaxML inspection results'}).waitFor();
}

async function clickCandidateAt(page,name,index){
  const buttons=page.getByRole('button',{name,exact:true});
  if(index>=await buttons.count())throw new Error('Candidate index missing: '+name+' '+index);
  await buttons.nth(index).click();
}
async function clickEnabled(page,name){
  const buttons=page.getByRole('button',{name,exact:true});
  for(let i=0;i<await buttons.count();i++){const button=buttons.nth(i);if(await button.isEnabled()){await button.click();return;}}
  throw new Error('No enabled candidate button: '+name);
}
async function reviewCandidates(page){
  await clickEnabled(page,'Review W-2 candidate');
  await page.getByRole('heading',{name:'Review TaxML W-2 candidate'}).waitFor();
  await page.locator('select[aria-label="Whose W-2 is this?"]').selectOption('taxpayer');
  await page.locator('input[aria-label="Box 1 · Wages, tips, other compensation"]').fill('50000.00');
  await page.locator('input[aria-label="Box 2 · Federal income tax withheld"]').fill('5000.00');
  await page.locator('input[aria-label="Confirm all TaxML W-2 amounts and ownership"]').check();
  await page.getByRole('button',{name:'Add reviewed W-2',exact:true}).click();
  await reopenDecodedSource(page);
  for(let i=0;i<2;i++){
    await clickCandidateAt(page,'Review 1099-INT candidate',i);
    await page.getByRole('heading',{name:'Review TaxML 1099-INT candidate'}).waitFor();
    await page.locator('input[aria-label="1099-INT payer name"]').fill('Synthetic Bank '+i);
    await page.locator('input[aria-label="Confirm supported 1099-INT situation"]').check();
    await page.locator('input[aria-label="Confirm all TaxML 1099-INT amounts and household"]').check();
    await page.getByRole('button',{name:'Add reviewed 1099-INT',exact:true}).click();
    const intCount=await page.evaluate(()=>data.interest.length);if(intCount<1){const err=await page.locator('.dialog-error').textContent();throw new Error('1099-INT review did not add: '+err);}
    await reopenDecodedSource(page);
  }
  await clickEnabled(page,'Review 1099-DIV candidate');
  await page.getByRole('heading',{name:'Review TaxML 1099-DIV candidate'}).waitFor();
  await page.locator('input[aria-label="1099-DIV payer name"]').fill('Synthetic Brokerage');
  await page.locator('input[aria-label="Confirm qualified dividend eligibility"]').check();
  await page.locator('input[aria-label="Confirm supported 1099-DIV situation"]').check();
  await page.locator('input[aria-label="Confirm all TaxML 1099-DIV amounts and household"]').check();
  await page.getByRole('button',{name:'Add reviewed 1099-DIV',exact:true}).click();
  const divCount=await page.evaluate(()=>data.dividends.length);if(divCount<1){const err=await page.locator('.dialog-error').textContent();throw new Error('1099-DIV review did not add: '+err);}
  await reopenDecodedSource(page);
}
async function saveAndReopen(page,launchContext,context,server,offline,returnId,scratch){
  await page.getByRole('button',{name:'Close',exact:true}).click();
  await page.evaluate(()=>navigate('w2'));
  await page.locator('#tax-w2-0-wages').fill('60000.00');
  await page.locator('#tax-w2-0-federal_withholding').fill('5000.00');
  const before=await page.evaluate(async()=>{const next=await calculate();return {total_tax:next.summary.total_tax,amount_owed:next.summary.amount_owed,refund:next.summary.refund};});
  assert.ok(Number(before.total_tax)>0,'synthetic imported income did not produce positive tax');
  await page.evaluate(async()=>{await saveReturn();});
  await page.locator('#save-button:not([disabled])').waitFor();
  await context.close();
  const fresh=await launchContext();
  const freshPage=await fresh.newPage();freshPage.setDefaultTimeout(120000);await freshPage.goto(`http://127.0.0.1:${server.port}/${offline?'?offline=1':''}`);await freshPage.locator('#save-button:not([disabled])').waitFor();
  const reopenedId=await freshPage.evaluate(()=>currentId);const reopenedState=await freshPage.evaluate(async()=>{if(!result?.summary)await calculate();return {data:{w2:data.w2.length,interest:data.interest.length,dividends:data.dividends.length},references:[...(metadata.w2_records||[]),...(metadata.income_document_records?.interest||[]),...(metadata.income_document_records?.dividends||[])].map(item=>item.source_document?.document_id||item.source_document?.id||null),summary:{total_tax:result?.summary?.total_tax,amount_owed:result?.summary?.amount_owed,refund:result?.summary?.refund}}});const reopenedDocs=await freshPage.evaluate(async id=>{const digest=async file=>{if(typeof file?.arrayBuffer==='function')return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer())),byte=>byte.toString(16).padStart(2,'0')).join('');throw Error('persisted document is not a Blob/File: '+Object.prototype.toString.call(file)+' keys='+Object.keys(file||{}));};const rows=await documentsForReturn(id);return Promise.all(rows.map(async row=>({id:row.id,name:row.name,encrypted:Boolean(row.default_encrypted),container:row.binding_files?.container||null,sha256:await digest(row.file),encrypted_source_sha256:row.default_encrypted?.encrypted_source_sha256||null})));},reopenedId);const reopened={id:reopenedId,...reopenedState,docs:reopenedDocs};
  assert.equal(reopened.id,returnId);assert.deepEqual(reopened.data,{w2:1,interest:2,dividends:1});assert.equal(reopened.docs.length,2);assert.ok(reopened.docs.some(row=>row.encrypted));assert.ok(reopened.docs.some(row=>row.name==='main.entity'&&row.container==='binary_entity'&&row.sha256===sourceHash));assert.ok(reopened.docs.some(row=>row.name==='synthetic-default-binary-array.tax'&&row.encrypted_source_sha256));assert.ok(reopened.references.every(Boolean));const decodedId=reopened.docs.find(row=>row.name==='main.entity').id;assert.ok(reopened.references.every(reference=>reference===decodedId));assert.equal(reopened.summary.total_tax,5225);assert.equal(reopened.summary.amount_owed,4);
  await fresh.close();return {before,reopened};
}
(async()=>{
  const checks=[];
  for(const offline of [false,true]){
    const scratch=fs.mkdtempSync(path.join(os.tmpdir(),'tax-default-import-'));const server=await startServer(scratch);const profileDir=fs.mkdtempSync(path.join(os.tmpdir(),'tax-default-import-profile-'));const launchContext=()=>chromium.launchPersistentContext(profileDir,{headless:true,acceptDownloads:true,...(process.env.TAX_REBORN_BROWSER?{executablePath:process.env.TAX_REBORN_BROWSER}:{})});let context=await launchContext();const page=await context.newPage();page.setDefaultTimeout(120000);
    try{await page.goto(`http://127.0.0.1:${server.port}/${offline?'?offline=1':''}`);const id=await openReturn(page);const inventory=await inspectInventory(page,id,'synthetic-default-binary-array.tax');const negatives=await runNegativeChecks(page,id);const results=await inspectBinaryEntity(page);const persisted=await page.evaluate(async returnId=>{const digest=async file=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer())),byte=>byte.toString(16).padStart(2,'0')).join('');const rows=await documentsForReturn(returnId);return Promise.all(rows.map(async row=>({id:row.id,name:row.name,container:row.binding_files?.container||null,sha256:await digest(row.file),default_encrypted:row.default_encrypted||null})));},id);assert.ok(persisted.some(row=>row.name==='main.entity'&&row.container==='binary_entity'&&row.sha256===sourceHash));assert.ok(persisted.some(row=>row.name==='synthetic-default-binary-array.tax'&&row.default_encrypted?.encrypted_source_sha256));await reviewCandidates(page);const preSave=await page.evaluate(()=>({w2:data.w2.length,interest:data.interest.length,dividends:data.dividends.length}));const saved=await saveAndReopen(page,launchContext,context,server,offline,id,scratch);context=null;checks.push({mode:offline?'Pyodide-IndexedDB':'HTTP-SQLite',all_passed:true,inventory_members:inventory.inventory.length,entity_members:inventory.entityCount,negative_checks:negatives,persisted_documents:saved.reopened.docs.length,source_reader_visible:true,reader_structure:results.structure,candidate_buttons:results.candidateButtons,tax_before_reopen:saved.before,reopened:saved.reopened});}
    finally{if(context)await context.close();server.child.kill('SIGTERM');}
  }
  console.log(JSON.stringify({all_passed:true,fixture_scope:'owned synthetic encrypted archive around public binary-tax fixture; no vendor material',checks},null,2));
})().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
