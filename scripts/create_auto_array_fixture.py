"""Owned v5 carriers supply arrays; no hand-entered descriptor profile."""
from pathlib import Path
import base64,hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import create_derived_binary_fixture as derived
import create_binary_fixture as owned
from taxml_wire import read_xprf_resources

def payload(encoded,first,last,limit,byte26,byte27):
    return struct.pack('<H',1)+encoded+struct.pack('<HHHBB',first,last,limit,byte26,byte27)

def fixture(**options):
    request=derived.fixture(**options);profile=request['profile']
    fsid=profile['templates'][0]['formset_id'];carriers=[];replacements={}
    for index,carrier in enumerate(request['carriers']):
        resources=read_xprf_resources(base64.b64decode(carrier['base64']),carrier['sha256'])
        if index==0:
            resources[2000,1]=payload(b'\xff'+b'OWNED_ROWS'.ljust(32,b' '),12,12,10,49,2)
        else:
            values=[b'FW2',fsid.encode(),b'1',b'1']
            resources[18000,3]=struct.pack('<H',4)+b''.join(bytes([len(value)])+value for value in values)
            resources[2001,3]=payload(b'\x06HIDDEN',12,12,25,97,1)
        blob=owned.owned_xprf(resources);digest=hashlib.sha256(blob).hexdigest()
        replacements[carrier['sha256']]=digest
        carriers.append(dict(base64=base64.b64encode(blob).decode(),sha256=digest))
    profile.pop('compiled_arrays')
    profile['format']='tax-reborn-binary-entity-profile-v5'
    profile['registry_order']=[carrier['sha256'] for carrier in carriers]
    for target in profile['templates']:target['carrier_sha256']=replacements[target['carrier_sha256']]
    request['carriers']=carriers
    return request

def build(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);entries={}
    for name,options in [('auto-array-income',{}),('auto-array-used',{'used_array':True}),('auto-array-opaque',{'opaque':True})]:
        request=fixture(**options);source=base64.b64decode(request['base64'])
        encoded=(json.dumps(request,sort_keys=True,indent=2)+'\n').encode('utf-8')
        (destination/(name+'.taxbin')).write_bytes(source)
        (destination/(name+'-request.json')).write_bytes(encoded)
        entries[name]=dict(bytes=len(source),sha256=hashlib.sha256(source).hexdigest(),request_sha256=hashlib.sha256(encoded).hexdigest())
    manifest=dict(vendor_resources_included=False,original_runtime_executions=0,
        current_arrays='actual owned2000/2001 resources through same effective registry',
        manually_enumerated_profile_arrays=False,entries=entries)
    (destination/'auto-array-manifest.json').write_bytes((json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode('utf-8'))
    return manifest

if __name__=='__main__':print(json.dumps(build(ROOT/'fixtures/binary-tax'),indent=2))
