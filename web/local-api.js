'use strict';
// Offline Android/PWA adapter. Desktop uses the private loopback SQLite API.
(function () {
  // This state is separate from federal data and never enters the calculation worker.
  let w2Defaults = {};
  const metadataId = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value);
  const w2Money = new Set(['wages','federal_withholding','social_security_wages','social_security_withholding','medicare_wages','medicare_withholding','social_security_tips','dependent_care_benefits']);
  w2Defaults={employer:'',owner:'taxpayer',...Object.fromEntries([...w2Money].map(key=>[key,'0']))};
  const sorted = value => Array.isArray(value) ? value.map(sorted) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key=>[key,sorted(value[key])])) : value;
  function canonicalW2(row) {
    const value={...w2Defaults,...row};
    for(const key of w2Money){
      const text=String(value[key]??'0').trim()||'0';
      if(!/^-?\d+(\.\d{1,2})?$/.test(text))throw Error('W-2 review requires valid USD amounts with at most two decimal places');
      const negative=text.startsWith('-'),[whole,part='']=text.replace(/^-/,'').split('.');
      const cents=BigInt(whole)*100n+BigInt(part.padEnd(2,'0'));
      value[key]=(negative&&cents!==0n?'-':'')+String(cents/100n)+'.'+String(cents%100n).padStart(2,'0');
    }
    return JSON.stringify(sorted(value));
  }
  async function w2Fingerprint(row) {
    const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonicalW2(row)));
    return [...new Uint8Array(hash)].map(byte=>byte.toString(16).padStart(2,'0')).join('');
  }
  function localSource(value) {
    if(value==null)return null;
    if(typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(key=>!['document_id','return_id','name','method','taxml_receipt'].includes(key))||!metadataId(value.document_id)||!metadataId(value.return_id)||!['ocr','manual','taxml'].includes(value.method)||typeof(value.name??'')!=='string'||(value.name||'').length>256||/[\u0000-\u001f\u007f]/.test(value.name||''))throw Error('Invalid local source-document reference');
    const output={document_id:value.document_id,return_id:value.return_id,name:value.name||'',method:value.method};
    if(value.method==='taxml'){
      const receipt=value.taxml_receipt,keys=['source_sha256','wire_profile_sha256','template_carrier_sha256','template_resource_id','form_path','archive_member','candidate_sha256'];
      if(!receipt||typeof receipt!=='object'||Array.isArray(receipt)||Object.keys(receipt).length!==keys.length||keys.some(key=>!Object.hasOwn(receipt,key))||['source_sha256','wire_profile_sha256','template_carrier_sha256','candidate_sha256'].some(key=>typeof receipt[key]!=='string'||!/^[0-9a-f]{64}$/.test(receipt[key]))||!Number.isInteger(receipt.template_resource_id)||receipt.template_resource_id<0||receipt.template_resource_id>65535||typeof receipt.form_path!=='string'||!/^\d{1,6}(?:\/\d{1,6}){1,2}$/.test(receipt.form_path)||receipt.archive_member!==null&&(typeof receipt.archive_member!=='string'||!receipt.archive_member||receipt.archive_member.length>1024||/[\u0000-\u001f\u007f]/.test(receipt.archive_member)))throw Error('Invalid TaxML source receipt');
      output.taxml_receipt=JSON.parse(JSON.stringify(receipt));
    }else if(Object.hasOwn(value,'taxml_receipt'))throw Error('TaxML source receipt requires the TaxML method');
    return output;
  }
  async function normalizeMetadata(data,provided,previous=null,options={}) {
    const rows=data.w2||[];if(!Array.isArray(rows)||rows.length>1000)throw Error('Invalid W-2 preparation record collection');
    const fingerprints=await Promise.all(rows.map(async row=>{try{return await w2Fingerprint(row);}catch(error){if(options.draft)return null;throw error;}}));let entries;
    if(provided!=null){
      if(typeof provided!=='object'||Array.isArray(provided)||provided.version!==1||Object.keys(provided).some(key=>!['version','w2_records','investment_records','income_document_records','income_import_events'].includes(key))||!Array.isArray(provided.w2_records)||provided.w2_records.length!==rows.length)throw Error('W-2 preparation records must match the W-2 collection');
      entries=provided.w2_records;
    }else{
      entries=fingerprints.map(hash=>{const old=(previous?.w2_records||[]).filter(item=>item.row_fingerprint===hash);return hash&&old.length===1&&fingerprints.filter(value=>value===hash).length===1?old[0]:{};});
    }
    const seen=new Set(),records=entries.map((item,index)=>{
      if(!item||typeof item!=='object'||Array.isArray(item)||Object.keys(item).some(key=>!['record_id','row_fingerprint','reviewed','reviewed_at','reviewed_fingerprint','source_document'].includes(key)))throw Error('Invalid W-2 preparation record');
      const id=item.record_id||crypto.randomUUID();if(!metadataId(id)||seen.has(id))throw Error('W-2 preparation record identifiers must be unique UUIDv4 values');seen.add(id);
      if(item.reviewed!=null&&typeof item.reviewed!=='boolean')throw Error('W-2 reviewed status must be true or false');
      const checked=!!item.reviewed;
      if(checked&&(!/^[0-9a-f]{64}$/.test(item.reviewed_fingerprint||'')||typeof item.reviewed_at!=='string'||item.reviewed_at.length>40||!/(?:Z|[+-]\d\d:\d\d)$/.test(item.reviewed_at)||!Number.isFinite(Date.parse(item.reviewed_at))))throw Error('Reviewed W-2 requires its checked values and valid review time');
      const reviewed=checked&&item.reviewed_fingerprint===fingerprints[index];
      const source=localSource(item.source_document),oldSource=previous?.w2_records?.find(entry=>entry.record_id===id)?.source_document;
      if(oldSource?.method==='taxml'&&JSON.stringify(sorted(source))!==JSON.stringify(sorted(oldSource)))throw Error('Saved TaxML source receipts cannot be removed or changed');
      return {record_id:id,row_fingerprint:fingerprints[index],reviewed,reviewed_at:reviewed?item.reviewed_at:null,reviewed_fingerprint:reviewed?fingerprints[index]:null,source_document:source};
    });
    const investments=await window.taxInvestmentCorrections.normalize(data.capital_gains||[],provided?.investment_records,previous?.investment_records,options);
    const income=await window.taxIncomePreparation.normalize(data,provided?.income_document_records,previous?.income_document_records,options);
    const events=await window.taxIncomePreparation.normalizeEvents(Object.hasOwn(provided||{},'income_import_events')?provided.income_import_events:previous?.income_import_events||[]);
    for(const old of previous?.income_import_events||[]){const current=events.find(item=>item.event_id===old.event_id);if(!current||JSON.stringify(sorted(current))!==JSON.stringify(sorted(old)))throw Error('Saved income-import history cannot be removed or changed');}
    return {version:1,w2_records:records,investment_records:investments,income_document_records:income,income_import_events:events};
  }
  window.taxRecordMetadata={setDefaults:value=>{w2Defaults={...value};},fingerprint:w2Fingerprint,canonicalW2,normalize:normalizeMetadata,
    empty:()=>({version:1,w2_records:[],income_document_records:{interest:[],dividends:[]},income_import_events:[]}),newRecord:source=>({record_id:crypto.randomUUID(),row_fingerprint:null,reviewed:false,reviewed_at:null,reviewed_fingerprint:null,source_document:localSource(source)})};
  const offline = new URLSearchParams(location.search).get('offline') === '1';
  let worker, sequence = 0, dbPromise;
  const pending = new Map();
  const uuid = () => crypto.randomUUID();
  const validId = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value);
  const caps = {product:'Tax Reborn',project_number:'000002',version:'2026.10.14-preview.11',tax_year:2025,
    jurisdiction:'US federal',currency:'USD',electronic_filing:false,state_returns:"31 full-year resident state drafts",official_product_parity:false,
    storage:'private on-device IndexedDB',requires_account:false,offline:true};
  function engine(command, payload) {
    if (!worker) {
      worker = new Worker('tax-worker.js');
      worker.onmessage = event => {
        const item = pending.get(event.data.id);
        if (!item) return;
        clearTimeout(item.timeout); pending.delete(event.data.id);
        event.data.error ? item.reject(new Error(event.data.error)) : item.resolve(event.data.result);
      };
      worker.onerror = event => {
        for (const item of pending.values()) {clearTimeout(item.timeout); item.reject(new Error(event.message || 'Offline calculation engine failed to load'));}
        pending.clear(); worker.terminate(); worker = null;
      };
    }
    const id = ++sequence;
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(()=>{pending.delete(id);reject(new Error('Offline engine took too long; please reload before retrying.'));},180000);
      pending.set(id,{resolve,reject,timeout}); worker.postMessage({id,command,payload});
    });
  }
  function database() {
    if (!dbPromise) dbPromise = new Promise((resolve,reject)=>{
      const request = indexedDB.open('TaxRebornReturns',1);
      request.onupgradeneeded = () => request.result.createObjectStore('returns',{keyPath:'id'});
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error('Device storage unavailable. Export a backup before closing.'));
    });
    return dbPromise;
  }
  async function store(operation,id,record,expectedRevision) {
    const db = await database();
    return new Promise((resolve,reject)=>{
      const transaction = db.transaction('returns',operation==='get'||operation==='all'?'readonly':'readwrite');
      const object = transaction.objectStore('returns');
      let result;
      if(operation==='put'&&expectedRevision!==undefined){
        const current=object.get(id);current.onsuccess=()=>{
          if((current.result?.updated_at??null)!==expectedRevision){reject(new Error('This saved return changed in another workspace. Reopen it before saving the import'));transaction.abort();return;}
          const put=object.put(record);put.onsuccess=()=>{result=put.result;};
        };
      }else{
        const request = operation==='get'?object.get(id):operation==='all'?object.getAll():operation==='put'?object.put(record):object.delete(id);
        request.onsuccess = ()=>{result=request.result;};
      }
      transaction.oncomplete = ()=>resolve(result);
      transaction.onerror = transaction.onabort = ()=>reject(new Error('Device save did not complete; keep the draft open and export a backup.'));
    });
  }
  window.taxLocalEngine = engine;
  if (!offline) { window.taxApi = (path, options) => fetch(path, options); return; }
  const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function worksheet(record) {
    const r = record.result;
    return '<!doctype html><meta charset="utf-8"><title>2025 Federal tax worksheet</title><style>body{font:14px system-ui;max-width:850px;margin:35px auto}td,th{padding:7px;border-bottom:1px solid #ddd}table{width:100%;border-collapse:collapse}.notice{padding:12px;border:2px solid #a76a00}</style><h1>Tax Reborn · 2025 US federal worksheet</h1><p>'+escape(record.data.name)+'</p><p class="notice">CALCULATION DRAFT · Not filed with IRS. State drafts are prepared separately. Electronic filing unavailable.</p><ul>'+r.blocking_issues.map(x=>'<li>'+escape(x)+'</li>').join('')+'</ul><table><tr><th>1040 line</th><th>USD whole dollars</th></tr>'+Object.entries(r.lines).map(([key,value])=>'<tr><td>'+escape(key)+'</td><td>'+escape((r.not_computed_lines||[]).includes(key)?'Not computed':value)+'</td></tr>').join('')+'</table><h2>Calculation trail</h2><table>'+r.trace.map(x=>'<tr><td>'+escape(x.label)+'</td><td>'+escape(x.amount)+'</td><td>'+escape(x.source)+'</td></tr>').join('')+'</table>';
  }
  const json = (value,status=200) => new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
  window.taxApi = async (requestPath,options={}) => {
    try {
      const path = new URL(requestPath,location.href).pathname;
      const method = (options.method || 'GET').toUpperCase();
      const body = options.body ? JSON.parse(options.body) : {};
      if (method==='GET' && path==='/api/health') return json(caps);
      if (method==='GET' && path==='/api/schema') {
        const data = await engine('schema');
        window.taxRecordMetadata.setDefaults(data.capabilities?.row_templates?.w2||{});
        return json({...data,capabilities:{...data.capabilities,...caps}});
      }
      if (method==='POST' && path==='/api/calculate') return json(await engine('calculate',body));
      if (path==='/api/returns') {
        if (method==='GET') return json({returns:(await store('all')).sort((a,b)=>b.updated_at.localeCompare(a.updated_at)).map(r=>({id:r.id,name:r.data.name,updated_at:r.updated_at,summary:r.result.summary}))});
        if (method==='POST') {
          const id = body.id || uuid();
          if (!validId(id) || typeof body.data?.name !== 'string' || !body.data.name.trim() || body.data.name.length>200) throw new Error('Expected a named return and valid UUIDv4 identifier');
          const result = await engine('calculate',body.data);
          const previous=await store('get',id);
          const metadata=await normalizeMetadata(body.data,body.metadata,previous?.metadata);
          if(Object.hasOwn(body,'expected_updated_at')&&body.expected_updated_at!==null&&(typeof body.expected_updated_at!=='string'||body.expected_updated_at.length>40))throw Error('Invalid saved-return revision');
          const record = {id,data:body.data,result,metadata,states:previous?.states || {},updated_at:new Date(Math.max(Date.now(),Number.isFinite(Date.parse(previous?.updated_at))?Date.parse(previous.updated_at)+1:0)).toISOString()};
          await store('put',id,record,Object.hasOwn(body,'expected_updated_at')?body.expected_updated_at:undefined); return json(record);
        }
      }
      const match = path.match(/^\/api\/returns\/([^/]+)(?:\/(export\.json|worksheet\.html|form1040\.pdf|paper-packet\.pdf|masked-review\.pdf|paper-checklist\.json|states))?$/);
      if (match && validId(match[1])) {
        const record = await store('get',match[1]);
        if (!record) return json({error:'Return not found'},404);
        const normalized=await normalizeMetadata(record.data,record.metadata);
        if(JSON.stringify(normalized)!==JSON.stringify(record.metadata)){record.metadata=normalized;await store('put',record.id,record);}
        if (match[2]==='states') {
          if(method==='GET') return json({states:record.states || {}});
          if(method==='POST') {
            if(!/^[a-z]{2}$/.test(body.jurisdiction || '') || !body.input || typeof body.input!=='object') throw new Error('Expected jurisdiction and state input');
            record.states={...(record.states || {}),[body.jurisdiction]:body.input}; await store('put',record.id,record); return json({states:record.states});
          }
        }
        if (method==='DELETE' && !match[2]) {await store('delete',match[1]);return json({ok:true});}
        if (method==='GET') {
          if (match[2]==='export.json') return json({format:'tax-reborn-return-v1',...record});
          if (match[2]==='worksheet.html') return new Response(worksheet(record),{headers:{'Content-Type':'text/html'}});
          if (match[2]==='paper-checklist.json') return json(await engine('paper_status',record));
          if (['form1040.pdf','paper-packet.pdf','masked-review.pdf'].includes(match[2])) {
            const output = await engine(match[2]==='masked-review.pdf'?'masked_pdf':match[2]==='paper-packet.pdf'?'packet_pdf':'pdf',record);
            const binary = atob(output.base64);
            return new Response(Uint8Array.from(binary,c=>c.charCodeAt(0)),{headers:{'Content-Type':'application/pdf'}});
          }
          return json(record);
        }
      }
      return json({error:'Unknown offline endpoint'},404);
    } catch (error) {return json({error:String(error.message || error)},400);}
  };
})();
