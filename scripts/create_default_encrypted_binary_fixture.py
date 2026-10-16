"""Create an owned default-encrypted archive around the public binary-tax fixture.
The keys are synthetic test material from public-test-compatibility.json."""
from __future__ import annotations
import base64, io, json, zipfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'web/samples/default-encrypted'
REQ=json.loads((ROOT/'web/samples/binary-tax/auto-array-income-request.json').read_text())
CFG=json.loads((OUT/'public-test-compatibility.json').read_text())
def pair(branch,role):
 d=CFG[branch][role];return base64.b64decode(d['key_base64']),base64.b64decode(d['iv_base64'])
def encrypt(raw,key,iv):
 pad=16-len(raw)%16;raw+=bytes([pad])*pad
 e=Cipher(algorithms.AES(key),modes.CBC(iv)).encryptor();return e.update(raw)+e.finalize()
def b64(raw):return base64.b64encode(raw).decode()
source=base64.b64decode(REQ['base64'])
profile=json.dumps(REQ['profile'],sort_keys=True,separators=(',',':')).encode()
carriers=[base64.b64decode(x['base64']) for x in REQ['carriers']]
manifest=("<?xml version=\"1.0\" encoding=\"UTF-8\"?><Manifest xmlns=\"http://schemas.intuit.com/LocalCfpContainer.xsd\"><documents>"
  "<document><entityType>/owned/binary-taxml</entityType><entityKey>main.entity</entityKey></document>"
  "<document><entityType>/owned/wire-profile</entityType><entityKey>profile.entity</entityKey></document>"
  "<document><entityType>/owned/registry</entityType><entityKey>carrier-0.entity</entityKey></document>"
  "<document><entityType>/owned/registry</entityType><entityKey>carrier-1.entity</entityKey></document>"
  "</documents></Manifest>").encode()
mk,mi=pair('current','manifest');dk,di=pair('current','member')
with zipfile.ZipFile(OUT/'synthetic-default-binary-array.tax','w',compression=zipfile.ZIP_STORED) as z:
 z.writestr('manifest.xml',encrypt(manifest,mk,mi));z.writestr('main.entity',encrypt(source,dk,di));z.writestr('profile.entity',encrypt(profile,dk,di));z.writestr('carrier-0.entity',encrypt(carriers[0],dk,di));z.writestr('carrier-1.entity',encrypt(carriers[1],dk,di));z.writestr('retained.opaque',b'owned retained opaque ciphertext')
(OUT/'synthetic-default-binary-profile.json').write_text(json.dumps(REQ['profile'],sort_keys=True,indent=2)+'\n')
for i,raw in enumerate(carriers): (OUT/f'synthetic-default-binary-carrier-{i}.xprf').write_bytes(raw)
print('archive',OUT/'synthetic-default-binary-array.tax','source_bytes',len(source),'profile_bytes',len(profile),'carriers',[len(x) for x in carriers])
