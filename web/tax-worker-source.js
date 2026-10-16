'use strict';
// Same independently written Python engine as desktop; no remote tax service.
let engineReady;
let pdfReady;
let taxmlReady;
let sourceMCReady;
const sourceMCRuntimeSHA='0f5b412fba280a37f920dd4b6314ea3c8507938c8afd4e01799967884f3854ba';
async function sourceMCFiles(py) {
 if(!sourceMCReady)sourceMCReady=(async()=>{
  const base=new URL('./',self.location.href);
  const digest=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
  const resource=async name=>{const r=await fetch(new URL(name,base));if(!r.ok)throw Error('Local source-value report resource missing: '+name);return new Uint8Array(await r.arrayBuffer());};
  const raw=await resource('source-mc-runtime.json');
  if(await digest(raw)!==sourceMCRuntimeSHA)throw Error('Local source-value runtime manifest changed');
  const manifest=JSON.parse(new TextDecoder().decode(raw));
  const rows=manifest.modules;
  if(manifest.format!=='tax-reborn-source-mc-runtime-v1'||manifest.command!=='source_mc_input_diagnose'||manifest.python_module_limit!==32||!Array.isArray(rows)||rows.length!==28||new Set(rows.map(r=>r.path)).size!==rows.length||rows.filter(r=>r.path.endsWith('.py')).length>32||rows.some(r=>!r||typeof r.path!=='string'||!(/^(?:source_mc_input\.py|source_mc\/[A-Za-z_0-9]+\.py|source-mc-authority\.json)$/.test(r.path))||!Number.isSafeInteger(r.bytes)||r.bytes<1||r.bytes>1048576||!(/^[0-9a-f]{64}$/.test(r.sha256))))throw Error('Invalid local source-value runtime allowlist');
  const bytes=await Promise.all(rows.map(async row=>{const value=await resource(row.path);if(value.length!==row.bytes||await digest(value)!==row.sha256)throw Error('Local source-value runtime changed: '+row.path);return value;}));
  py.FS.mkdirTree('/home/pyodide/source_mc');
  rows.forEach((row,i)=>py.FS.writeFile('/home/pyodide/'+row.path,bytes[i]));
  await py.runPythonAsync('import source_mc_input');
 })();
 return sourceMCReady;
}
function taxWorkerError(error) {
  const message=String(error?.message||error);
  if(error?.name!=='PythonError')return message;
  const type=String(error.type||'').split('.').pop(),last=message.trimEnd().split('\n').pop()||'';
  if(type==='CompatibilityConfigError')return 'The selected compatibility configuration is invalid. Choose a valid local configuration.';
  if(type==='UnsupportedEncryptionRoute')return 'This encrypted source protection route is not supported.';
  if(type==='EncryptedContainerError')return 'This compatibility configuration cannot read the selected source. Check the original file and selected configuration.';
  const expected=last.match(/^(?:[A-Za-z_]\w*\.)*(ValueError|UnsupportedProfile): (.+)$/);
  if(expected&&expected[1]===type)return expected[2];
  console.error('Local engine exception',message);
  return 'Local processing could not complete. Keep the source file and try again.';
}
function ready() {
  if (!engineReady) engineReady = (async () => {
    const py = await loadPyodide({indexURL: new URL('vendor/pyodide/', self.location.href).href});
    const base = new URL('./', self.location.href);
    const names = ['tax_engine.py','tax_special_capital.py','tax_child_income.py','tax_extended.py','tax_credits.py','tax_additional.py','tax_longtail.py','tax_filing.py','presentation_schema.py','rules_2025.json','forms/paper-fact-schema-2025.json'];
    const contents = await Promise.all(names.map(async name => {
      const response = await fetch(new URL(name, base));
      if (!response.ok) throw new Error('Offline tax engine resource missing: '+name);
      return response.text();
    }));
    py.FS.mkdirTree('/home/pyodide/forms');
    names.forEach((name,index)=>py.FS.writeFile('/home/pyodide/'+name, contents[index]));
    await py.runPythonAsync('import sys\nsys.path.insert(0, "/home/pyodide")\nimport json, tax_engine, presentation_schema');
    return py;
  })();
  return engineReady;
}
let queue = Promise.resolve();
self.onmessage = event => {
  const {id, command, payload} = event.data;
  queue = queue.catch(()=>{}).then(async () => {
    try {
      const py = await ready();
      py.globals.set('_tax_input_json', JSON.stringify(payload || {}));
      let code;
      if (command === 'calculate') code = 'json.dumps(tax_engine.calculate_return(json.loads(_tax_input_json)), allow_nan=False)';
      else if (command === 'schema') code = 'json.dumps({"default_return": tax_engine.default_return(), "demos": tax_engine.demo_returns(), "capabilities": presentation_schema.capabilities()}, allow_nan=False)';
      else if (['taxml_inspect','taxml_export','binary_tax_edit','source_stored_cell_correct','source_link_diagnostics','source_mc_input_diagnose','default_encrypted_inspect','default_encrypted_taxml_inspect'].includes(command)) {
        if (!taxmlReady) taxmlReady = (async()=>{
          const base=new URL('./',self.location.href),names=['taxml_wire.py','taxml_native.py','taxml_mac.py','taxml_xml_edit.py','taxml_preparation.py','taxml_container.py','binary_tax.py','binary_derived.py','source_integer.py','source_stored_cell.py','source_link_diagnostics.py'];
          const response=await fetch(new URL('binary-runtime.json',base));
          if(!response.ok)throw Error('Local binary tax-data manifest missing');
          const manifest=await response.json();
          if(manifest.format!=='tax-reborn-binary-runtime-v1'||!Array.isArray(manifest.modules)||!manifest.modules.length||manifest.modules.length>64||manifest.modules.some(name=>typeof name!=='string'||!/^interop\/(?:__init__|(?:form_core|derived_form|container)\/[a-z_0-9]+)\.py$/.test(name)))throw Error('Invalid local binary tax-data manifest');
          names.push(...manifest.modules);
          const text=await Promise.all(names.map(async name=>{const response=await fetch(new URL(name,base));if(!response.ok)throw Error('Local TaxML inspector resource missing: '+name);return response.text();}));
          py.FS.mkdirTree('/home/pyodide/interop/form_core');py.FS.mkdirTree('/home/pyodide/interop/derived_form');py.FS.mkdirTree('/home/pyodide/interop/container');
          names.forEach((name,index)=>py.FS.writeFile('/home/pyodide/'+name,text[index]));
          await py.runPythonAsync('import taxml_preparation, binary_tax, source_stored_cell, source_link_diagnostics\nfrom interop.container import default_encrypted_import');
        })();
        await taxmlReady;
        if(command==='default_encrypted_taxml_inspect') {
          code=`import base64,json
from interop.container import default_encrypted_import
_default_taxml_request=json.loads(_tax_input_json)
if not isinstance(_default_taxml_request,dict) or set(_default_taxml_request)!={'base64','compatibility','is_previous_year_return','profile','carriers','profile_acknowledged'}:
 raise ValueError('Invalid default encrypted TaxML request.')
_raw=base64.b64decode(_default_taxml_request['base64'],validate=True)
_taxml_result=default_encrypted_import.inspect_default_taxml_mapping(_raw,compatibility=_default_taxml_request['compatibility'],is_previous_year_return=_default_taxml_request['is_previous_year_return'],profile=_default_taxml_request['profile'],carriers=_default_taxml_request['carriers'],profile_acknowledged=_default_taxml_request['profile_acknowledged'])
json.dumps(_taxml_result,allow_nan=False)`
        } else if(command==='default_encrypted_inspect') {
          code=`import base64,hashlib,json
from interop.container.default_encrypted_reference import load_default_encrypted_container,read_entities
_default_request=json.loads(_tax_input_json)
if not isinstance(_default_request,dict) or set(_default_request)!={'base64','compatibility','is_previous_year_return'}:
 raise ValueError('Invalid default encrypted .tax request.')
_raw=base64.b64decode(_default_request['base64'],validate=True)
_container=load_default_encrypted_container(_raw,compatibility=_default_request['compatibility'],is_previous_year_return=_default_request['is_previous_year_return'])
def _ack(payload,document):
 try:
  value=json.loads(payload.decode('utf-8'))
  return {'format':'json-member','value':value}
 except (UnicodeDecodeError,json.JSONDecodeError):
  return {'format':'opaque-binary','decoded_bytes':len(payload),'decoded_sha256':hashlib.sha256(payload).hexdigest()}
_decoded=read_entities(_container,_ack)
_inventory=_container.inventory()
_documents=[]
for document,(_,parsed) in zip(_container.documents,_decoded):
 item={'entity_type':document.entity_type,'entity_type_code':document.entity_type_code,'entity_key':document.entity_key,'decoded_sha256':hashlib.sha256(document.payload).hexdigest(),'decoded_bytes':len(document.payload),'parsed':parsed,'payload_base64':base64.b64encode(document.payload).decode('ascii')}
 _documents.append(item)
json.dumps({'format':'tax-reborn-default-encrypted-inspection-v1','branch':_container.branch,'encrypted_source_sha256':_container.encrypted_source_sha256,'inventory':_inventory,'documents':_documents,'unreferenced_members':[name.decode('utf-8','strict') for name in _container.unreferenced_members]},allow_nan=False)`
        } else if(command==='source_mc_input_diagnose') {
          await sourceMCFiles(py);
          code='json.dumps(source_mc_input.diagnose_request(json.loads(_tax_input_json)), allow_nan=False)';
        } else code=command==='taxml_inspect'?'json.dumps(taxml_preparation.inspect_request(json.loads(_tax_input_json)), allow_nan=False)':command==='binary_tax_edit'?'json.dumps(binary_tax.edit_request(json.loads(_tax_input_json)), allow_nan=False)':command==='source_stored_cell_correct'?'json.dumps(source_stored_cell.correct_request(json.loads(_tax_input_json)), allow_nan=False)':command==='source_link_diagnostics'?'json.dumps(source_link_diagnostics.inspect_request(json.loads(_tax_input_json)), allow_nan=False)':'json.dumps(taxml_preparation.export_request(json.loads(_tax_input_json)), allow_nan=False)';
      }
      else if (['pdf','packet_pdf','masked_pdf','paper_status','document_text'].includes(command)) {
        if (!pdfReady) pdfReady = (async () => {
          const base = new URL('./', self.location.href);
          const responses = await Promise.all(['forms.py','forms/f1040-2025.pdf','vendor/python/pypdf-6.10.0.whl'].map(name=>fetch(new URL(name,base))));
          if (responses.some(response=>!response.ok)) throw new Error('Offline PDF resources missing');
          py.FS.writeFile('/home/pyodide/forms.py', await responses[0].text());
          py.FS.mkdirTree('/home/pyodide/forms');
          py.FS.writeFile('/home/pyodide/forms/f1040-2025.pdf', new Uint8Array(await responses[1].arrayBuffer()));
          py.FS.writeFile('/home/pyodide/pypdf.whl', new Uint8Array(await responses[2].arrayBuffer()));
          const resource=async name=>{const response=await fetch(new URL(name,base));if(!response.ok)throw new Error('Official PDF resource missing: '+name);return new Uint8Array(await response.arrayBuffer());};
          const sourceBytes=await resource('forms/official-sources-2025.json');
          const manifest=JSON.parse(new TextDecoder().decode(sourceBytes));
          const additional=['official_forms.py','privacy_review.py','forms/official-field-map-2025.json','forms/official-sources-2025.json',...manifest.forms.filter(row=>row.sha256).map(row=>{if(!/^[A-Za-z0-9_-]+\.pdf$/.test(row.path))throw new Error('Invalid bundled IRS template path');return 'forms/'+row.path;})];
          const bytes=await Promise.all(additional.map(resource));
          additional.forEach((name,index)=>py.FS.writeFile('/home/pyodide/'+name,bytes[index]));
          await py.runPythonAsync('sys.path.insert(0, "/home/pyodide/pypdf.whl")\nimport forms, base64');
        })();
        await pdfReady;
        if (command === 'pdf') code = 'json.dumps({"base64": base64.b64encode(forms.form1040_pdf(json.loads(_tax_input_json))).decode("ascii")})';
        else if (command === 'packet_pdf') code = 'json.dumps({"base64": base64.b64encode(forms.paper_packet_pdf(json.loads(_tax_input_json))).decode("ascii")})';
        else if (command === 'masked_pdf') code = 'json.dumps({"base64": base64.b64encode(forms.masked_review_pdf(json.loads(_tax_input_json))).decode("ascii")})';
        else if (command === 'paper_status') code = 'json.dumps(forms.packet_status(json.loads(_tax_input_json)), allow_nan=False)';
        else code = `import io
from pypdf import PdfReader
_doc=PdfReader(io.BytesIO(base64.b64decode(json.loads(_tax_input_json)["base64"])), strict=False)
if _doc.is_encrypted: raise ValueError("Encrypted PDF: unlock a local copy before importing.")
if len(_doc.pages)>25: raise ValueError("Document import supports at most 25 pages.")
json.dumps({"text": chr(10).join(page.extract_text() or "" for page in _doc.pages), "pages": len(_doc.pages)})`;
      }
      else throw new Error('Unknown offline engine command');
      const result = JSON.parse(await py.runPythonAsync(code));
      self.postMessage({id, result});
    } catch (error) {
      self.postMessage({id, error: taxWorkerError(error)});
    }
  });
};
