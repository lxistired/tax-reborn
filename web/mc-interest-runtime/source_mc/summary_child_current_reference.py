"""Finite source-D2 child owner and current amount read; no UUID fabrication.

The caller injects a strict binary loader and trusted metadata identities. No
files, native objects, factories, UUID generation, queue or writes are executed.
This selected branch requires a root summary and one direct existing child.
"""
from decimal import Decimal
import hashlib
from interop.form_core.hash_structure_reference import validate_document_hashes
from interop.derived_form.value_hash_wire_reference import find_value
from .actual_summary_arrays_reference import verify_summary_arrays


def _id(value):
    if type(value) is not bytes or not value.rstrip(b' ') or len(value)>32:
        raise ValueError('Explicit native identifier bytes required')
    return value.rstrip(b' ').upper()


def _forms(forms,prefix):
    for i,form in enumerate(forms):
        path=prefix+(i,)
        yield path,form
        yield from _forms(form.children,path)


def read_request(request, *, binary_loader, approved_metadata):
    keys={'source','expected_source_sha256','summary_path','row_number','field_id','need_native_row_uuid'}
    if type(request) is not dict or set(request)!=keys:
        raise ValueError('Exact source summary child read request required')
    if request['need_native_row_uuid'] is not False:
        raise ValueError('Runtime record UUID type14A is not established by source document; form UUID is not row UUID')
    if request['source'].get('profile',{}).get('format')!='tax-reborn-binary-entity-profile-v5':
        raise ValueError('This source-ID view requires v5 actual effective array context')
    if type(approved_metadata) is not dict or set(approved_metadata)!={'summary_identity','child_identity','fields','array_blocks'}:
        raise ValueError('Trusted external metadata identities required; never uploaded claims')
    field_id=request['field_id']
    if field_id not in approved_metadata['fields']:
        raise ValueError('Select a source-reviewed field from this narrow metadata profile')
    spec=approved_metadata['fields'][field_id]
    if type(request['row_number']) is not int or not 1<=request['row_number']<=65520:
        raise ValueError('Ordinary nonzero native BINT row number required')
    path=request['summary_path']
    if type(path) is not list or len(path)!=2 or any(type(i) is not int or i<0 for i in path):
        raise ValueError('One root summary path is required; nested summary disambiguation is not modeled')
    doc,buffers,bound,registry,selected,source=binary_loader(request['source'])
    source_hash=hashlib.sha256(source).hexdigest()
    if source_hash!=request['expected_source_sha256']:
        raise ValueError('Source changed after review')
    hash_proof=validate_document_hashes(doc)
    fsindex,summary_index=path
    try:formset=doc.formsets[fsindex];summary=formset.forms[summary_index]
    except IndexError as error:raise ValueError('Summary path is absent') from error
    if _id(summary.header.identifier)!=b'FSCHB' or summary.header.parent is not None:
        raise ValueError('This finite branch requires the existing root FSCHB owner')
    fsid=_id(formset.header.identifier).decode()
    if selected.get((fsid,'FSCHB'))!=tuple(approved_metadata['summary_identity']):
        raise ValueError('Summary metadata identity differs from trusted selection')
    candidates=[(p,f)for p,f in _forms(formset.forms,(fsindex,))
                if _id(f.header.identifier)==b'F1099I' and f.header.word7c==request['row_number']]
    if len(candidates)!=1:
        raise ValueError('One exact same-FormSet child ID/runtime-copy match required; no missing or ambiguous inventory')
    child_path,child=candidates[0]
    if child_path[:-1]!=tuple(path) or len(child_path)!=3:
        raise ValueError('Only the existing immediate summary child branch is closed')
    parent=child.header.parent
    if parent is None or _id(parent.identifier)!=b'FSCHB' or parent.file_copy!=summary.header.file_copy:
        raise ValueError('Child source parent descriptor does not resolve to this summary owner')
    if selected.get((fsid,'F1099I'))!=tuple(approved_metadata['child_identity']):
        raise ValueError('Child metadata identity differs from trusted selection')
    template=registry.resolve(fsid,'F1099I',selected[fsid,'F1099I'])
    declared=[field for field in template.fields if field.field_id==field_id]
    if len(declared)!=1 or (declared[0].ordinal,declared[0].kind,declared[0].format,declared[0].attributes)!=tuple(spec):
        raise ValueError('Complete selected field metadata differs from source-reviewed facts')
    # Parent table selection is explicit and bound separately from scalar FV.
    tables=[table for table in summary.tables if _id(table.identifier)==b'BINT']
    if len(tables)!=1:
        raise ValueError('One existing BINT source table required')
    array_proof=verify_summary_arrays(bound,registry,formset_id=fsid,approved_blocks=approved_metadata['array_blocks'])
    summary_template=registry.resolve(fsid,'FSCHB',selected[fsid,'FSCHB'])
    endpoints=[]
    for ordinal in(4,11):
        matches=[f for f in summary_template.fields if f.ordinal==ordinal]
        if len(matches)!=1:raise ValueError('Summary metadata endpoint is absent')
        ids=[e.source_field_index for e in summary.derived_tail.field_map.entries if _id(e.identifier)==matches[0].field_id.encode()]
        if len(ids)!=1:raise ValueError('Summary source D2 endpoint is absent or ambiguous')
        endpoints.append(ids[0])
    if (tables[0].word28,tables[0].word2a)!=tuple(endpoints):
        raise ValueError('Stored BINT table field endpoints differ from source/full-ID mapping')
    tail=child.derived_tail
    entries=[entry for entry in tail.field_map.entries if _id(entry.identifier)==field_id.encode()]
    if len(entries)>1:raise ValueError('Ambiguous source D2 identity')
    source_ordinal=entries[0].source_field_index if entries else None
    node=find_value(child.hash_state,source_ordinal,0) if source_ordinal is not None else None
    trace={'source_ordinal':source_ordinal,'current_ordinal':declared[0].ordinal,'field_id':field_id}
    amount=None;present=False
    if node is not None:
        trace.update(kind=node.kind_byte,raw64=str(node.raw),packed_exponent=node.exponent_byte,
                     value_header=node.header,FV_attributes=node.specific_attributes,format_flag10=node.flag10,uninterpreted_flag11=node.flag11)
        if node.kind_byte!=11 or node.specific_attributes not in(0,1,2,3,8,9,10,11):
            raise ValueError('Only actual kind11 and selected ordinary FV masks are modeled')
        present=bool(node.specific_attributes&1)
        if present:
            if node.header or node.flag10 or node.flag11:
                raise ValueError('Normal current-value header/format profile required')
            coefficient=node.raw if node.raw<1<<63 else node.raw-(1<<64)
            if abs(coefficient)>10**11:raise ValueError('Selected finite cents magnitude exceeded')
            amount=format(Decimal(coefficient).scaleb(-2),'f')
    return {'source_sha256':source_hash,'summary_path':path,'child_path':list(child_path),
        'source_formset_id':fsid,'summary_file_copy_U32':summary.header.file_copy,
        'child_file_copy_U32':child.header.file_copy,'child_runtime_copy_number_U16':child.header.word7c,
        'resolved_parent_runtime_copy_number_U16':parent.word7c,
        'child_source_header_wire_sha256':hashlib.sha256(child.metadata['source_header_wire']).hexdigest(),
        'row_number':request['row_number'],'field':trace,'present':present,'amount':amount,
        'hash_structure_validation':hash_proof,'source_owner_selection_verified_in_finite_branch':True,
        'actual_array_proof':array_proof,
        'row_UUID':None,'row_UUID_verified':False,'native_RuntimeRecordUUID_lookup_or_generation':False,
        'group0_FormUUID_is_not_row_UUID':True,'native_active_copy_inventory_verified':False,
        'native_GetSummarizedForm_executed':False,'native_load_Fixup_events_executed':False,
        'source_metadata_origin_authenticated':False,'comparison_only':True,'can_commit_to_source':False,
        'scope':'Exact root FSCHB + unique direct F1099I/runtime-copy selected from current decoded source; UUID path and other parent disambiguation remain unimplemented'}
