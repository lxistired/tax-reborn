'use strict';
// Execute the actual interview render functions with a small DOM recorder.
// The stdin schema comes from the real host calculation module.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const base=path.resolve(__dirname,'..'),schema=JSON.parse(fs.readFileSync(0,'utf8'));
const source=fs.readFileSync(path.join(base,'web/app.js'),'utf8');
const target='amt.special_distribution_same_basis_confirmed';
const data=structuredClone(schema.default_return);
const at=(object,p)=>p.split('.').reduce((v,k)=>v?.[k],object);
const sandbox={schema,data,console,MONEY_KEYS:new Set(),renderedPaths:new Set(),
  moduleDefinitions:new Map([['amt',{label:'Alternative Minimum Tax',description:'Review AMT facts'}]]),
  normalizedPath:p=>p,rowTemplate:()=>undefined,get:p=>at(data,p),
  set:(p,value)=>{const keys=p.split('.'),last=keys.pop();at(data,keys.join('.'))[last]=value;},
  el:(tag,attrs,...children)=>({tag,attrs:attrs||{},children:children.flat(Infinity).filter(x=>x!=null),classList:{add(){},remove(){}}}),
  title:(...args)=>({tag:'title',attrs:{},children:args}),
  card:(...args)=>({tag:'card',attrs:{},children:args.flat(Infinity)}),
  humanLabel:s=>s,renderPage:()=>{},decimalCents:()=>0,
  openRecords:new Set(),clone:structuredClone,changed:()=>{}};
vm.createContext(sandbox);
const helpers=source.slice(source.indexOf('function schemaValue('),source.indexOf('function mergeDefaults('));
const renderers=source.slice(source.indexOf('function field('),source.indexOf('const recordDefinitions='));
if(!helpers||!renderers||renderers.length>25000)throw Error('Actual renderer boundary changed; update test intentionally');
vm.runInContext(helpers+'\n'+renderers+'\nthis.actual=modulePage("amt");',sandbox);
const found=[];
function visit(item){if(Array.isArray(item)){for(const child of item)visit(child);return;}if(!item||typeof item!=='object')return;if(item.tag==='input'&&item.attrs.name===target)found.push(item);for(const c of item.children||[])visit(c);}
visit(sandbox.actual);
if(found.length!==1)throw Error('The real AMT interview did not render exactly one same-basis control');
const input=found[0];
if(input.attrs.type!=='checkbox'||input.attrs.checked!==false)throw Error('Same-basis control must be a real unchecked checkbox');
input.attrs.onChange({target:{checked:true}});
if(at(data,target)!==true)throw Error('Checkbox did not write the separate boolean field');
console.log(JSON.stringify({actual_AMT_interview_rendered:true,checkbox_count:1,default_unchecked:true,change_writes_boolean:true,path:target}));
