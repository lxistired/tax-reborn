'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto').webcrypto;
const base=path.resolve(__dirname,'..'),sandbox={window:{},crypto,TextEncoder,console};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(base,'web/income-preparation.js'),'utf8'),sandbox);
(async()=>{
  const api=sandbox.window.taxIncomePreparation,cases=JSON.parse(fs.readFileSync(path.join(base,'fixtures/special_dividend_metadata.json'),'utf8'));
  for(const test of cases){
    if(api.canonical('dividends',test.row)!==test.canonical)throw Error('Host/browser canonical values differ');
    if(await api.fingerprint('dividends',test.row)!==test.fingerprint)throw Error('Host/browser fingerprints differ');
  }
  let rejected=false;try{api.canonical('dividends',{special_distribution_confirmed:'true'});}catch(error){rejected=true;}
  if(!rejected)throw Error('Non-Boolean confirmation accepted');
  console.log(JSON.stringify({cases:cases.length,passed:cases.length,invalid_confirmation_rejected:true,legacy_default_fingerprint_preserved:true}));
})().catch(error=>{console.error(error);process.exitCode=1;});
