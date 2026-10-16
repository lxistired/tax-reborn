"""Actual-v5 existing one-row OID source projection, no missing-form defaults.

Wire current facts are conditional comparison inputs. This does not execute
native Form.GetTable/Build, GetOrCreateUUID, Load/Fixup/defaults or assignments.
"""
from decimal import Decimal
import hashlib
from interest_snapshot_reference import read_snapshot
from strict_actual_array_interest_reference import exact_source_owner_ids,_raw_header_ids
from strict_bint_row_scope_reference import reject_extra_bint_rows
from current_string_input_reference import current_string_input
from numeric_current_input_reference import StoredCents,current_numeric_input
from interop.derived_form.value_hash_wire_reference import find_value


def read_OID_snapshot(request,*,binary_loader,approved_bank_profile,approved_OID):
    if type(approved_OID)is not dict or set(approved_OID)!={'child_identity','input_fields','selector_fields','target_fields'}:raise ValueError('External exact OID source profile required')
    inputs=approved_OID['input_fields'];boxes=approved_OID['selector_fields'];targets=approved_OID['target_fields']
    if len(inputs)!=14 or len(boxes)!=7 or len(targets)!=6:raise ValueError('All14 typed OID inputs, seven boxes and six current targets required')
    if len({p['reference']for p in inputs})!=14 or len({p['field_id']for p in boxes})!=7 or len({p['reference']for p in targets})!=6:raise ValueError('Unique complete OID field plans required')
    loaded=binary_loader(request['source']);doc,buffers,bound,registry,selected,wire=loaded
    def same_loader(source):
        if source!=request['source']:raise ValueError('Current OID source changed')
        return loaded
    bank=read_snapshot(request,binary_loader=same_loader,approved_profile=approved_bank_profile)
    exact_source_owner_ids(doc,bank['owner_proof']);reject_extra_bint_rows(doc,bound,request['summary_path'],first_row=1)
    sp=tuple(request['summary_path']);fs=doc.formsets[sp[0]];summary=fs.forms[sp[1]];fsid=fs.header.identifier.decode().rstrip(' ')
    def walk(forms,path=()):
        for i,f in enumerate(forms):
            p=path+(i,);yield p,f
            yield from walk(f.children,p)
    all_oid=[(p,f)for p,f in walk(fs.forms)if f.header.identifier.ljust(32,b' ')==b'F1099O'.ljust(32,b' ')]
    if len(all_oid)!=1:raise ValueError('One existing source F1099O required; omitted form is not native blank')
    relative,child=all_oid[0];cp=(sp[0],)+relative
    if len(cp)!=3 or cp[:-1]!=sp or child.header.word7c!=1:raise ValueError('Only one direct existing F1099O copy1 is closed')
    rawid,parent=_raw_header_ids(child)
    if rawid.ljust(32,b' ')!=b'F1099O'.ljust(32,b' ')or parent is None or parent.ljust(32,b' ')!=b'FSCHB'.ljust(32,b' ')or child.header.parent.file_copy!=summary.header.file_copy:
        raise ValueError('Exact same-owner F1099O C4/CB identity and parent U32 filecopy required')
    if tuple(selected.get((fsid,'F1099O'),()))!=tuple(approved_OID['child_identity']):raise ValueError('Approved current OID template identity required')
    factorykey=(fs.header.identifier,child.header.identifier)
    if bound.context.form_factories.get(factorykey)!='value_form'or bound.context.table_factories.get(factorykey)!='value_table':raise ValueError('Explicit caller ValueForm/ValueTable boundary required')
    key=(fs.header.identifier,summary.header.identifier);arrays=[a for block in bound.arrays[key]for a in block if a.identifier.ljust(32,b' ')==b'BOID'.ljust(32,b' ')]
    if len(arrays)!=1 or(arrays[0].first_field,arrays[0].last_field,arrays[0].element_limit,arrays[0].flags)!=(12,20,65520,49):raise ValueError('Exact actual BOID12..20 descriptor required')
    raw_descriptors=[r for block in bank['actual_array_proof']['array_blocks']for r in block['records']if r['identifier']=='BOID']
    if raw_descriptors!=[dict(identifier='BOID',first_field=12,last_field=20,element_limit=65520,flags=49,byte27=0)]:raise ValueError('Exact same-registry BOID raw byte27 descriptor required')
    tables=[t for t in summary.tables if t.identifier.ljust(32,b' ')==b'BOID'.ljust(32,b' ')]
    if len(tables)!=1 or tables[0].last_used_record_index!=1:raise ValueError('One existing BOID saved first-row header required')
    table=tables[0];tw=table.metadata.get('source_wire')
    if type(tw)is not bytes or len(tw)<3 or tw[0]!=0xe1:raise ValueError('Original BOID E1 wire required')
    size=int.from_bytes(tw[1:3],'big')
    if tw[3:3+size]!=b'BOID':raise ValueError('Exact original BOID table ID bytes required')
    entries={e.identifier:e.source_field_index for e in summary.derived_tail.field_map.entries};first=entries.get(b'L1OID'.ljust(32,b' '));last=entries.get(b'PBOID'.ljust(32,b' '))
    if first is None or last is None or first>last or(table.word28,table.word2a)!=(first,last):raise ValueError('Original BOID endpoints must match complete source D2 IDs')
    matches=[]
    for b in bound.bindings.get(sp,()):
        if 12<=b.current_field_index<=20 or first<=b.source_field_index<=last:
            if b.element_index!=1:raise ValueError('Additional stored BOID rows or element0 require native inventory/recovery; even Unused must refuse')
            matches.append((b.current_field_index,b.element_index))
    traces=[]
    def read(plan,element):
        required={'reference','form_id','field_id','ordinal','kind','format','template_attributes'}
        if type(plan)is not dict or set(plan)!=required:raise ValueError('Exact complete current OID field plan required')
        form,path,identity=(child,cp,approved_OID['child_identity'])if plan['form_id']=='F1099O'else(summary,sp,approved_bank_profile['summary_identity'])
        if plan['form_id']not in('F1099O','FSCHB'):raise ValueError('Unknown OID source owner')
        fspec=[f for f in registry.resolve(fsid,plan['form_id'],identity).fields if f.field_id==plan['field_id']]
        if len(fspec)!=1 or tuple(getattr(fspec[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(plan[k]for k in('ordinal','kind','format','template_attributes')):raise ValueError('Current OID metadata differs from approved field')
        fid=plan['field_id'].encode().ljust(32,b' ');es=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
        if len(es)>1:raise ValueError('Ambiguous current OID D2 ID')
        source=es[0].source_field_index if es else None;node=find_value(form.hash_state,source,element)if source is not None else None
        bs=[b for b in bound.bindings.get(path,())if b.field_id==fid and b.element_index==element]
        attrs=0;value=None
        if node is not None:
            if len(bs)!=1:raise ValueError('Stored OID value needs exact full-ID binding')
            b=bs[0]
            if(b.source_field_index,b.current_field_index,b.source_kind,b.source_format,b.fv_attributes)!=(source,plan['ordinal'],plan['kind'],plan['format'],node.specific_attributes)or(node.kind_byte,node.flag10)!=(plan['kind'],plan['format']):raise ValueError('OID source/current kind, format or binding differs')
            if b.native_action not in('preserve','requires_string_or_identity_context','requires_additional_scalar_codec')and not(b.native_action=='drop_empty_storage'and not node.specific_attributes&1):raise ValueError('Unclosed OID native conversion')
            attrs=node.specific_attributes
            if attrs not in(0,1,2,3,8,9,10,11):raise ValueError('Unknown OID source attributes')
            if plan['kind']==11:value=current_numeric_input(StoredCents(node.kind_byte,node.raw,attrs,node.header,node.flag10,node.flag11,node.exponent_byte))
            elif plan['kind']==7:value=current_string_input(node,table=form.string_table,table_id=form.table_id)
            elif plan['kind']in(3,10):
                if attrs&1:
                    if node.header or node.flag10 or node.flag11:raise ValueError('Finite normal OID scalar header required')
                    if plan['kind']==3:
                        if node.raw not in(0,1):raise ValueError('Canonical current OID checkbox required')
                        value=bool(node.raw)
                    else:
                        if not 1<=node.raw<=65520:raise ValueError('Actual current positive HCOPYNUM required; Header.word7c is separate')
                        value=Decimal(node.raw)
            else:raise ValueError('Unknown OID current scalar kind')
        elif bs:raise ValueError('OID binding points at missing hash node')
        traces.append(dict(reference=plan['reference'],form_id=plan['form_id'],field_id=plan['field_id'],document_path=list(path),
            source_ordinal=source,current_ordinal=plan['ordinal'],element_index=element,present=bool(attrs&1),FV_attributes=attrs,
            source_storage='D2_absent'if source is None else'hash_node_absent'if node is None else'stored',
            value_hex=value.hex()if type(value)is bytes else None,value_decimal=format(value,'f')if type(value)is Decimal else None,
            value_boolean=value if type(value)is bool else None,packed_exponent=node.exponent_byte if node else None))
        return value,attrs
    childkey='owned-OID-source-copy:'+':'.join(map(str,cp));rowkey='owned-OID-summary-row:1';facts={4274:{rowkey:Decimal(1)}}
    for plan in inputs:
        value,attrs=read(plan,0);facts[plan['reference']]={childkey:value}
    selected_values=[];boxstates=[]
    for plan in boxes:
        if type(plan.get('literal'))is not str or not plan['literal']or not plan['literal'].isascii()or '\0'in plan['literal']or len(plan['literal'])>128:raise ValueError('Original finite OID ValueMapping literal required')
        field={k:v for k,v in plan.items()if k!='literal'};value,attrs=read(field,0)
        if plan['kind']!=3 or plan['format']or plan['template_attributes']!=132:raise ValueError('Exact OID kind3 checkbox metadata required')
        if value is True:selected_values.append(plan['literal'])
        boxstates.append(dict(field_id=plan['field_id'],present=bool(attrs&1),rendered_nonempty=value is True,Used_zero_is_present=bool(attrs&1 and value is False)))
    if len(selected_values)>1:raise ValueError('Conflicting OID selector mappings require unclosed duplicate-key protocol')
    facts[boxes[0]['reference']]={childkey:selected_values[0]if selected_values else None}
    priors={}
    for plan in targets:
        field={k:v for k,v in plan.items()if k!='assign_statement'};element=0 if plan['form_id']=='F1099O'else 1;value,attrs=read(field,element)
        priors[plan['reference']]={childkey if element==0 else rowkey:dict(value=value,computed=bool(attrs&2),overridden=bool(attrs&8),itemized=False,
            assign_statement=plan['assign_statement'])}
    return dict(source_sha256=hashlib.sha256(wire).hexdigest(),typed_inputs=facts,current_assignment_storage=priors,current_field_trace=traces,
        selector_states=boxstates,BOID_saved_row_scope=dict(saved_last_row=1,all_bound_BOID_nodes_examined=True,observed_fields=matches,flags49_preserved=True),
        child_path=list(cp),summary_path=list(sp),runtime_copy_number=child.header.word7c,document_file_copy=child.header.file_copy,
        owned_source_label=childkey,owned_summary_row_label=rowkey,Header_word7c_is_not_HCOPYNUM=True,
        assignments_executed=False,complete172_OID_graph_executed=False,source_complete14873=False,
        native_record_inventory_verified=False,owned_labels_are_native_UUIDs=False,comparison_only=True,writeback_allowed=False,
        original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
