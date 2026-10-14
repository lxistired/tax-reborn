// Exercise the actual browser merge routine on old persisted address records.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
const start=source.indexOf('function legacyForeignAddress('),end=source.indexOf('\nconst knownInputSections',start);
assert(start>=0&&end>start);
const ctx={clone:structuredClone,rowTemplate:()=>null};vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);
const defaults={identity:{foreign_country:''},filing_details:{mailing_address_type:'domestic'}};
for(const [input,want]of[[{identity:{foreign_country:' Canada '},filing_details:{}},'foreign'],[{identity:{foreign_country:''}},'domestic'],[{identity:{foreign_country:'Canada'},filing_details:{mailing_address_type:'domestic'}},'domestic'],[{identity:{foreign_country:''},filing_details:{mailing_address_type:'foreign'}},'foreign']]){
 const before=JSON.stringify(input),actual=ctx.mergeDefaults(input,defaults);assert.equal(actual.filing_details.mailing_address_type,want);assert.equal(JSON.stringify(input),before);assert.equal(ctx.legacyForeignAddress(input),Boolean(input.identity.foreign_country?.trim())&&!Object.hasOwn(input.filing_details||{},'mailing_address_type'));
}
console.log(JSON.stringify({legacy_address_browser_migration_cases:4,passed:4,submitted_input_preserved:true}));
