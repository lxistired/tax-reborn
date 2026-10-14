// Real local API/SQLite and actual browser Pyodide/IndexedDB import acceptance.
// Every TaxML input is independently authored synthetic data; no vendor fixture.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),scratch=fs.mkdtempSync(path.join(os.tmpdir(),'tax-document-dedup-'));
const out=path.join(root,'qa/document-import-guard-20261015');fs.mkdirSync(out,{recursive:true});
const child=spawn('python3',['-u','-c',`import sys,json;sys.path.insert(0,${JSON.stringify(root)});from http.server import ThreadingHTTPServer;import server;http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);http.store=server.Store(${JSON.stringify(scratch)});print(json.dumps({'port':http.server_port}),flush=True);http.serve_forever()`],{stdio:['ignore','pipe','pipe']});
let browser;const checks=[],errors=[];
const fixtures=[['w2','W-2','synthetic-modern-windows-request.json'],['interest','1099-INT','synthetic-native-interest-request.json'],['dividends','1099-DIV','synthetic-native-dividend-request.json']];
async function openCandidate(page,request,type,label){
 await page.evaluate(async({request,type})=>{
  const bytes=text=>Uint8Array.from(atob(text),v=>v.charCodeAt(0));
  const file=new File([bytes(request.base64)],'Synthetic-'+type+'.xml',{type:'application/xml'}),profile=new File([JSON.stringify(request.profile)],'Synthetic-profile.json',{type:'application/json'}),registries=request.carriers.map((item,index)=>new File([bytes(item.base64)],'Synthetic-registry-'+index+'.xprf'));
  const inspected=await window.taxMLImport.inspect(file,profile,registries,'plaintext_xml',true);
  const row={id:crypto.randomUUID(),returnId:currentId,file,name:file.name,type:file.type,size:file.size,created:new Date().toISOString()};
  await documentOperation('readwrite',store=>store.put(row));
  showTaxMLCandidates(row,inspected,currentId,revision);
 },{request,type});
 await page.getByRole('button',{name:'Review '+label+' candidate',exact:true}).click();
 if(type==='w2'){
  await page.getByLabel('Employer name',{exact:true}).fill('Synthetic import guard employer');
  await page.getByLabel('Whose W-2 is this?',{exact:true}).selectOption('taxpayer');
  await page.getByLabel('Box 7 · Social Security tips',{exact:true}).fill('0');
  await page.getByLabel('Box 10 · Dependent-care benefits',{exact:true}).fill('0');
  await page.getByLabel('Confirm all TaxML W-2 amounts and ownership').check();
 }else{
  await page.getByLabel(label+' payer name').fill('Synthetic import guard payer');
  await page.getByLabel('Confirm supported '+label+' situation').check();
  if(type==='dividends')await page.getByLabel('Confirm qualified dividend eligibility').check();
  await page.getByLabel('Confirm all TaxML '+label+' amounts and household').check();
 }
}
(async()=>{
 const ready=await new Promise((resolve,reject)=>{let text='';child.stdout.on('data',buffer=>{text+=buffer;try{resolve(JSON.parse(text.split('\n')[0]));}catch{}});child.on('exit',code=>reject(Error('Test API exited '+code)));});
 const origin='http://127.0.0.1:'+ready.port;browser=await chromium.launch({headless:true});
 for(const offline of [false,true]){
  const context=await browser.newContext({viewport:{width:offline?390:1280,height:900}});
  await context.route('**/*',route=>{const url=new URL(route.request().url());return url.origin===origin||['blob:','data:'].includes(url.protocol)?route.continue():route.abort();});
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  await page.goto(origin+(offline?'/?offline=1':''));await page.waitForFunction(()=>!document.querySelector('#save-button').disabled,{timeout:120000});
  for(const [type,label,file] of fixtures){
   const request=JSON.parse(fs.readFileSync(path.join(root,'fixtures/taxml',file),'utf8'));
   await page.evaluate(async type=>{newReturn();data.name='Synthetic '+type+' duplicate guard';await saveReturn();},type);
   await openCandidate(page,request,type,label);
   await page.getByRole('button',{name:'Add reviewed '+label,exact:true}).click();
   await page.waitForFunction(type=>data[type].length===1,type);
   await page.evaluate(async()=>{await calculate();await saveReturn();await loadReturn(currentId);});
   const before=await page.evaluate(type=>({data:clone(data),metadata:clone(metadata),id:currentId,summary:clone(result.summary),count:data[type].length}),type);
   // New attachment ID and fresh inspection simulate re-uploading the same file.
   await openCandidate(page,request,type,label);
   await page.getByRole('button',{name:'Add reviewed '+label,exact:true}).click();
   try{await page.locator('.dialog-error').filter({hasText:'already supplied a '+label}).waitFor();}
   catch(error){console.error('Synthetic duplicate UI diagnostic',JSON.stringify(await page.evaluate(()=>({dialogErrors:[...document.querySelectorAll('.dialog-error')].map(node=>node.textContent),metadata,revision,resultSummary:result?.summary}))));await page.screenshot({path:path.join(out,'failed-'+(offline?'IndexedDB':'SQLite')+'-'+type+'.png'),fullPage:true});throw error;}
   const after=await page.evaluate(type=>({data:clone(data),metadata:clone(metadata),id:currentId,summary:clone(result.summary),count:data[type].length}),type);
   assert.deepEqual(after,before);
   await page.screenshot({path:path.join(out,(offline?'IndexedDB':'SQLite')+'-'+type+'-duplicate-refused.png'),fullPage:true});
   await page.evaluate(async()=>{closeDialog();await saveReturn();});
   await page.reload();await page.waitForFunction(()=>!document.querySelector('#save-button').disabled,{timeout:120000});
   await page.waitForFunction(()=>result&&calculatedRevision===revision&&!calculationError,null,{timeout:120000});
   const reopened=await page.evaluate(type=>({count:data[type].length,id:currentId,summary:clone(result.summary),metadata:clone(metadata)}),type);
   assert.equal(reopened.count,1);assert.equal(reopened.id,before.id);assert.deepEqual(reopened.summary,before.summary);assert.deepEqual(reopened.metadata,before.metadata);
   const name=(offline?'actual browser Pyodide/IndexedDB':'HTTP/SQLite')+' '+label+' re-upload refused; saved record and tax totals retained after reload';checks.push(name);console.log('PASS',name);
  }
  await context.close();
 }
 assert.deepEqual(errors,[]);
 const receipt={checked_at_utc:new Date().toISOString(),all_passed:true,checks,cases:checks.length,actual_Pyodide_inspection:true,actual_HTTP_SQLite_and_IndexedDB_roundtrips:true,synthetic_only:true,original_vendor_runtime:0,physical_phone_acceptance:false};
 fs.writeFileSync(path.join(out,'browser-acceptance.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();child.kill('SIGTERM');fs.rmSync(scratch,{recursive:true,force:true});});
