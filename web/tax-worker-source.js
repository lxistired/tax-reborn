'use strict';
// Same independently written Python engine as desktop; no remote tax service.
let engineReady;
let pdfReady;
let taxmlReady;
function ready() {
  if (!engineReady) engineReady = (async () => {
    const py = await loadPyodide({indexURL: new URL('vendor/pyodide/', self.location.href).href});
    const base = new URL('./', self.location.href);
    const names = ['tax_engine.py','tax_extended.py','tax_credits.py','tax_additional.py','tax_longtail.py','tax_filing.py','presentation_schema.py','rules_2025.json','forms/paper-fact-schema-2025.json'];
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
      else if (command === 'taxml_inspect') {
        if (!taxmlReady) taxmlReady = (async()=>{
          const base=new URL('./',self.location.href),names=['taxml_wire.py','taxml_preparation.py'];
          const text=await Promise.all(names.map(async name=>{const response=await fetch(new URL(name,base));if(!response.ok)throw Error('Local TaxML inspector resource missing: '+name);return response.text();}));
          names.forEach((name,index)=>py.FS.writeFile('/home/pyodide/'+name,text[index]));
          await py.runPythonAsync('import taxml_preparation');
        })();
        await taxmlReady;
        code='json.dumps(taxml_preparation.inspect_request(json.loads(_tax_input_json)), allow_nan=False)';
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
      self.postMessage({id, error: String(error.message || error)});
    }
  });
};
