'use strict';
(function(){
 let ocrPromise, ocrClient, queue=Promise.resolve();
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
  const candidates={},sources={};
  const lowQuality=Number(confidence)>0&&Number(confidence)<50;
  if(lowQuality)warnings.push('The photo text was not read confidently. Retake a close, straight, well-lit photo or enter the amounts manually. No amount is filled from this low-quality result.');
  for(const [key,pattern] of Object.entries(labels)){
   const match=pattern.exec(text);if(!match)continue;
   // Never scan into another box when OCR omitted or damaged its label.
   // Accept the label's own line, or one immediately following amount-only line.
   const after=text.slice(match.index+match[0].length).split(/\r?\n/);
   const inline=after[0]||'';
   const nextLabel=/\b(?:[1-9]|1[0-4])[\s.:)]+(?:Federal|Social|Medicare|Wages|Allocated|Nonqualified|Dependent)/i.exec(inline);
   let region=nextLabel?inline.slice(0,nextLabel.index):inline;
   if(!region.trim()&&/^\s*\$?\s*(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}\s*$/.test(after[1]||''))region=after[1];
   const values=[...region.matchAll(/(?:\$\s*)?((?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2})(?!\d)/g)];
   if(values.length===1&&!lowQuality){candidates[key]=values[0][1].replaceAll(',','');sources[key]=match[0]+' '+region.trim();}
   else warnings.push('Box '+key.replaceAll('_',' ')+': ambiguous or missing amount; enter manually.');
  }
  if(form_type==='unknown')warnings.push('Document type was not recognized as W-2. Manual entry is required.');
  return {text:text.slice(0,100000),form_type,candidates,sources,warnings,confidence:Number(confidence)||0};
 }
 function createOCRClient(){
  // Own the native Worker from construction onward. The pinned Tesseract
  // createWorker wrapper can leave language/initialization failures pending,
  // and does not expose its Worker until initialization has completed.
  const worker=new Worker(new URL('ocr-worker.js',location.href).href);
  const jobs=new Map();let sequence=0,closed=false,client;
  function terminate(error=Error('Local OCR was stopped. Retry extraction.')){
   if(closed)return;closed=true;worker.terminate();
   if(ocrClient===client){ocrClient=null;ocrPromise=null;}
   for(const job of jobs.values()){clearTimeout(job.timer);job.reject(error);}jobs.clear();
  }
  const names={load:'engine loading',loadLanguage:'language loading',initialize:'initialization',recognize:'image recognition'};
  function call(action,payload){
   if(closed)return Promise.reject(Error('Local OCR was reset. Retry extraction.'));
   const jobId='tax-ocr-'+(++sequence);
   return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>terminate(Error('Local OCR '+names[action]+' timed out. The engine was reset; retry extraction.')),120000);
    jobs.set(jobId,{resolve,reject,timer,action});
    try{worker.postMessage({workerId:'tax-local-ocr',jobId,action,payload});}
    catch(error){terminate(Error('Local OCR could not start this task. Retry extraction.'));}
   });
  }
  worker.onmessage=event=>{
   const packet=event.data,job=jobs.get(packet?.jobId);
   if(!job||packet.action!==job.action||packet.status==='progress')return;
   if(packet.status!=='resolve'&&packet.status!=='reject')return;
   clearTimeout(job.timer);jobs.delete(packet.jobId);
   if(packet.status==='resolve')job.resolve({data:packet.data});
   else job.reject(Error('Local OCR '+names[job.action]+' failed. The engine will restart on retry.'));
  };
  worker.onerror=event=>{event.preventDefault();terminate(Error('Local OCR runtime could not load. The engine was reset; retry extraction.'));};
  worker.onmessageerror=()=>terminate(Error('Local OCR returned an unreadable response. The engine was reset; retry extraction.'));
  client={terminate,initialize:async()=>{
   const path=new URL('vendor/tesseract/',location.href).href;
   // Same pinned worker protocol and OEM1/LSTM model as the prior wrapper.
   await call('load',{options:{lstmOnly:true,corePath:path,logging:false}});
   await call('loadLanguage',{langs:'eng',options:{langPath:path,gzip:true,lstmOnly:true}});
   await call('initialize',{langs:'eng',oem:1,config:{}});
  },recognize:async file=>call('recognize',{image:new Uint8Array(await file.arrayBuffer()),options:{},output:{text:true}})};
  return client;
 }
 function resetOCR(error){const client=ocrClient;ocrClient=null;ocrPromise=null;client?.terminate(error);}
 function loadOCR(){
  if(!ocrPromise){
   const client=createOCRClient();ocrClient=client;
   ocrPromise=client.initialize().then(()=>client).catch(error=>{if(ocrClient===client){ocrClient=null;ocrPromise=null;}client.terminate(error);throw error;});
  }
  return ocrPromise;
 }
 async function prepareOCRImage(file){
  // Keep the attachment untouched. Only the temporary OCR copy is filtered.
  // Large camera images of screens contain a pixel grid that can be mistaken
  // for thousands of characters. Preserve the whole frame and its proportions.
  const bitmap=await createImageBitmap(file);
  try{
   const width=bitmap.width,height=bitmap.height;
   if(!width||!height||width*height>40000000)throw Error('This image resolution is not supported for local extraction. The original attachment is kept.');
   const scale=Math.min(1,1600/Math.max(width,height));
   const w=Math.max(1,Math.round(width*scale)),h=Math.max(1,Math.round(height*scale));
   // Never enlarge small images or squeeze a narrow strip into a tiny height.
   if(scale===1||Math.min(w,h)<320)return file;
   const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;
   const context=canvas.getContext('2d',{willReadFrequently:true});
   if(!context)throw Error('The local image reader is unavailable. The original attachment is kept.');
   context.imageSmoothingEnabled=true;context.imageSmoothingQuality='high';
   context.drawImage(bitmap,0,0,w,h);
   const pixels=context.getImageData(0,0,w,h),gray=new Uint8Array(w*h),stride=w+1;
   const sum=new Float64Array(stride*(h+1)),squares=new Float64Array(stride*(h+1));
   for(let y=0;y<h;y++){
    let row=0,rowSquares=0;
    for(let x=0;x<w;x++){
     const i=y*w+x,o=i*4,value=Math.round(.299*pixels.data[o]+.587*pixels.data[o+1]+.114*pixels.data[o+2]);
     gray[i]=value;row+=value;rowSquares+=value*value;
     const j=(y+1)*stride+x+1;sum[j]=sum[j-stride]+row;squares[j]=squares[j-stride]+rowSquares;
    }
   }
   // Sauvola local threshold: 31-pixel window, k=.2, R=128. This suppresses
   // background texture without assuming a form layout or any expected amount.
   for(let y=0;y<h;y++)for(let x=0;x<w;x++){
    const x0=Math.max(0,x-15),x1=Math.min(w,x+16),y0=Math.max(0,y-15),y1=Math.min(h,y+16);
    const count=(x1-x0)*(y1-y0),a=y0*stride+x0,b=y0*stride+x1,c=y1*stride+x0,d=y1*stride+x1;
    const mean=(sum[d]-sum[b]-sum[c]+sum[a])/count;
    const variance=Math.max(0,(squares[d]-squares[b]-squares[c]+squares[a])/count-mean*mean);
    const threshold=mean*(1+.2*(Math.sqrt(variance)/128-1));
    const value=gray[y*w+x]<threshold?0:255,o=(y*w+x)*4;
    pixels.data[o]=pixels.data[o+1]=pixels.data[o+2]=value;pixels.data[o+3]=255;
   }
   context.putImageData(pixels,0,0);
   const prepared=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
   if(!prepared)throw Error('The local image copy could not be prepared. The original attachment is kept.');
   return prepared;
  }finally{bitmap.close();}
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
  const image=await prepareOCRImage(file);
  const worker=await loadOCR();const output=await worker.recognize(image);
  return parse(output.data.text,output.data.confidence);
 }
 window.parseTaxDocumentText=parse;
 window.extractTaxDocument=file=>{const task=queue.catch(()=>{}).then(async()=>{let timeout;try{return await Promise.race([extract(file),new Promise((resolve,reject)=>{timeout=setTimeout(()=>reject(Error('Local extraction timed out. The OCR engine was reset; retry extraction.')),120000);})]);}catch(error){resetOCR(error);throw error;}finally{clearTimeout(timeout);}});queue=task;return task;};
})();
