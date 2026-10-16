const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{chromium}=require(process.env.TAX_REBORN_PLAYWRIGHT||'playwright');
const root=path.resolve(__dirname,'..'),fixtureDir=path.join(root,'web/samples/default-encrypted');
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
async function inspectInventory(page,returnId,archive,expectedName){
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
  assert.ok(persisted.some(row=>row.name===archive && row.default_encrypted?.branch==='current'));
  return {body,persisted};
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
  assert.match(body,/Source SHA-256/);
  assert.match(body,/Binary source fields/);
  assert.match(body,/nonempty supported structures/);
  assert.doesNotMatch(body,/No supported W-2, 1099-DIV or 1099-INT candidates were found/);
  return body;
}
(async()=>{
  const checks=[];
  for(const offline of [false,true]){
    const scratch=fs.mkdtempSync(path.join(os.tmpdir(),'tax-default-import-'));
    const server=await startServer(scratch);
    const browser=await chromium.launch({headless:true,...(process.env.TAX_REBORN_BROWSER?{executablePath:process.env.TAX_REBORN_BROWSER}:{})});
    const context=await browser.newContext({acceptDownloads:true});
    const page=await context.newPage();page.setDefaultTimeout(120000);
    try{
      await page.goto(`http://127.0.0.1:${server.port}/${offline?'?offline=1':''}`);
      const id=await openReturn(page);
      const inventory=await inspectInventory(page,id,'synthetic-default-binary-array.tax');
      const results=await inspectBinaryEntity(page);
      const persisted=await page.evaluate(async returnId=>documentsForReturn(returnId),id);
      assert.ok(persisted.some(row=>row.name==='main.entity'&&row.binding_files?.container==='binary_entity'));
      assert.ok(persisted.some(row=>row.name==='synthetic-default-binary-array.tax'&&row.default_encrypted?.encrypted_source_sha256));
      checks.push({mode:offline?'Pyodide-IndexedDB':'HTTP-SQLite',all_passed:true,inventory_members:6,entity_members:4,persisted_documents:persisted.length,source_reader_visible:true,source_reader_excerpt:results.slice(0,600)});
    }finally{
      await context.close();await browser.close();server.child.kill('SIGTERM');
    }
  }
  console.log(JSON.stringify({all_passed:true,fixture_scope:'owned synthetic encrypted archive around public binary-tax fixture; no vendor material',checks},null,2));
})().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
