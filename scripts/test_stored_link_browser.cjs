// Real main App, actual Worker, Documents File inputs and read-only downloads.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn,spawnSync}=require('node:child_process'),crypto=require('node:crypto');
const {chromium}=require(process.env.TAX_REBORN_PLAYWRIGHT||'playwright');
const root=path.resolve(__dirname,'..'),out=path.resolve(process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/stored-link-browser')),fixture=path.join(root,'fixtures/binary-tax'),scratch=fs.mkdtempSync(path.join(os.tmpdir(),'tax-stored-link-')),python=process.env.TAX_REBORN_TEST_PYTHON||'python3';
fs.mkdirSync(out,{recursive:true});const child=spawn(python,['-B','-u','-c',`import sys,json;sys.path.insert(0,${JSON.stringify(root)});from http.server import ThreadingHTTPServer;import server;h=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);h.store=server.Store(${JSON.stringify(scratch)});print(json.dumps({'port':h.server_port}),flush=True);h.serve_forever()`],{stdio:['ignore','pipe','pipe']});
let browser,serverErrors='';child.stderr.on('data',b=>{serverErrors+=b;});const checks=[],errors=[];
const snapshot=page=>page.evaluate(()=>({id:currentId,data:clone(data),metadata:clone(metadata),result:clone(result),revision,calculatedRevision}));
(async()=>{
 const ready=await new Promise((resolve,reject)=>{let text='';child.stdout.on('data',b=>{text+=b;try{resolve(JSON.parse(text.split('\n')[0]));}catch{}});child.on('exit',code=>reject(Error('API exited '+code+' '+serverErrors)));});
 const origin='http://127.0.0.1:'+ready.port;browser=await chromium.launch({headless:true,executablePath:process.env.TAX_REBORN_BROWSER||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 for(const offline of[false,true]){
  const mode=offline?'Pyodide-IndexedDB':'HTTP-SQLite',context=await browser.newContext({acceptDownloads:true,viewport:{width:offline?390:1280,height:900}});
  await context.route('**/*',r=>{const u=new URL(r.request().url());return u.origin===origin||['blob:','data:'].includes(u.protocol)?r.continue():r.abort();});
  const page=await context.newPage();page.setDefaultTimeout(120000);page.on('pageerror',e=>errors.push(e.message));let downloads=0;page.on('download',()=>downloads++);
  await page.goto(origin+(offline?'/?offline=1':''));await page.waitForFunction(()=>!document.querySelector('#save-button').disabled);
  await page.evaluate(async()=>{newReturn();data.name='Independent saved-link read-only test';await calculate();await saveReturn();await loadReturn(currentId);const original=showTaxMLCandidates;showTaxMLCandidates=function(row,view,...args){window.__linkSource=row;window.__linkView=view;return original(row,view,...args);};});
  const before=await snapshot(page),stored=await page.evaluate(()=>api('/api/returns/'+currentId));
  await page.evaluate(()=>showTaxMLImport());await page.getByLabel('Choose plaintext TaxML or .tax container',{exact:true}).setInputFiles(path.join(fixture,'owned-existing-link.taxbin'));await page.getByLabel('Choose explicit TaxML wire profile',{exact:true}).setInputFiles(path.join(fixture,'owned-existing-link-profile.json'));await page.getByLabel('Choose caller-owned XPRF registries',{exact:true}).setInputFiles(path.join(fixture,'owned-existing-link-registry.xprf'));
  await page.getByLabel('TaxML container declaration',{exact:true}).selectOption('binary_entity');await page.getByLabel('Acknowledge the selected unverified wire profile',{exact:true}).check();await page.getByRole('button',{name:'Inspect locally',exact:true}).click();await page.getByRole('button',{name:'Check stored links',exact:true}).waitFor();const documentId=await page.evaluate(()=>__linkSource.id);
  const originalDownload=page.waitForEvent('download');await page.getByRole('button',{name:'Download original source',exact:true}).click();const source=await originalDownload,sourcePath=path.join(out,mode+'-original-source.taxbin');await source.saveAs(sourcePath);assert.deepEqual(fs.readFileSync(sourcePath),fs.readFileSync(path.join(fixture,'owned-existing-link.taxbin')));
  await page.getByRole('button',{name:'Check stored links',exact:true}).click();assert((await page.locator('.dialog').innerText()).includes('does not grant editing permission'));
  await page.getByRole('button',{name:'Run link check',exact:true}).click();await page.getByText('1 saved link(s) checked · 1 consistent within this source.',{exact:true}).waitFor();
  const wait=page.waitForEvent('download');await page.getByRole('button',{name:'Download read-only check',exact:true}).click();const dl=await wait,audit=path.join(out,mode+'-stored-link-audit.json');await dl.saveAs(audit);
  const verified=spawnSync(python,['-B',path.join(root,'scripts/verify_stored_link_audit.py'),audit],{cwd:root,encoding:'utf8'});assert.equal(verified.status,0,verified.stdout+'\n'+verified.stderr);const readback=JSON.parse(verified.stdout);
  assert.deepEqual(await snapshot(page),before);assert.deepEqual(await page.evaluate(()=>api('/api/returns/'+currentId)),stored);await page.evaluate(()=>closeDialog());
  const held=[];
  for(const action of['input','return','source','profile','carrier','request','changed','close']){
   await page.evaluate(()=>{showStoredLinkDiagnostics(__linkSource,__linkView,currentId,revision);window.__linkEngine=taxLocalEngine;window.__heldLink=null;window.taxLocalEngine=async(command,payload)=>{const result=await __linkEngine(command,payload);if(command==='source_link_diagnostics')return new Promise(resolve=>{window.__heldLink=()=>resolve(result);});return result;};});
   await page.getByRole('button',{name:'Run link check',exact:true}).click();await page.waitForFunction(()=>typeof __heldLink==='function');const count=downloads;
   await page.evaluate(action=>{
    if(action==='input'){window.__keptLinkName=data.name;data.name='Changed without revision';}
    else if(action==='return'){window.__keptLinkId=currentId;currentId=crypto.randomUUID();}
    else if(action==='source'){window.__keptLinkFile=__linkSource.file;__linkSource.file=new File(['other source'],'other.taxbin');}
    else if(action==='profile'){window.__keptLinkProfile=__linkSource.binding_files.profile;__linkSource.binding_files.profile=new File(['{}'],'other.json');}
    else if(action==='carrier'){window.__keptLinkCarrier=__linkSource.binding_files.carriers[0];__linkSource.binding_files.carriers[0]=new File(['other bytes'],'other.xprf');}
    else if(action==='request'){window.__keptLinkRequest=taxMLImport.sourceRequest;taxMLImport.sourceRequest=view=>{const r=__keptLinkRequest(view);r.base64='different complete request';return r;};}
    else if(action==='changed'){window.__keptLinkLifecycle={revision,calculatedRevision,dirty};changed();}
    else closeDialog();
   },action);
   await page.evaluate(()=>{__heldLink();window.taxLocalEngine=__linkEngine;});await page.waitForTimeout(250);assert.equal(downloads,count);if(action!=='close')assert(!(await page.locator('.dialog').innerText()).includes('Saved relationship consistent'));
   await page.evaluate(async action=>{
    if(action==='input')data.name=__keptLinkName;
    else if(action==='return')currentId=__keptLinkId;
    else if(action==='source')__linkSource.file=__keptLinkFile;
    else if(action==='profile')__linkSource.binding_files.profile=__keptLinkProfile;
    else if(action==='carrier')__linkSource.binding_files.carriers[0]=__keptLinkCarrier;
    else if(action==='request')taxMLImport.sourceRequest=__keptLinkRequest;
    else if(action==='changed'){revision=__keptLinkLifecycle.revision;calculatedRevision=__keptLinkLifecycle.calculatedRevision;dirty=__keptLinkLifecycle.dirty;await checkpointWorkspace();}
    closeDialog();
   },action);held.push(action);
  }
  // A shown result cannot be downloaded after its source binding changes.
  await page.evaluate(()=>showStoredLinkDiagnostics(__linkSource,__linkView,currentId,revision));await page.getByRole('button',{name:'Run link check',exact:true}).click();await page.getByText('1 saved link(s) checked · 1 consistent within this source.',{exact:true}).waitFor();const shownCount=downloads;
  await page.evaluate(()=>{window.__keptLinkFile=__linkSource.file;__linkSource.file=new File(['changed'],'changed.taxbin');});await page.getByRole('button',{name:'Download read-only check',exact:true}).click();await page.locator('.dialog-error').filter({hasText:'fresh check'}).waitFor();assert.equal(downloads,shownCount);await page.evaluate(()=>{__linkSource.file=__keptLinkFile;closeDialog();});
  await page.evaluate(()=>showStoredLinkDiagnostics(__linkSource,__linkView,currentId,revision));await page.getByRole('button',{name:'Run link check',exact:true}).click();await page.getByText('1 saved link(s) checked · 1 consistent within this source.',{exact:true}).waitFor();await page.evaluate(()=>{window.__linkDownload=downloadBlob;downloadBlob=async()=>false;});const cancelled=downloads;await page.getByRole('button',{name:'Download read-only check',exact:true}).click();await page.waitForTimeout(200);assert.equal(downloads,cancelled);await page.evaluate(()=>{downloadBlob=__linkDownload;closeDialog();});
  assert.deepEqual(await snapshot(page),before);assert.deepEqual(await page.evaluate(()=>api('/api/returns/'+currentId)),stored);
  await page.reload();await page.waitForFunction(()=>!document.querySelector('#save-button').disabled);await page.waitForFunction(()=>result&&calculatedRevision===revision&&!calculationError);const after=await snapshot(page);assert.deepEqual(after.data,before.data);assert.deepEqual(after.metadata,before.metadata);assert.deepEqual(after.result,before.result);assert.deepEqual(await page.evaluate(()=>api('/api/returns/'+currentId)),stored);
  await page.evaluate(async id=>{await showLocalSource({return_id:currentId,document_id:id});},documentId);await page.getByRole('button',{name:'Inspect / correct source',exact:true}).click();await page.getByRole('button',{name:'Check stored links',exact:true}).waitFor();await page.getByRole('button',{name:'Check stored links',exact:true}).click();await page.getByRole('button',{name:'Run link check',exact:true}).click();await page.getByText('1 saved link(s) checked · 1 consistent within this source.',{exact:true}).waitFor();
  const reopenWait=page.waitForEvent('download');await page.getByRole('button',{name:'Download read-only check',exact:true}).click();const reopened=await reopenWait,reopenedPath=path.join(out,mode+'-reopened-link-audit.json');await reopened.saveAs(reopenedPath);const reopenCheck=spawnSync(python,['-B',path.join(root,'scripts/verify_stored_link_audit.py'),reopenedPath],{cwd:root,encoding:'utf8'});assert.equal(reopenCheck.status,0,reopenCheck.stdout+'\n'+reopenCheck.stderr);await page.evaluate(()=>closeDialog());assert.deepEqual((await snapshot(page)).data,before.data);assert.deepEqual(await page.evaluate(()=>api('/api/returns/'+currentId)),stored);
  checks.push({mode,actual_File_inputs:true,actual_main_App_and_General_Worker:true,complete_original_source_713_bytes_exact:true,audit_readback:readback,late_result_refusals:held,already_shown_source_change_blocks_download:true,cancel_simulated_without_download:true,shared_worker_remains_usable:true,full_current_input_metadata_result_saved_return_reload_unchanged:true,source_attachment_profile_carriers_reopened_after_reload:true,reopened_audit_readback:JSON.parse(reopenCheck.stdout),writeback_allowed:false,native_inventory_verified:false});
  console.log('PASS',mode);await context.close();
 }
 assert.deepEqual(errors,[]);const receipt={at_utc:new Date().toISOString(),all_passed:true,checks,original_resources_used:false,foreground_windows:0};fs.writeFileSync(path.join(out,'stored-link-browser-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();child.kill('SIGTERM');fs.rmSync(scratch,{recursive:true,force:true});});
