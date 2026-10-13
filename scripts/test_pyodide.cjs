const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),vendor=path.join(root,'web/vendor/pyodide');
const {loadPyodide}=require(path.join(vendor,'pyodide.js'));
(async()=>{const py=await loadPyodide({indexURL:vendor+path.sep});py.FS.mkdirTree('/app/tests');py.FS.mkdirTree('/app/fixtures');
 for(const name of ['tax_engine.py','tax_extended.py','tax_credits.py','tax_additional.py','rules_2025.json',...fs.readdirSync(path.join(root,'tests')).filter(n=>n.startsWith('test_')&&n.endsWith('.py')).map(n=>'tests/'+n),...fs.readdirSync(path.join(root,'fixtures')).filter(n=>n.endsWith('.json')).map(n=>'fixtures/'+n)])py.FS.writeFile('/app/'+name,fs.readFileSync(path.join(root,name)));
 py.FS.chdir('/app');const report=await py.runPythonAsync(`import sys,json,unittest,io\nsys.path.insert(0,'/app')\nsys.path.insert(0,'/app/tests')\ns=io.StringIO()\nr=unittest.TextTestRunner(stream=s,verbosity=1).run(unittest.defaultTestLoader.discover('/app/tests'))\njson.dumps({'successful':r.wasSuccessful(),'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'log':s.getvalue(),'python':sys.version})`);
 fs.writeFileSync(path.join(root,'qa/pyodide-expanded-tests.json'),report);console.log(report);if(!JSON.parse(report).successful)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
