#!/usr/bin/env python3
"""Build the bounded independent source-value report runtime, without source data."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];WEB=ROOT/'web'
PYTHON_FILES=('source_mc_input.py',
 'source_mc/MC_input_query_reference.py','source_mc/MC_leaf_selection_reference.py','source_mc/MC_path_UUID_reference.py','source_mc/__init__.py',
 'source_mc/actual_summary_arrays_reference.py','source_mc/compiled_identity_runtime_adapter.py','source_mc/current_mapping_numeric_reference.py',
 'source_mc/current_numeric_leaf_reference.py','source_mc/current_string_input_reference.py','source_mc/finite_interest_prefix_reference.py',
 'source_mc/form_uuid_initialization_reference.py','source_mc/interest_snapshot_reference.py','source_mc/normal_Mef_components_reference.py',
 'source_mc/normal_query_address_reference.py','source_mc/numeric_current_input_reference.py','source_mc/owned_MC_nodes_reference.py',
 'source_mc/owned_current_MC_value_reference.py','source_mc/postcopy_cache_reference.py','source_mc/raw_numeric_input_reference.py',
 'source_mc/raw_tke_nodes_reference.py','source_mc/raw_tke_xml_reference.py','source_mc/source_child_form_uuid_reference.py',
 'source_mc/source_current_supplier.py','source_mc/strict_actual_array_interest_reference.py','source_mc/strict_bint_row_scope_reference.py',
 'source_mc/summary_child_current_reference.py')
AUTHORITY='source-mc-authority.json'
AUTHORITY_SHA='ca53d158123e9aba70f9e44a32eb2a8ff1ba795ea9039eba7afcd1b00bed841b'
assert len(PYTHON_FILES)==27 and len(set(PYTHON_FILES))==27
assert set(p.relative_to(WEB).as_posix()for p in(WEB/'source_mc').rglob('*.py'))==set(PYTHON_FILES[1:])
rows=[]
for name in(*PYTHON_FILES,AUTHORITY):
 raw=(WEB/name).read_bytes()
 if name.endswith('.py'):
  compile(raw,name,'exec')
  if b'/Users/'in raw or b'bound.private.raw'in raw or b'rea-wave'in raw or b'private.asm'in raw:raise ValueError('Private audit dependency in '+name)
 rows.append({'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
assert rows[-1]['sha256']==AUTHORITY_SHA
manifest={'format':'tax-reborn-source-mc-runtime-v1','command':'source_mc_input_diagnose','python_module_limit':32,'modules':rows,
 'original_resource_payloads_bundled':False,'native_GetMultiCopyInputValue_executed':False,'writeback_allowed':False}
raw=(json.dumps(manifest,indent=2)+'\n').encode();(WEB/'source-mc-runtime.json').write_bytes(raw)
worker=WEB/'tax-worker-source.js';text=worker.read_text()
text,count=re.subn(r"const sourceMCRuntimeSHA='(?:[0-9a-f]{64}|BUILD_SOURCE_MC_MANIFEST)';",lambda m:"const sourceMCRuntimeSHA='"+hashlib.sha256(raw).hexdigest()+"';",text)
if count!=1:raise ValueError('Expected one fixed source-MC manifest identity')
worker.write_text(text)
assets=WEB/'offline-assets.json';data=json.loads(assets.read_text());values=data if isinstance(data,list)else data['assets']
values[:]=sorted(set(values+list(PYTHON_FILES)+[AUTHORITY,'source-mc-runtime.json','source-mc-diagnostics.js']))
assets.write_text(json.dumps(data,indent=2)+'\n')
print('Source-value report runtime:',len(PYTHON_FILES),'independent Python modules;',sum(x['bytes']for x in rows),'bytes')
