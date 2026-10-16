#!/usr/bin/env python3
"""Build the separate source-input comparison from independent local code.

Original resources, input requests and normalized programs are not build inputs.
"""
from pathlib import Path
import argparse,json,hashlib,re
ROOT=Path(__file__).resolve().parents[1];WEB=ROOT/'web';RUNTIME=WEB/'mc-interest-runtime'

def outputs():
 manifest=json.loads((RUNTIME/'mc-interest-runtime.json').read_text());assert manifest['format']=='tax-reborn-owned-mc-interest-runtime-v1'
 rows=manifest['files'];paths=[r['path']for r in rows]
 actual={p.relative_to(RUNTIME).as_posix()for p in RUNTIME.rglob('*.py')};actual.update({'raw-interest-authority.json','CS24-runtime-authority.json','CS37-resource-authority.json','source-mc-authority.json'})
 assert len(paths)==188 and len(set(paths))==188 and set(paths)==actual and sum(p.endswith('.py')for p in paths)==184
 for row in rows:
  assert re.fullmatch(r'(?:[A-Za-z_0-9-]+\.(?:py|json)|source_mc/[A-Za-z_0-9]+\.py|interop/(?:__init__|(?:form_core|derived_form|container)/[a-z_0-9]+)\.py)',row['path'])
  data=(RUNTIME/row['path']).read_bytes();row['bytes']=len(data);row['sha256']=hashlib.sha256(data).hexdigest()
 raw=(json.dumps(manifest,indent=2)+'\n').encode();digest=hashlib.sha256(raw).hexdigest()
 source=(RUNTIME/'worker-source.js').read_text();source,count=re.subn(r"const fixedManifestSHA='[0-9a-f]{64}';",lambda _:"const fixedManifestSHA='"+digest+"';",source,count=1);assert count==1
 prefix=(WEB/'tax-worker.js').read_text().split('// Source:',1)[0]
 worker=prefix.rstrip()+'\n\n'+(WEB/'vendor/pyodide/pyodide.js').read_text()+'\n'+source
 offline=json.loads((WEB/'offline-assets.json').read_text());assets=offline if isinstance(offline,list)else offline['assets']
 assets[:]=sorted(set(assets+['source-mc-interest.js']+['mc-interest-runtime/'+p for p in paths]+['mc-interest-runtime/mc-interest-runtime.json','mc-interest-runtime/worker-source.js','mc-interest-runtime/worker.js']))
 return {RUNTIME/'mc-interest-runtime.json':raw,RUNTIME/'worker-source.js':source.encode(),RUNTIME/'worker.js':worker.encode(),WEB/'offline-assets.json':(json.dumps(offline,indent=2)+'\n').encode()}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
 for p,data in outputs().items():
  if args.check:assert p.read_bytes()==data,'Rebuild '+p.name
  else:p.write_bytes(data)
 print('Independent source-input comparison worker verified'if args.check else'Independent source-input comparison worker rebuilt')
