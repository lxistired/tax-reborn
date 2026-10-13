'use strict';
// Offline Android/PWA adapter. Desktop uses the private loopback SQLite API.
(function () {
  const offline = new URLSearchParams(location.search).get('offline') === '1';
  let worker, sequence = 0, dbPromise;
  const pending = new Map();
  const uuid = () => crypto.randomUUID();
  const validId = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value);
  const caps = {product:'Tax Reborn',project_number:'000002',version:'2026.10.13-preview.1',tax_year:2025,
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
  async function store(operation,id,record) {
    const db = await database();
    return new Promise((resolve,reject)=>{
      const transaction = db.transaction('returns',operation==='get'||operation==='all'?'readonly':'readwrite');
      const object = transaction.objectStore('returns');
      const request = operation==='get'?object.get(id):operation==='all'?object.getAll():operation==='put'?object.put(record):object.delete(id);
      let result;
      request.onsuccess = ()=>{result=request.result;};
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
          const record = {id,data:body.data,result,states:previous?.states || {},updated_at:new Date().toISOString()};
          await store('put',id,record); return json(record);
        }
      }
      const match = path.match(/^\/api\/returns\/([^/]+)(?:\/(export\.json|worksheet\.html|form1040\.pdf|states))?$/);
      if (match && validId(match[1])) {
        const record = await store('get',match[1]);
        if (!record) return json({error:'Return not found'},404);
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
          if (match[2]==='form1040.pdf') {
            const output = await engine('pdf',record);
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
