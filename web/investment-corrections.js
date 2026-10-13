'use strict';
(function(){
 const id=value=>typeof value==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value);
 const hash=value=>typeof value==='string'&&/^[0-9a-f]{64}$/.test(value);
 const money=['proceeds','cost_basis','adjustment','wash_sale_disallowed'];
 let defaults={description:'',term:'long',proceeds:'0',cost_basis:'0',adjustment:'0',special_rate:false,wash_sale_disallowed:'0',wash_sale_confirmed:false,adjustment_code:''};
 const copy=value=>JSON.parse(JSON.stringify(value));
 const sorted=value=>Array.isArray(value)?value.map(sorted):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,sorted(value[key])])):value;
 function amount(value){
  const text=String(value).trim()||'0';
  if(text.length>64||!/^-?\d+(?:\.\d{1,2})?$/.test(text))throw Error('Investment amounts require USD decimals with at most two places');
  const negative=text.startsWith('-'),[whole,part='']=text.replace(/^-/,'').split('.'),cents=BigInt(whole)*100n+BigInt(part.padEnd(2,'0'));
  return(negative&&cents!==0n?'-':'')+String(cents/100n)+'.'+String(cents%100n).padStart(2,'0');
 }
 function canonical(row){
  if(!row||typeof row!=='object'||Array.isArray(row))throw Error('Expected an investment-sale record');
  const value={...defaults,...row};for(const name of money)value[name]=amount(value[name]);
  return JSON.stringify(sorted(value));
 }
 async function fingerprint(row){const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(row)));return[...new Uint8Array(digest)].map(byte=>byte.toString(16).padStart(2,'0')).join('');}
 function newRecord(){return{record_id:crypto.randomUUID(),row_fingerprint:null,basis_corrections:[]};}
 async function normalize(rows,provided=null,previous=null,options={}){
  if(!Array.isArray(rows)||rows.length>1000)throw Error('Invalid investment-sale preparation collection');
  const fingerprints=await Promise.all(rows.map(async row=>{try{return await fingerprint(row);}catch(error){if(options.draft)return null;throw error;}}));
  const entries=provided==null?fingerprints.map(current=>{const matches=(previous||[]).filter(item=>item.row_fingerprint===current);return current&&matches.length===1&&fingerprints.filter(value=>value===current).length===1?matches[0]:{};}):provided;
  if(!Array.isArray(entries)||entries.length!==rows.length)throw Error('Investment preparation records must match their sale collection');
  const recordIds=new Set(),correctionIds=new Set();
  return entries.map((entry,index)=>{
   if(!entry||typeof entry!=='object'||Array.isArray(entry)||Object.keys(entry).some(key=>!['record_id','row_fingerprint','basis_corrections'].includes(key)))throw Error('Invalid investment preparation record');
   const ident=entry.record_id||crypto.randomUUID();if(!id(ident)||recordIds.has(ident))throw Error('Investment record identifiers must be unique UUIDv4 values');recordIds.add(ident);
   const history=entry.basis_corrections||[];if(!Array.isArray(history)||history.length>100)throw Error('Invalid basis-correction history');
   const corrections=history.map(item=>{
    const keys=['correction_id','previous_fingerprint','result_fingerprint','old_cost_basis','new_cost_basis','applied_at','reason'];
    if(!item||typeof item!=='object'||Array.isArray(item)||Object.keys(item).length!==keys.length||Object.keys(item).some(key=>!keys.includes(key))||!id(item.correction_id)||correctionIds.has(item.correction_id))throw Error('Invalid or duplicate basis-correction identifier');
    correctionIds.add(item.correction_id);
    if(!hash(item.previous_fingerprint)||!hash(item.result_fingerprint)||typeof item.applied_at!=='string'||item.applied_at.length>40||!/(?:Z|[+-]\d\d:\d\d)$/.test(item.applied_at)||!Number.isFinite(Date.parse(item.applied_at)))throw Error('Basis correction requires before/after fingerprints and a valid time');
    if(typeof item.reason!=='string'||item.reason.length>500||/[\u0000-\u001f\u007f]/.test(item.reason))throw Error('Invalid basis-correction source note');
    const before=amount(item.old_cost_basis),after=amount(item.new_cost_basis);if(after.startsWith('-'))throw Error('Corrected cost basis cannot be negative');
    return{...item,old_cost_basis:before,new_cost_basis:after};
   });
   return{record_id:ident,row_fingerprint:fingerprints[index],basis_corrections:corrections};
  });
 }
 async function plan(row,recordId,newBasis,reason=''){
  if(!id(recordId))throw Error('Choose one valid investment-sale record');
  const next=amount(newBasis);if(next.startsWith('-'))throw Error('Corrected cost basis cannot be negative');
  if(typeof reason!=='string'||reason.length>500||/[\u0000-\u001f\u007f]/.test(reason))throw Error('Use a single-line source note of at most 500 characters');
  return{record_id:recordId,correction_id:crypto.randomUUID(),previous_fingerprint:await fingerprint(row),new_cost_basis:next,reason};
 }
 async function apply(data,metadata,proposal){
  if(!id(proposal?.record_id)||!id(proposal?.correction_id)||!hash(proposal.previous_fingerprint))throw Error('Invalid basis-correction proposal');
  const newBasis=amount(proposal.new_cost_basis);if(newBasis.startsWith('-'))throw Error('Corrected cost basis cannot be negative');
  if(typeof proposal.reason!=='string'||proposal.reason.length>500||/[\u0000-\u001f\u007f]/.test(proposal.reason))throw Error('Invalid basis-correction source note');
  const next=copy(data),prepared=copy(metadata),records=await normalize(next.capital_gains||[],prepared.investment_records);
  const index=records.findIndex(item=>item.record_id===proposal.record_id);if(index<0)throw Error('The selected investment sale no longer exists');
  const record=records[index],current=await fingerprint(next.capital_gains[index]);
  const existing=records.flatMap(item=>item.basis_corrections.map(change=>({record_id:item.record_id,...change}))).find(item=>item.correction_id===proposal.correction_id);
  if(existing){
   if(existing.record_id!==proposal.record_id||existing.new_cost_basis!==newBasis||existing.previous_fingerprint!==proposal.previous_fingerprint||existing.reason!==proposal.reason)throw Error('This correction identifier is already used for different source values');
   if(current!==existing.result_fingerprint)throw Error('This sale changed after its correction; review its current values before making another correction');
   prepared.investment_records=records;return{data:next,metadata:prepared,already_applied:true};
  }
  if(current!==proposal.previous_fingerprint)throw Error('This investment sale changed during review; reopen the correction and check its current source');
  if(record.basis_corrections.length>=100)throw Error('This record already has 100 corrections; export its history before starting a new record');
  const oldBasis=amount(next.capital_gains[index].cost_basis??'0');
  // Absolute overwrite. Never add a correction amount repeatedly to basis.
  next.capital_gains[index].cost_basis=newBasis;
  const after=await fingerprint(next.capital_gains[index]);record.row_fingerprint=after;
  record.basis_corrections.push({correction_id:proposal.correction_id,previous_fingerprint:current,result_fingerprint:after,old_cost_basis:oldBasis,new_cost_basis:newBasis,applied_at:new Date().toISOString(),reason:proposal.reason});
  prepared.investment_records=records;return{data:next,metadata:prepared,already_applied:false};
 }
 window.taxInvestmentCorrections={setDefaults:value=>{defaults={...value};},newRecord,amount,canonical,fingerprint,normalize,plan,apply};
})();
