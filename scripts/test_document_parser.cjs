// Actual source parser in a VM, with independent bad-photo/text-layout inputs.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),ctx={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(root,'web/document-import.js'),'utf8'),ctx);
const parse=ctx.window.parseTaxDocumentText;
const cases=[
 ['same-line amount','2025 W-2\n2 Federal income tax withheld 6,500.00\n3 Social security wages 60,000.00',95,{federal_withholding:'6500.00',social_security_wages:'60000.00'}],
 ['immediate amount line','2025 W-2\n2 Federal income tax withheld\n6500.00\n3 Social security wages\n60000.00',95,{federal_withholding:'6500.00',social_security_wages:'60000.00'}],
 ['damaged next box label','2025 W-2\n2 Federal income tax withheld\n3 S0cial secur1ty wage5 60000.00',95,{}],
 ['missing current amount followed by bare amount after next label','2025 W-2\n2 Federal income tax withheld\n3 S0cial secur1ty wage5\n60000.00',95,{}],
 ['two amounts remain ambiguous','2025 W-2\n2 Federal income tax withheld 6500.00 60000.00',95,{}],
 ['same-line next box boundary','2025 W-2\n2 Federal income tax withheld 6500.00 3 Social security wages 60000.00',95,{federal_withholding:'6500.00',social_security_wages:'60000.00'}],
 ['low-confidence photo never fills amounts','2025 W-2\n1 Wages tips other compensation 60000.00\n2 Federal income tax withheld 60000.00',35,{}],
 ['readable-PDF path retains values','2025 W-2\n1 Wages tips other compensation 60000.00\n2 Federal income tax withheld 6500.00',100,{wages:'60000.00',federal_withholding:'6500.00'}]
];
for(const [name,text,confidence,expected]of cases){const out=parse(text,confidence);assert.deepEqual(JSON.parse(JSON.stringify(out.candidates)),expected,name);if(confidence<50)assert(out.warnings.some(w=>w.includes('No amount is filled')));else for(const key of Object.keys(expected))assert(out.sources[key]?.includes('compensation')||out.sources[key]?.includes('withheld')||out.sources[key]?.includes('wages'));}
const report={passed:cases.length,all_passed:true,scope:'Conservative amount candidates and source excerpts; not a claim of camera digit accuracy',cases:cases.map(c=>c[0])};
fs.writeFileSync(path.join(root,'qa/document-parser-photo-boundaries.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
