'use strict';
(function(){
 const requiredMoney=['wages','federal_withholding','social_security_wages','social_security_withholding','medicare_wages','medicare_withholding','social_security_tips','dependent_care_benefits'];
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
  return window.taxLocalEngine('taxml_inspect',{base64:encoded(bytes),container,profile,carriers,profile_acknowledged:acknowledged});
 }
 async function reviewedRecord(candidate,values,source,confirmed,defaults){
  if(!candidate||candidate.can_review!==true||candidate.missing_boxes?.length)throw Error('This candidate has unresolved source facts and cannot be added.');
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
 window.taxMLImport={inspect,reviewedRecord,requiredMoney};
})();
