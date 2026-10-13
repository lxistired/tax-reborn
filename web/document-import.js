'use strict';
(function(){
 let ocrPromise, scriptPromise, queue=Promise.resolve();
 const labels={wages:/\b1\s+Wages[,\s]+tips[,\s]+other\s+compensation\b/i,
 federal_withholding:/\b2\s+Federal\s+income\s+tax\s+withheld\b/i,
 social_security_wages:/\b3\s+Social\s+security\s+wages\b/i,
 social_security_withholding:/\b4\s+Social\s+security\s+tax\s+withheld\b/i,
 medicare_wages:/\b5\s+Medicare\s+wages\s+and\s+tips\b/i,
 medicare_withholding:/\b6\s+Medicare\s+tax\s+withheld\b/i,
 social_security_tips:/\b7\s+Social\s+security\s+tips\b/i,
 dependent_care_benefits:/\b10\s+Dependent\s+care\s+benefits\b/i};
 function parse(text,confidence=0){
  const warnings=['Verify every amount against the source document before adding a W-2. OCR never establishes tax eligibility.'];
  const form_type=/(?:\bW[-–\s]?2\b|wage\s+and\s+tax\s+statement)/i.test(text)?'w2':'unknown';
  if(!/\b2025\b/.test(text))warnings.push('The extracted text does not establish tax year 2025.');
  const candidates={};
  for(const [key,pattern] of Object.entries(labels)){
   const match=pattern.exec(text);if(!match)continue;
   const after=text.slice(match.index+match[0].length,match.index+match[0].length+160);
   const nextLabel=/\b(?:[1-9]|1[0-4])\s+(?:Federal|Social|Medicare|Wages|Allocated|Nonqualified|Dependent)/i.exec(after);
   const region=nextLabel?after.slice(0,nextLabel.index):after;
   const values=[...region.matchAll(/(?:\$\s*)?((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})(?!\d)/g)];
   if(values.length===1)candidates[key]=values[0][1].replaceAll(',','');
   else warnings.push('Box '+key.replaceAll('_',' ')+': ambiguous or missing amount; enter manually.');
  }
  if(form_type==='unknown')warnings.push('Document type was not recognized as W-2. Manual entry is required.');
  return {text:text.slice(0,100000),form_type,candidates,warnings,confidence:Number(confidence)||0};
 }
 function loadOCR(){
  if(!scriptPromise)scriptPromise=new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='vendor/tesseract/tesseract.min.js';script.onload=resolve;script.onerror=()=>reject(Error('Local OCR runtime is missing.'));document.head.append(script);});
  if(!ocrPromise)ocrPromise=scriptPromise.then(()=>window.Tesseract.createWorker('eng',1,{workerPath:new URL('ocr-worker.js',location.href).href,langPath:new URL('vendor/tesseract/',location.href).href,corePath:new URL('vendor/tesseract/',location.href).href,workerBlobURL:false})).catch(error=>{ocrPromise=null;throw error;});
  return ocrPromise;
 }
 async function extract(file){
  if(!(file instanceof Blob)||file.size>10000000)throw Error('Choose a document smaller than 10 MB.');
  if(file.type==='application/pdf'||/\.pdf$/i.test(file.name||'')){
   const bytes=new Uint8Array(await file.arrayBuffer());let raw='';for(let i=0;i<bytes.length;i+=16384)raw+=String.fromCharCode(...bytes.subarray(i,i+16384));
   const output=await window.taxLocalEngine('document_text',{base64:btoa(raw)});
   const result=parse(output.text,100);
   if(!output.text.trim())result.warnings.push('This PDF is scanned or has no readable text. Attach a photo of the W-2 and use local image extraction, or enter the amounts manually.');
   return result;
  }
  if(!/^image\//.test(file.type))throw Error('Only a W-2 image or PDF can be extracted.');
  const worker=await loadOCR();const output=await worker.recognize(file);
  return parse(output.data.text,output.data.confidence);
 }
 window.parseTaxDocumentText=parse;
 window.extractTaxDocument=file=>{const task=queue.catch(()=>{}).then(async()=>{let timeout;try{return await Promise.race([extract(file),new Promise((resolve,reject)=>{timeout=setTimeout(()=>reject(Error('Local extraction timed out. Reload before retrying, or enter the document manually.')),120000);})]);}finally{clearTimeout(timeout);}});queue=task;return task;};
})();
