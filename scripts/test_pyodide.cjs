const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),vendor=path.join(root,'web/vendor/pyodide');
const {loadPyodide}=require(path.join(vendor,'pyodide.js'));
// HTTP/SQLite server integration requires a host socket and subprocess. Its
// native Python checks are separate from the browser's federal/form checks.
const excludedTests=['test_desktop_origin.py','test_taxml_import.py','test_w2_metadata.py','test_investment_metadata.py','test_income_metadata.py','test_special_dividend_http.py','test_child_income_http.py','test_person_dates_http.py'];
(async()=>{const py=await loadPyodide({indexURL:vendor+path.sep});py.FS.mkdirTree('/app/tests');py.FS.mkdirTree('/app/fixtures');py.FS.mkdirTree('/app/forms');py.FS.mkdirTree('/app/docs');
 for(const name of ['tax_engine.py','tax_special_capital.py','tax_child_income.py','tax_extended.py','tax_credits.py','tax_additional.py','tax_longtail.py','tax_filing.py','forms.py','official_forms.py','privacy_review.py','income_preparation.py','rules_2025.json',...fs.readdirSync(path.join(root,'forms')).filter(n=>/\.(pdf|json)$/.test(n)).map(n=>'forms/'+n),...fs.readdirSync(path.join(root,'tests')).filter(n=>n.endsWith('.py')&&!excludedTests.includes(n)).map(n=>'tests/'+n),...fs.readdirSync(path.join(root,'fixtures')).filter(n=>n.endsWith('.json')).map(n=>'fixtures/'+n)])py.FS.writeFile('/app/'+name,fs.readFileSync(path.join(root,name)));
 py.FS.writeFile('/app/docs/final_validation_20261013.json',fs.readFileSync(path.join(root,'docs/final_validation_20261013.json')));
 py.FS.writeFile('/app/pypdf.whl',fs.readFileSync(path.join(root,'web/vendor/python/pypdf-6.10.0.whl')));await py.runPythonAsync("import sys;sys.path.insert(0,'/app/pypdf.whl')");
 py.FS.chdir('/app');const report=await py.runPythonAsync(`import sys,json,unittest,io\nsys.path.insert(0,'/app')\nsys.path.insert(0,'/app/tests')\ns=io.StringIO()\nr=unittest.TextTestRunner(stream=s,verbosity=1).run(unittest.defaultTestLoader.discover('/app/tests'))\njson.dumps({'successful':r.wasSuccessful(),'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'executed':r.testsRun-len(r.skipped),'log':s.getvalue(),'python':sys.version})`);
 const receipt={...JSON.parse(report),excluded_host_integration_tests:excludedTests,scope:'Federal calculation and form tests in real Pyodide; host HTTP/SQLite integration is checked in native Python.'};
 fs.writeFileSync(path.join(root,'qa/pyodide-expanded-tests.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));if(!receipt.successful)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
