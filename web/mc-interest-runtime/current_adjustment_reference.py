"""Finite current kind3 boxes -> selected original ValueMapping string literal.

This supplies the adjustment-code leaf only. It does not compute an adjustment
amount, resolve native row UUIDs, create records, or update parent totals.
"""
import hashlib
from interop.derived_form.value_hash_wire_reference import find_value
from interest_snapshot_reference import read_snapshot

FIELDS=('TBXN','TBXA','TBXO','TBXH','TBXB','TBXR','TBXU','TBXT')


def select_current_boxes(states,*,approved_entries):
    if type(states)is not dict or set(states)!=set(FIELDS):
        raise ValueError('All eight explicit current adjustment boxes required')
    if type(approved_entries)is not list or len(approved_entries)!=8 or any(type(r)is not dict for r in approved_entries)or {r.get('field_id')for r in approved_entries}!=set(FIELDS):
        raise ValueError('Trusted eight-entry ValueMapping literal profile required')
    selected=[];trace=[]
    for entry in approved_entries:
        value=entry['literal']
        if type(value)is not str or not value or not value.isascii()or '\0'in value or len(value)>128:
            raise ValueError('Exact finite original ValueMapping literal required')
        name=entry['field_id'];row=states[name]
        present=False;checked=False
        if row is not None:
            if type(row)is not dict or set(row)!={'native_kind','raw64','FV_attributes','value_header','format_flag10','flag11'}:
                raise ValueError('Explicit finite current checkbox storage required')
            if row['native_kind']!=3 or type(row['FV_attributes'])is not int or row['FV_attributes']not in(0,1,2,3,8,9,10,11):
                raise ValueError('Current kind3 and ordinary Used/Computed/Override masks required')
            if type(row['raw64'])is not int or not 0<=row['raw64']<1<<64 or any(type(row[k])is not int or not 0<=row[k]<=255 for k in('value_header','format_flag10','flag11')):
                raise ValueError('Exact raw U64 and unsigned header bytes required')
            present=bool(row['FV_attributes']&1)
            if present:
                if type(row['raw64'])is not int or row['raw64']not in(0,1)or any(row[k]for k in('value_header','format_flag10','flag11')):
                    raise ValueError('Used current checkbox requires canonical0/1 and the finite normal header/format profile')
                checked=row['raw64']==1
        trace.append(dict(field_id=name,present=present,rendered_nonempty=checked,
            selected_literal=value if checked else None,
            Used_zero_is_present_but_rendered_empty=present and not checked))
        if checked:selected.append(value)
    if len(selected)>1:raise ValueError('Conflicting current adjustment literals require the unclosed duplicate-key mapping protocol')
    return dict(value=selected[0]if selected else None,states=trace,
        source_Used_zero_is_not_source_absent=True,native_UUID_mapping_executed=False)


def read_adjustment_selector(request,*,binary_loader,approved_profile,approved_entries):
    snapshot=read_snapshot(request,binary_loader=binary_loader,approved_profile=approved_profile)
    doc,buffers,bound,registry,selected,source=binary_loader(request['source'])
    proof=snapshot['owner_proof'];digest=hashlib.sha256(source).hexdigest()
    if digest!=proof['source_sha256']:raise ValueError('Source changed between current typed reads')
    path=proof['child_path'];form=doc.formsets[path[0]].forms[path[1]].children[path[2]];fsid=proof['source_formset_id']
    template=registry.resolve(fsid,'F1099I',selected[fsid,'F1099I']);states={};traces=[]
    if type(approved_entries)is not list or len(approved_entries)!=8:raise ValueError('Complete trusted adjustment metadata required')
    for plan in approved_entries:
        if type(plan)is not dict or set(plan)!={'field_id','ordinal','kind','format','template_attributes','literal'}:
            raise ValueError('Exact complete adjustment source metadata required')
        fields=[f for f in template.fields if f.field_id==plan['field_id']]
        if len(fields)!=1 or(fields[0].ordinal,fields[0].kind,fields[0].format,fields[0].attributes)!=(plan['ordinal'],3,0,132)or(plan['kind'],plan['format'],plan['template_attributes'])!=(3,0,132):
            raise ValueError('Selected current adjustment metadata differs from approved original fields')
        field_id=plan['field_id'].encode().ljust(32,b' ')
        entries=[e for e in form.derived_tail.field_map.entries if e.identifier==field_id]
        if len(entries)>1:raise ValueError('Ambiguous full-ID source adjustment field')
        source_ordinal=entries[0].source_field_index if entries else None
        node=find_value(form.hash_state,source_ordinal,0)if source_ordinal is not None else None
        trace=dict(field_id=plan['field_id'],source_ordinal=source_ordinal,current_ordinal=plan['ordinal'],
            source_storage='D2_absent'if source_ordinal is None else'hash_node_absent'if node is None else'stored')
        state=None
        if node is not None:
            matches=[b for b in bound.bindings.get(tuple(path),())if b.field_id==field_id and b.element_index==0]
            if len(matches)!=1 or(matches[0].source_field_index,matches[0].current_field_index)!=(source_ordinal,plan['ordinal']):
                raise ValueError('Current adjustment full-ID source binding differs')
            binding=matches[0]
            if(node.kind_byte,node.flag10,binding.source_kind,binding.source_format)!=(3,0,3,0):
                raise ValueError('Source checkbox kind/format conversion is unclosed')
            if binding.native_action not in('preserve','requires_additional_scalar_codec')and not(binding.native_action=='drop_empty_storage'and not node.specific_attributes&1):
                raise ValueError('Unclosed native adjustment conversion or array action')
            state=dict(native_kind=node.kind_byte,raw64=node.raw,FV_attributes=node.specific_attributes,
                value_header=node.header,format_flag10=node.flag10,flag11=node.flag11)
            trace.update(state)
        states[plan['field_id']]=state;traces.append(trace)
    result=select_current_boxes(states,approved_entries=approved_entries)
    return dict(reference=9443,source_sha256=digest,owner_proof=proof,current_adjustment_trace=traces,
        input_value={snapshot['source_label']:result['value']},selector=result,
        current_source_values_are_loaded=True,owned_labels_are_native_UUIDs=False,
        native_record_inventory_verified=False,native_mapping_UUID_resolution_executed=False,
        complete_adjustment_or_parent_total=False,comparison_only=True,can_commit_to_source=False,
        original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
