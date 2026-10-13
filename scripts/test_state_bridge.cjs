// Adapter tests: pinned tax year, literal IL arithmetic, schema rejection, proof exports.
// The 196 upstream state-composer tests are a separate dependency validation result.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');let output;const context=vm.createContext({self:{postMessage:x=>output=x},TextEncoder,TextDecoder,structuredClone});vm.runInContext(fs.readFileSync(path.join(root,'web/state-worker.js'),'utf8'),context);
function call(input,command='calculate'){context.self.onmessage({data:{id:1,command,input}});if(output.error)throw Error(output.error);return output.result;}
const checks=[];function test(name,f){f();checks.push(name);}
test('31-state schema and all input descriptors available',()=>{const fields=call(undefined,'schema');assert.equal(fields.find(f=>f.key==='jurisdiction').options.length,31);assert.ok(fields.length>1000);});
let r;test('Literal 2025 Illinois 4.95% tax after $2,850 exemption',()=>{r=call({jurisdiction:'il',filingStatus:'single',federalAGI:60100,exemptions:1,dependents:0,stateWithholding:3000});assert.equal(r.lines['12_tax'],'$2,834');assert.equal(r.lines['38_refund'],'$166');});
test('Rule evaluation is fixed to 2025 and includes derivation evidence',()=>{assert.equal(r.as_of,'2025-12-31');assert.equal(r.evaluations[0].proof.asOf,'2025-12-31');assert.equal(r.filing_packet_ready,false);assert.ok(JSON.stringify(r).includes('citation'));});
test('Unknown jurisdiction rejected instead of falling back to New York',()=>assert.throws(()=>call({jurisdiction:'dc',filingStatus:'single',federalAGI:60100})));
test('Unknown input fields rejected',()=>assert.throws(()=>call({jurisdiction:'il',federalAGI:60100,inventedTaxCredit:9999})));
test('Missing AGI rejected for AGI-based state',()=>assert.throws(()=>call({jurisdiction:'il',filingStatus:'single'})));
test('Nonfinite and unknown status rejected',()=>{assert.throws(()=>call({jurisdiction:'il',federalAGI:NaN}));assert.throws(()=>call({jurisdiction:'il',filingStatus:'invalid',federalAGI:60000}));});
test('Federal $60000 example also agrees with literal whole-dollar rounding',()=>{const q=call({jurisdiction:'il',filingStatus:'single',federalAGI:60000,exemptions:1,dependents:0,stateWithholding:3000});assert.equal(q.lines['12_tax'],'$2,829');assert.equal(q.lines['38_refund'],'$171');});
const report={all_passed:true,checks,tests:checks.length,scope:'Local state adapter and two literal Illinois cases; not independent all-state validation',source:'https://tax.illinois.gov/content/dam/soi/en/web/tax/forms/incometax/documents/currentyear/individual/il-1040-instr.pdf',tax_year:2025};fs.writeFileSync(path.join(root,'qa/state-bridge-tests.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
