'use strict';
(function(){
 const requiredMoney=['wages','federal_withholding','social_security_wages','social_security_withholding','medicare_wages','medicare_withholding','social_security_tips','dependent_care_benefits'];
 const interestMoney=['interest_income','treasury_interest','tax_exempt_interest','federal_withholding'];
 const sourceContexts=new WeakMap();
 const hash=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
 function encoded(bytes){let text='';for(let i=0;i<bytes.length;i+=16384)text+=String.fromCharCode(...bytes.subarray(i,i+16384));return btoa(text);}
 async function inspect(file,profileFile,registryFiles,container,acknowledged){
  if(!(file instanceof Blob)||!file.size||file.size>10*1024*1024)throw Error('Choose a nonempty TaxML file smaller than 10 MB.');
  if(!(profileFile instanceof Blob)||profileFile.size>1024*1024)throw Error('Choose a wire-profile JSON file smaller than 1 MB.');
  if(!Array.isArray(registryFiles)||!registryFiles.length||registryFiles.length>8)throw Error('Choose 1 to 8 caller-owned XPRF registry files.');
  if(acknowledged!==true)throw Error('Review and acknowledge the selected wire profile before inspection.');
  let profile;try{profile=JSON.parse(await profileFile.text());}catch{throw Error('The selected wire profile is not valid JSON.');}
  const carriers=[];
  for(const carrier of registryFiles){if(!(carrier instanceof Blob)||!carrier.size||carrier.size>32*1024*1024)throw Error('Choose registry files smaller than 32 MB each.');const bytes=new Uint8Array(await carrier.arrayBuffer());carriers.push({base64:encoded(bytes),sha256:await hash(bytes)});}
  const bytes=new Uint8Array(await file.arrayBuffer());
  const request={base64:encoded(bytes),container,profile,carriers,profile_acknowledged:acknowledged};
  const result=await window.taxLocalEngine('taxml_inspect',request);
  for(const candidate of result.candidates||[])sourceContexts.set(candidate,{request,candidateHash:candidate.receipt.candidate_sha256});
  return result;
 }
 async function correctedSource(candidate,values,confirmed){
  const context=sourceContexts.get(candidate);
  if(!context||candidate.can_review!==true||candidate.missing_boxes?.length)throw Error('Reopen and inspect the source before exporting a corrected XML copy.');
  if(confirmed!==true)throw Error('Review and confirm the corrected source box amounts first.');
  const names=candidate.record_type==='interest'?interestMoney:requiredMoney.slice(0,6);
  const amounts=Object.fromEntries(names.map(name=>[name,String(values?.[name]??'').trim()]));
  return window.taxLocalEngine('taxml_export',{inspection:context.request,expected_candidate_sha256:context.candidateHash,amounts,confirmed});
 }
 async function reviewedRecord(candidate,values,source,confirmed,defaults){
  if(!candidate||candidate.record_type&&candidate.record_type!=='w2'||candidate.can_review!==true||candidate.missing_boxes?.length)throw Error('This W-2 candidate has unresolved source facts and cannot be added.');
  if(confirmed!==true)throw Error('Check the tax year, owner and every amount against the source W-2 first.');
  if(!values||!['taxpayer','spouse'].includes(values.owner))throw Error('Select taxpayer or spouse explicitly. Source flags do not establish ownership.');
  if(typeof values.employer!=='string'||!values.employer.trim())throw Error('Enter the employer name from the original W-2.');
  const row={...defaults,employer:values.employer.trim(),owner:values.owner};
  for(const name of requiredMoney){const text=String(values[name]??'').trim();if(!text||!/^\d+(?:\.\d{1,2})?$/.test(text))throw Error('Enter every W-2 amount explicitly, including zero for a verified blank Box 7 or Box 10.');row[name]=text;}
  const receipt=candidate.receipt;
  const metadata=window.taxRecordMetadata.newRecord({...source,method:'taxml',taxml_receipt:receipt});
  const fingerprint=await window.taxRecordMetadata.fingerprint(row);
  metadata.reviewed=true;metadata.reviewed_at=new Date().toISOString();metadata.reviewed_fingerprint=fingerprint;metadata.row_fingerprint=fingerprint;
  return {row,metadata};
 }
 async function reviewedInterest(candidate,values,source,confirmed){
  if(!candidate||candidate.record_type!=='interest'||candidate.can_review!==true||candidate.missing_boxes?.length)throw Error('This interest candidate has unresolved source facts and cannot be added.');
  if(confirmed!==true||values?.supported_scope!==true)throw Error('Confirm tax year, household, every amount and the supported interest situation first.');
  if(typeof values.payer!=='string'||!values.payer.trim()||values.payer.trim().length>256)throw Error('Enter the payer name from the original 1099-INT.');
  const boxes=window.taxIncomePreparation.interestBoxes(Object.fromEntries(interestMoney.map(name=>[name,String(values[name]??'').trim()])));
  const cents=key=>BigInt(boxes[key].replace('.','')),taxable=cents('interest_income')+cents('treasury_interest');
  const row={payer:values.payer.trim(),taxable:String(taxable/100n)+'.'+String(taxable%100n).padStart(2,'0'),tax_exempt:boxes.tax_exempt_interest,federal_withholding:boxes.federal_withholding};
  const metadata=window.taxIncomePreparation.newRecord();
  metadata.source_document=window.taxRecordMetadata.validateSource({...source,method:'taxml',taxml_receipt:candidate.receipt});
  metadata.taxml_interest_boxes=boxes;
  const fingerprint=await window.taxIncomePreparation.fingerprint('interest',row);
  metadata.reviewed=true;metadata.reviewed_at=new Date().toISOString();metadata.reviewed_fingerprint=fingerprint;metadata.row_fingerprint=fingerprint;
  return{row,metadata};
 }
 window.taxMLImport={inspect,reviewedRecord,reviewedInterest,correctedSource,requiredMoney,interestMoney};
})();
