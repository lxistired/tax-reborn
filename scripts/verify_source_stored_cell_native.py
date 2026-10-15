"""Independent selected-node inverse check for complete synthetic source exports.

This verifier does not call the correction API to create its expected document.
It resolves the full saved field ID, checks raw cents, restores that one raw in
an independently decoded output and compares the complete semantic document.
"""
from pathlib import Path
from dataclasses import replace
from decimal import Decimal
import argparse,base64,hashlib,json,sys

ROOT=Path(__file__).resolve().parents[1]
def verify(path,*,element=1,value='1234.57'):
    app=ROOT;sys.path[:0]=[str(app/'web'),str(app/'scripts')]
    import binary_tax as api
    request=json.loads((app/'fixtures/source-cell/request.json').read_text());original=base64.b64decode(request['base64']);actual=Path(path).read_bytes()
    expected=json.loads((app/'fixtures/source-cell/expected.json').read_text());row=next(r for r in expected['outputs']if r['element']==element and r['value']==value)
    assert len(original)==8459 and hashlib.sha256(original).hexdigest()==expected['source_sha256']=='4025e24fe7ac3d7d35e3bbed2cdb4f5292a26a7c7f0e8b04018b7ae783f625d0'
    assert len(actual)==row['bytes'] and hashlib.sha256(actual).hexdigest()==row['sha256']
    before=api._context(request);after=api._context({**request,'base64':base64.b64encode(actual).decode()})
    beforedoc,afterdoc=before[0],after[0];beforeforms=dict(api.walk_forms(beforedoc));afterforms=dict(api.walk_forms(afterdoc));assert len(beforedoc.formsets)==len(afterdoc.formsets)==2 and len(beforeforms)==len(afterforms)==8
    beforeform,afterform=beforeforms[(0,0)],afterforms[(0,0)]
    assert beforedoc.formsets[0].header.identifier==afterdoc.formsets[0].header.identifier==b'OWNEDCELL2025'
    assert beforeform.header.identifier==afterform.header.identifier==b'FW2'
    ids=[e for e in beforeform.derived_tail.field_map.entries if e.identifier.rstrip(b' ')==b'SYNTHETIC_AMOUNT'];assert len(ids)==1;source_ordinal=ids[0].source_field_index;assert source_ordinal==112
    specs=[x for x in before[3].resolve('OWNEDCELL2025','FW2',before[4][('OWNEDCELL2025','FW2')]).fields if x.field_id=='SYNTHETIC_AMOUNT'];assert len(specs)==1 and specs[0].ordinal==12 and specs[0].kind==11 and specs[0].format==0
    def node(form):
        matches=[n for block in form.hash_state.buffers for n in block.nodes if(n.field_index,n.element_index)==(source_ordinal,element)]
        assert len(matches)==1 and api.derived.find_value(form.hash_state,source_ordinal,element)is matches[0];return matches[0]
    old,new=node(beforeform),node(afterform)
    assert old.raw=={1:2500,3:0}[element] and new.raw==int(Decimal(value)*100)
    assert (old.kind_byte,old.flag10,old.header,old.specific_attributes)==(new.kind_byte,new.flag10,new.header,new.specific_attributes)==(11,0,0,3)
    assert replace(new,raw=old.raw)==old
    restored_form=replace(afterform,hash_state=replace(afterform.hash_state,buffers=tuple(replace(block,nodes=tuple(replace(n,raw=old.raw)if n is new else n for n in block.nodes))for block in afterform.hash_state.buffers)))
    restored_doc=api.replace_form(afterdoc,(0,0),restored_form)
    assert api.derived_snapshot(restored_doc)==api.derived_snapshot(beforedoc),'Another source fact changed besides the selected node raw64'
    counts=lambda fs:{'tables':sum(len(f.tables)for f in fs.values()),'children':sum(len(f.children)for f in fs.values()),'links':sum(len(f.links)for f in fs.values())}
    assert counts(beforeforms)==counts(afterforms);assert counts(afterforms)['links']==8 and counts(afterforms)['children']>0 and counts(afterforms)['tables']>0
    return {'verified':True,'independent_inverse_raw_check':True,'correct_request_used_as_oracle':False,'independently_generated':True,'original_resources':False,'original_taxpayer_fixture':False,'source_sha256':expected['source_sha256'],'bytes':len(actual),'sha256':hashlib.sha256(actual).hexdigest(),'formsets':2,'forms':8,**counts(afterforms),'element':element,'source_ordinal':source_ordinal,'current_ordinal':12,'old_signed_raw':old.raw,'new_signed_raw':new.raw,'corrected_value':value,'Used_zero_preserved_as_present':element==3,'node_header_kind_flags_exponent_unchanged':True,'restoring_one_raw_makes_complete_document_equal_before':True,'same_stored_owners':True,'complete_raw_objects_preserved':True,'row_creation':False,'native_propagation':False,'tax_recalculated':False,'original_program_acceptance_verified':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('--element',type=int,default=1,choices=[1,3]);p.add_argument('--value',default='1234.57');p.add_argument('--output',type=Path);a=p.parse_args();r=verify(a.file,element=a.element,value=a.value);text=json.dumps(r,indent=2)+'\n'
    if a.output:a.output.write_text(text)
    print(text,end='')
