'use strict';
// Same independently written Python engine as desktop; no remote tax service.
let engineReady;
let pdfReady;
function ready() {
  if (!engineReady) engineReady = (async () => {
    const py = await loadPyodide({indexURL: new URL('vendor/pyodide/', self.location.href).href});
    const base = new URL('./', self.location.href);
    const names = ['tax_engine.py','tax_extended.py','tax_credits.py','tax_additional.py','rules_2025.json'];
    const contents = await Promise.all(names.map(async name => {
      const response = await fetch(new URL(name, base));
      if (!response.ok) throw new Error('Offline tax engine resource missing: '+name);
      return response.text();
    }));
    names.forEach((name,index)=>py.FS.writeFile('/home/pyodide/'+name, contents[index]));
    await py.runPythonAsync('import sys\nsys.path.insert(0, "/home/pyodide")\nimport json, tax_engine');
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
      else if (command === 'schema') code = 'json.dumps({"default_return": tax_engine.default_return(), "demos": tax_engine.demo_returns(), "capabilities": tax_engine.capabilities()}, allow_nan=False)';
      else if (command === 'pdf' || command === 'document_text') {
        if (!pdfReady) pdfReady = (async () => {
          const base = new URL('./', self.location.href);
          const responses = await Promise.all(['forms.py','forms/f1040-2025.pdf','vendor/python/pypdf-6.10.0.whl'].map(name=>fetch(new URL(name,base))));
          if (responses.some(response=>!response.ok)) throw new Error('Offline PDF resources missing');
          py.FS.writeFile('/home/pyodide/forms.py', await responses[0].text());
          py.FS.mkdirTree('/home/pyodide/forms');
          py.FS.writeFile('/home/pyodide/forms/f1040-2025.pdf', new Uint8Array(await responses[1].arrayBuffer()));
          py.FS.writeFile('/home/pyodide/pypdf.whl', new Uint8Array(await responses[2].arrayBuffer()));
          await py.runPythonAsync('sys.path.insert(0, "/home/pyodide/pypdf.whl")\nimport forms, base64');
        })();
        await pdfReady;
        if (command === 'pdf') code = 'json.dumps({"base64": base64.b64encode(forms.form1040_pdf(json.loads(_tax_input_json))).decode("ascii")})';
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
