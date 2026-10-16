#!/usr/bin/env python3
"""Own explicit controller/null profiles, dec1 fields and complete ZIPs.

Reuses only the independently authored public Mac fixture grammar and clear
container. No original vendor resource, binary, saved return or runtime is read.
"""
from pathlib import Path
import argparse,base64,hashlib,json,re,struct,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'web'),str(ROOT/'scripts')]
import create_mac_taxml_fixture as old
PROFILE='tax-reborn-taxml-native-mac-profile-v2'
FIELD='DECIMAL'
DEST=ROOT/'fixtures/mac-scalar-taxml'
def digest(data):return hashlib.sha256(data).hexdigest()
def resource_map():
    resources=old.resource_map();payload=resources[1900,2]
    resources[1900,2]=struct.pack('<H',9)+payload[2:]+b'\xff'+FIELD.encode().ljust(32,b' ')+struct.pack('<BBI',13,0,0)
    resources[2310,2]=old.mapping_list('FW2',old.FIELDS['FW2']+(FIELD,))
    return resources
def make_carrier():
    resources=resource_map();at=16+12*len(resources);directory=[];records=[]
    for (kind,rid),payload in resources.items():
        record=struct.pack('<IIH',len(payload)+10,len(payload),0)+payload
        directory.append(struct.pack('<HHII',kind,rid,at,len(record)));records.append(record);at+=len(record)
    return b'XPRF\0\1\x10\x0c\x0a\0\0\0'+struct.pack('<I',len(resources))+b''.join(directory)+b''.join(records)
def make_xml(filter_profile='controller_filter'):
    if filter_profile not in ('null_filter','controller_filter'):raise ValueError('Explicit selected profile required')
    xml=old.make_xml();values=iter(('0.7','1.2','-0.3'))
    def extra(match):
        return ('    <DECIMAL tpsType="dec1" tpsSubType="default" cidForm="OwnedFW2" cidField="Owned_DECIMAL"><td:value>'+next(values)+'</td:value></DECIMAL>\n').encode()+match[0]
    xml=re.sub(b'   </FW2>',extra,xml)
    if filter_profile=='controller_filter':
        for form,fields in old.FIELDS.items():
            for ordinal,field in enumerate(fields+(FIELD,)if form=='FW2'else fields,1):
                xml=xml.replace(('<'+field+' ').encode(),('<'+field+' field="'+str(ordinal)+'" elem="0" ').encode())
    return xml
def request(*,filter_profile='controller_filter',plaintext=False,blocked=False,xml=None):
    xml=make_xml(filter_profile)if xml is None else xml
    req=old.request(plaintext=plaintext,xml=xml,blocked=blocked);carrier=make_carrier();sha=digest(carrier)
    req['profile'].update(format=PROFILE,filter_profile=filter_profile,registry_order=[sha])
    req['carriers']=[{'base64':base64.b64encode(carrier).decode(),'sha256':sha}]
    return req
def build(destination=DEST):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    req=request();blocked=request(blocked=True);null=request(filter_profile='null_filter')
    files={'owned-mac-scalar.xprf':make_carrier(),'owned-mac-scalar.xml':make_xml(),'owned-mac-scalar.zip':base64.b64decode(req['base64']),
        'owned-mac-scalar-blocked.zip':base64.b64decode(blocked['base64'])}
    for name,data in files.items():(destination/name).write_bytes(data)
    for name,value in [('request.json',req),('null-request.json',null),('blocked-request.json',blocked),('plaintext-request.json',request(plaintext=True))]:
        (destination/name).write_bytes((json.dumps(value,indent=2,sort_keys=True)+'\n').encode('utf-8'))
    (destination/'profile.json').write_bytes((json.dumps(req['profile'],indent=2,sort_keys=True)+'\n').encode('utf-8'))
    manifest={'format':'tax-reborn-owned-mac-decimal-fixture-v1','vendor_bytes_included':False,'original_runtime_executions':0,
        'entities':2,'form_copies':7,'scalar_fields':3,'number_kind':'decimal_coefficient','fraction_digits':1,
        'native_factory_acceptance':False,'profile_mode':'Explicit controller_filter; separate explicit null_filter source',
        'files':{name:{'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())}for p in sorted(destination.iterdir())if p.is_file()and (name:=p.name)not in('manifest.json','README.md')}}
    (destination/'manifest.json').write_bytes((json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode('utf-8'));return manifest
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,default=DEST)
    print(json.dumps(build(parser.parse_args().destination)))
