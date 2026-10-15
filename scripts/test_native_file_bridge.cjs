// Verify the actual shipped bridge preserves bytes and device result states.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..');
const code=fs.readFileSync(path.join(root,'web/native-file-bridge.js'),'utf8');
function environment(window,search='',fetcher=async()=>{throw Error('No local transport');}){const ctx={window,Blob,File,Uint8Array,atob,btoa,URLSearchParams,location:{search},fetch:fetcher,document:{addEventListener(){}}};vm.createContext(ctx);vm.runInContext(code,ctx);return ctx;}
async function main(){
 const original=Uint8Array.from([0,255,13,10,0,71,128]);let called;
 let reply={saved:true,cancelled:false,bytes:original.length};
 const desktop=environment({},'?desktop=1',async(url,options)=>{assert.equal(url,'/api/native-save');assert.equal(options.method,'POST');const request=JSON.parse(options.body);called=[request.filename,request.mime,request.base64];return{ok:true,json:async()=>reply};});
 const saved=await desktop.window.taxNativeSaveFile(new Blob([original],{type:'application/octet-stream'}),'owned.taxbin');
 assert(saved.saved);assert.equal(called[0],'owned.taxbin');assert.equal(called[1],'application/octet-stream');assert.deepEqual(Buffer.from(called[2],'base64'),Buffer.from(original));
 reply={saved:false,cancelled:true};
 const cancelled=await desktop.window.taxNativeSaveFile(new Blob(['source']),'cancelled.taxbin');assert(cancelled.cancelled);assert.equal(cancelled.saved,false);
 const android=environment({TaxRebornAndroid:{saveFile(...args){called=args;}}});
 const pending=await android.window.taxNativeSaveFile(new Blob([original]),'android.taxbin');assert(pending.chooserOpened);assert.equal(pending.saved,undefined);assert.deepEqual(Buffer.from(called[2],'base64'),Buffer.from(original));
 const ios=environment({TaxRebornIOS:{saveFile:async()=>({saved:false,cancelled:true})}});
 assert((await ios.window.taxNativeSaveFile(new Blob(['source']),'ios.taxbin')).cancelled);
 await assert.rejects(()=>environment({}).window.taxNativeSaveFile(new Blob(['source']),'file.taxbin'),/unavailable/);
 await assert.rejects(()=>desktop.window.taxNativeSaveFile(new Blob([new Uint8Array(15000001)]),'huge.taxbin'),/too large/);
 console.log(JSON.stringify({actual_shipped_native_bridge:true,byte_exact_desktop_and_Android:true,desktop_and_iOS_cancellation_retained:true,Android_chooser_not_claimed_saved:true,absent_bridge_and_oversized_export_refused:true}));
}main().catch(error=>{console.error(error);process.exitCode=1;});
