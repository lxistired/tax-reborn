import {evaluate} from './packages/core/dist/index.js';
import {getCorpus} from './packages/corpus-us-federal/dist/index.js';
import {composeStateReturn,makeStateTaxEvaluator,stateReturnShape} from './packages/compose/dist/index.js';
import {z} from 'zod';
const schema=z.object(stateReturnShape).strict();
const corpus=getCorpus();
function fields(){return Object.entries(stateReturnShape).map(([key,s])=>{const description=s.description||'';let optional=false;while(s._def.innerType){optional=true;s=s._def.innerType;}const type=s._def.typeName;return {key,description,optional,type:type==='ZodBoolean'?'boolean':type==='ZodEnum'?'enum':type==='ZodNumber'?'number':type,options:s._def.values||[],integer:s._def.checks?.some(c=>c.kind==='int')||false};});}
function calculate(input){
 const checked=schema.parse(input);const evaluations=[];
 const run=(facts,target)=>{const result=evaluate(corpus,facts,{asOf:'2025-12-31',target});if(result.value.type!=='money')throw Error('Expected a money result from '+target);evaluations.push({target,value:result.value,proof:result.proof});return BigInt(result.value.cents??result.value.value);};
 const result=composeStateReturn(checked,makeStateTaxEvaluator(run,checked));
 return JSON.parse(JSON.stringify({...result,evaluations,tax_year:2025,as_of:'2025-12-31',source:'Invaro OpenTax pinned 72e1fc73ce0454c20c2fa6e8f7b7b41cd292e261',filing_packet_ready:false},(key,value)=>typeof value==='bigint'?value.toString():value));
}
export {calculate,fields};
if(typeof self!=='undefined')self.onmessage=event=>{try{const result=event.data.command==='schema'?fields():calculate(event.data.input);self.postMessage({id:event.data.id,result});}catch(error){self.postMessage({id:event.data.id,error:String(error.message||error)});}};
