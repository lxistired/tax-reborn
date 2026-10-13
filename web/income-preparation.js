'use strict';
// Independently authored local INT/DIV preparation contract. No vendor code or tax rules.
(function () {
 const templates={interest:{payer:'',taxable:'0',tax_exempt:'0',federal_withholding:'0'},dividends:{payer:'',ordinary:'0',qualified:'0',capital_gain_distributions:'0',federal_withholding:'0'}};
 const entryKeys=['record_id','row_fingerprint','reviewed','reviewed_fingerprint','reviewed_at','is_placeholder','unresolved_fields'];
 const copy=value=>JSON.parse(JSON.stringify(value));
 const sorted=value=>Array.isArray(value)?value.map(sorted):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,sorted(value[key])])):value;
 const packed=value=>JSON.stringify(sorted(value));
 const object=value=>value&&typeof value==='object'&&!Array.isArray(value);
 const validId=value=>typeof value==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value);
 const ident=value=>{if(!validId(value))throw Error('Expected a UUIDv4 local record identifier');return value;};
 async function hash(value){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(packed(value)));return[...new Uint8Array(bytes)].map(b=>b.toString(16).padStart(2,'0')).join('');}
 function amount(value){
  const text=String(value).trim();if(typeof value==='boolean'||text.length>64||! /^-?\d+(?:\.\d{1,2})?$/.test(text))throw Error('Expected an explicit USD amount with at most two decimal places');
  const negative=text.startsWith('-'),[whole,part='']=text.replace(/^-/,'').split('.'),cents=BigInt(whole)*100n+BigInt(part.padEnd(2,'0'));
  if(cents>99999999999999n)throw Error('USD amount exceeds preparation limit');
  return(negative&&cents?'-':'')+String(cents/100n)+'.'+String(cents%100n).padStart(2,'0');
 }
 function canonicalObject(type,row){
  if(!Object.hasOwn(templates,type)||!object(row)||Object.keys(row).some(k=>!(k in templates[type])))throw Error('Unsupported INT/DIV row or field');
  const value={...templates[type],...row};if(typeof value.payer!=='string'||value.payer.length>256)throw Error('Invalid payer label');
  for(const key of Object.keys(templates[type]).filter(k=>k!=='payer'))value[key]=amount(value[key]);return value;
 }
 const canonical=(type,row)=>packed(canonicalObject(type,row));
 const fingerprint=(type,row)=>hash(canonicalObject(type,row));
 const newRecord=(options={})=>({record_id:crypto.randomUUID(),row_fingerprint:null,reviewed:false,reviewed_fingerprint:null,reviewed_at:null,is_placeholder:options.is_placeholder??false,unresolved_fields:copy(options.unresolved_fields||[])});
 async function entry(type,row,item={},options={}){
  if(!object(item)||Object.keys(item).some(k=>!entryKeys.includes(k)))throw Error('Unsupported preparation metadata field');
  let current;try{current=await fingerprint(type,row);}catch(error){if(!options.draft)throw error;current=null;}
  const id=ident(item.record_id||crypto.randomUUID());
  const unresolved=item.unresolved_fields??[];
  if(!Array.isArray(unresolved)||unresolved.length!==new Set(unresolved).size||unresolved.some(k=>typeof k!=='string'||!([...Object.keys(templates[type]),'current_year_confirmation'].includes(k))))throw Error('Invalid unresolved-field collection');
  const placeholder=item.is_placeholder??false;if(typeof placeholder!=='boolean'||typeof(item.reviewed??false)!=='boolean')throw Error('Preparation flags must be Boolean');
  if(item.reviewed&&(!/^[0-9a-f]{64}$/.test(item.reviewed_fingerprint||'')||typeof item.reviewed_at!=='string'||item.reviewed_at.length>40||!/(?:Z|[+-]\d\d:\d\d)$/.test(item.reviewed_at)||!Number.isFinite(Date.parse(item.reviewed_at))))throw Error('Reviewed record requires its checked values and valid timestamp');
  const reviewed=!!item.reviewed&&current!=null&&item.reviewed_fingerprint===current&&(item.row_fingerprint==null||item.row_fingerprint===current);
  return{record_id:id,row_fingerprint:current,reviewed,reviewed_fingerprint:reviewed?current:null,reviewed_at:reviewed?item.reviewed_at:null,is_placeholder:placeholder,unresolved_fields:[...unresolved].sort()};
 }
 async function normalize(rowsByType,provided=null,previous=null,options={}){
  if(!object(rowsByType))throw Error('Expected current income rows');for(const value of[provided,previous])if(value!=null&&(!object(value)||Object.keys(value).some(k=>!Object.hasOwn(templates,k))))throw Error('Unsupported income preparation collection');
  const result={},ids=new Set();
  for(const type of Object.keys(templates)){
   const rows=rowsByType[type]||[];if(!Array.isArray(rows)||rows.length>1000)throw Error('Invalid income row collection');
   const hashes=await Promise.all(rows.map(async row=>{try{return await fingerprint(type,row);}catch(error){if(options.draft)return null;throw error;}}));
   const entries=provided?.[type]??hashes.map(current=>{const matches=(previous?.[type]||[]).filter(x=>x.row_fingerprint===current);return current&&matches.length===1&&hashes.filter(x=>x===current).length===1?matches[0]:{};});
   if(!Array.isArray(entries)||entries.length!==rows.length)throw Error('Preparation metadata must match current income rows');
   result[type]=await Promise.all(rows.map((row,index)=>entry(type,row,entries[index],options)));
   for(const item of result[type]){if(ids.has(item.record_id))throw Error('Source-record IDs must be unique across INT/DIV');ids.add(item.record_id);}
  }return result;
 }
 async function validateReceipt(receipt){
  const keys=['collection','removed_record_ids','result_record_ids','archived_replaced_records'];
  if(!object(receipt)||Object.keys(receipt).length!==keys.length||Object.keys(receipt).some(k=>!keys.includes(k))||!Object.hasOwn(templates,receipt.collection))throw Error('Invalid local replacement receipt fields');
  for(const key of['removed_record_ids','result_record_ids']){const values=receipt[key];if(!Array.isArray(values)||!values.length||values.length>1000||values.length!==new Set(values).size)throw Error('Invalid or duplicate receipt ID collection');values.forEach(ident);}
  if(receipt.removed_record_ids.some(id=>receipt.result_record_ids.includes(id)))throw Error('Replacement result and removed IDs must differ');
  const archived=receipt.archived_replaced_records;if(!Array.isArray(archived)||archived.length!==receipt.removed_record_ids.length)throw Error('Receipt requires every removed source row');
  const ids=[];for(const item of archived){if(!object(item)||Object.keys(item).length!==2||!object(item.metadata)||Object.keys(item).some(k=>!['row','metadata'].includes(k)))throw Error('Invalid archived source fields');canonicalObject(receipt.collection,item.row);const normalized=await entry(receipt.collection,item.row,item.metadata);if(packed(normalized)!==packed(item.metadata)||!normalized.is_placeholder)throw Error('Archived placeholder metadata differs from source facts');ids.push(normalized.record_id);}
  if(ids.length!==new Set(ids).size||packed([...ids].sort())!==packed([...receipt.removed_record_ids].sort()))throw Error('Archived source IDs do not match removed targets');return copy(receipt);
 }
 async function normalizeEvents(value=[]){
  if(!Array.isArray(value)||value.length>1000)throw Error('Invalid local import-event history');const ids=new Set();
  const result=[];for(const event of value){if(!object(event)||Object.keys(event).length!==3||Object.keys(event).some(k=>!['event_id','payload_hash','receipt'].includes(k))||!validId(event.event_id)||ids.has(event.event_id)||! /^[0-9a-f]{64}$/.test(event.payload_hash||'')||!object(event.receipt))throw Error('Invalid or duplicate local import-event receipt');ids.add(event.event_id);await validateReceipt(event.receipt);result.push(copy(event));}return result;
 }
 async function prepared(data,metadata){const value=copy(metadata||{});value.income_document_records=await normalize(data,value.income_document_records);value.income_import_events=await normalizeEvents(value.income_import_events);return value;}
 async function markReviewed(data,metadata,type,id,timestamp){
  const result=await prepared(data,metadata),item=result.income_document_records[type]?.find(x=>x.record_id===ident(id));if(!item)throw Error('Selected record no longer exists');
  Object.assign(item,{reviewed:true,reviewed_at:timestamp,reviewed_fingerprint:item.row_fingerprint});result.income_document_records=await normalize(data,result.income_document_records);return result;
 }
 async function summary(data,metadata){
  const value=await prepared(data,metadata),out={reviewed_by_id:{},missing_facts_by_id:{},reviewed:0,total:0};
  for(const entries of Object.values(value.income_document_records))for(const item of entries){const missing=[...item.unresolved_fields];if(item.is_placeholder&&!missing.includes('current_year_confirmation'))missing.push('current_year_confirmation');out.reviewed_by_id[item.record_id]=item.reviewed;out.missing_facts_by_id[item.record_id]=missing;out.reviewed+=Number(item.reviewed);out.total++;}return out;
 }
 async function plan(data,metadata,type,targetIds,replacementRows,eventId=crypto.randomUUID(),successful=true){
  const meta=await prepared(data,metadata);ident(eventId);if(!Object.hasOwn(templates,type)||typeof successful!=='boolean')throw Error('Invalid local import operation');if(!successful)return{status:'not_applied',reason:'Import has not succeeded'};
  if(!Array.isArray(targetIds)||!targetIds.length||targetIds.length!==new Set(targetIds).size)throw Error('Explicit unique replacement target IDs are required');targetIds.forEach(ident);
  if(!Array.isArray(replacementRows)||!replacementRows.length||replacementRows.length>1000)throw Error('Replacement must contain actual imported rows');
  const old=meta.income_import_events.find(x=>x.event_id===eventId),replayBefore=new Map((old?.receipt.archived_replaced_records||[]).map(x=>[x.metadata.record_id,x.metadata.row_fingerprint]));
  const targets=targetIds.map(id=>{if(old){if(!replayBefore.has(id))throw Error('Conflicting import-event targets');return{record_id:id,before_fingerprint:replayBefore.get(id)};}const item=meta.income_document_records[type].find(x=>x.record_id===id);if(!item||!item.is_placeholder)throw Error('Choose an existing explicit import placeholder');return{record_id:id,before_fingerprint:item.row_fingerprint};});
  const rows=replacementRows.map(row=>canonicalObject(type,row)),payload={collection:type,target_ids:[...targetIds].sort(),replacements:rows,before_fingerprints:Object.fromEntries(targets.map(x=>[x.record_id,x.before_fingerprint]))},payloadHash=await hash(payload);
  if(old){if(old.payload_hash!==payloadHash)throw Error('An import-event ID cannot identify different targets or amounts');return{status:'already_applied',event_id:eventId,payload_hash:payloadHash,receipt:copy(old.receipt)};}
  const newRecords=await Promise.all(rows.map(async row=>({row,metadata:await entry(type,row,newRecord())})));
  return{status:'planned',event_id:eventId,payload_hash:payloadHash,payload,targets,new_records:newRecords};
 }
 async function apply(data,metadata,proposal){
  const next=copy(data),meta=await prepared(next,metadata);if(proposal?.status==='not_applied')return{data:next,metadata:meta,already_applied:false,receipt:{status:'not_applied'}};
  ident(proposal?.event_id);if(proposal.status==='planned'&&await hash(proposal.payload)!==proposal.payload_hash)throw Error('Replacement proposal payload changed');const old=meta.income_import_events.find(x=>x.event_id===proposal.event_id);if(old){if(old.payload_hash!==proposal.payload_hash)throw Error('Conflicting import-event replay');return{data:next,metadata:meta,already_applied:true,receipt:{status:'already_applied',...copy(old.receipt)}};}
  if(proposal.status!=='planned'||await hash(proposal.payload)!==proposal.payload_hash)throw Error('Replacement proposal is not intact');
  const type=proposal.payload.collection,entries=meta.income_document_records[type],targets=new Map(proposal.targets.map(x=>[x.record_id,x.before_fingerprint]));
  if(targets.size!==proposal.targets.length||packed([...targets.keys()].sort())!==packed(proposal.payload.target_ids)||packed(Object.fromEntries(targets))!==packed(proposal.payload.before_fingerprints))throw Error('Replacement target identity mismatch');
  const pairs=(next[type]||[]).map((row,i)=>({row,metadata:entries[i]})),archived=[];
  for(const[id,before]of targets){const matches=pairs.filter(x=>x.metadata.record_id===id);if(matches.length!==1||matches[0].metadata.row_fingerprint!==before||!matches[0].metadata.is_placeholder)throw Error('Selected placeholder changed; review a fresh proposal');archived.push(copy(matches[0]));}
  if(packed(proposal.new_records.map(x=>canonicalObject(type,x.row)))!==packed(proposal.payload.replacements))throw Error('Replacement source rows differ from the proposal');
  for(const item of proposal.new_records){const normalized=await entry(type,item.row,item.metadata);if(packed(normalized)!==packed(item.metadata)||normalized.reviewed||normalized.is_placeholder||normalized.unresolved_fields.length)throw Error('New imported records require fresh unchecked metadata');}
  const first=pairs.findIndex(x=>targets.has(x.metadata.record_id)),position=pairs.slice(0,first).filter(x=>!targets.has(x.metadata.record_id)).length,kept=pairs.filter(x=>!targets.has(x.metadata.record_id));kept.splice(position,0,...copy(proposal.new_records));
  next[type]=kept.map(x=>x.row);meta.income_document_records[type]=kept.map(x=>x.metadata);
  const receipt={collection:type,removed_record_ids:[...targets.keys()].sort(),result_record_ids:proposal.new_records.map(x=>x.metadata.record_id),archived_replaced_records:archived};
  meta.income_import_events.push({event_id:proposal.event_id,payload_hash:proposal.payload_hash,receipt});const final=await prepared(next,meta);return{data:next,metadata:final,already_applied:false,receipt:{status:'applied',...copy(receipt)}};
 }
 window.taxIncomePreparation={canonical,fingerprint,newRecord,normalize,normalizeEvents,markReviewed,summary,plan,apply};
})();
