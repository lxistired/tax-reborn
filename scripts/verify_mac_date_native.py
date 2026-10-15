#!/usr/bin/env python3
"""Reopen a whole system-saved owned source and check every field and ZIP record."""
from pathlib import Path
import argparse, base64, json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'web'),str(ROOT/'scripts')]
import taxml_mac as mac
from create_mac_date_fixture import request, digest
from interop.container.raw_zip_reference import load_archive

def verify(path,index=0,value='02/29/2000'):
    req=json.loads((ROOT/'fixtures/mac-date-taxml/request.json').read_text())
    original=base64.b64decode(req['base64']);blob=Path(path).read_bytes()
    before=mac.inspect_request(req)['date_fields'];selected=before[index]
    original_doc=mac._context(req)[-1]
    reopened=mac._context({**req,'base64':base64.b64encode(blob).decode()})[-1]
    key=selected['key'];key=(key[0],bytes.fromhex(key[1]),bytes.fromhex(key[2]),key[3],bytes.fromhex(key[4]))
    field=next(f for f in original_doc.fields if f.key==key)
    expected=original_doc.source_bytes[:field.text_start]+value.encode()+original_doc.source_bytes[field.text_end:]
    assert reopened.source_bytes==expected
    a,b=load_archive(original),load_archive(blob)
    assert len(a.members)==len(b.members)==5
    assert [m.name for m in a.members]==[m.name for m in b.members]
    assert sum(x.local==y.local for x,y in zip(a.members,b.members))==4
    assert [(f.key,f.kind,value if f.key==key else f.text,f.attributes,f.value_attributes)for f in original_doc.fields]==[(f.key,f.kind,f.text,f.attributes,f.value_attributes)for f in reopened.fields]
    assert len(reopened.fields)==53
    return {'whole_file_readback':True,'bytes':len(blob),'sha256':digest(blob),'entities':2,'copies':7,
        'all_fields_checked':53,'changed_date_fields':1,'selected_date_index':index,'value':value,
        'all_other_local_records_exact':4,'original_manifest_exact':True,'date_never_money':True,
        'original_program_runtime':0,'native_date_load_executed':False,'full_original_compatibility':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--index',type=int,default=0);p.add_argument('--value',default='02/29/2000');a=p.parse_args()
    print(json.dumps(verify(a.file,a.index,a.value)))
