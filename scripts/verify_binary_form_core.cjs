// Execute the independently authored byte reader/writer in the actual WASM
// Python runtime used by the app. This does not run any vendor program.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const vendor = path.join(root, 'web/vendor/pyodide');
const {loadPyodide} = require(path.join(vendor, 'pyodide.js'));

(async () => {
  const py = await loadPyodide({indexURL: vendor + path.sep});
  py.FS.mkdirTree('/app/interop/form_core');
  py.FS.mkdirTree('/app/tests');
  const files = ['interop/__init__.py',
    ...fs.readdirSync(path.join(root, 'interop/form_core'))
      .filter(name => name.endsWith('.py'))
      .map(name => 'interop/form_core/' + name),
    'tests/test_binary_form_core.py'];
  for (const name of files) {
    py.FS.writeFile('/app/' + name, fs.readFileSync(path.join(root, name)));
  }
  py.FS.chdir('/app');
  const result = JSON.parse(await py.runPythonAsync(`
import io, json, sys, unittest
sys.path.insert(0, '/app')
log = io.StringIO()
suite = unittest.defaultTestLoader.discover('/app/tests', pattern='test_binary_form_core.py')
result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
json.dumps({'successful': result.wasSuccessful(), 'tests': result.testsRun,
 'failures': len(result.failures), 'errors': len(result.errors),
 'log': log.getvalue(), 'python': sys.version})
`));
  const receipt = {
    ...result,
    checked_at_utc: new Date().toISOString(),
    runtime: 'real Pyodide WASM Python; eight independent modules',
    input: 'authored single-form core byte buffers, without writer sidecars',
    original_runtime_executions: 0,
    original_saved_tax_fixtures: 0,
    whole_form_compatibility: false,
    whole_tax_compatibility: false,
    included_in_installer: false,
  };
  fs.writeFileSync(path.join(root, 'qa/binary-form-core-pyodide-20261015.json'),
    JSON.stringify(receipt, null, 2) + '\n');
  console.log(JSON.stringify(receipt));
  if (!result.successful) process.exitCode = 1;
})().catch(error => { console.error(error); process.exitCode = 1; });
