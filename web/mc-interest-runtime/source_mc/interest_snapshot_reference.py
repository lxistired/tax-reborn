"""Current validated source -> one ordinary direct-child interest graph row.

This is a comparison projection of existing wire values. It does not execute
native table initialization, UUID resolution, factories, Fixup, queues or writes.
All sixteen current child inputs are typed; CString bytes are used only for
IsNotBlank. No final Schedule B total or parent tax amount is asserted.
"""
from decimal import Decimal
import hashlib
from .numeric_current_input_reference import StoredCents,current_numeric_input
from .summary_child_current_reference import read_request
from interop.derived_form.value_hash_wire_reference import find_value
from .finite_interest_prefix_reference import Prefix
from .current_string_input_reference import current_string_input


def read_snapshot(request,*,binary_loader,approved_profile):
    if type(request)is not dict or request.get('field_id')!='L1':
        raise ValueError('One explicit ordinary interest-prefix request required')
    if type(approved_profile)is not dict or set(approved_profile)!={'summary_identity','child_identity','input_fields','output_fields','array_blocks'}:
        raise ValueError('Trusted exact prefix metadata profile required')
    inputs=approved_profile['input_fields'];outputs=approved_profile['output_fields']
    if type(inputs)is not list or len(inputs)!=16 or type(outputs)is not list or len(outputs)!=3:
        raise ValueError('All sixteen child and three current target fields required')
    fields={x['field_id']:tuple(x[k]for k in('ordinal','kind','format','template_attributes'))for x in inputs}
    if len(fields)!=16 or 'L1'not in fields:raise ValueError('Unique complete current input metadata required')
    base=dict(request);base['field_id']='L1'
    proof=read_request(base,binary_loader=binary_loader,approved_metadata={
        'summary_identity':approved_profile['summary_identity'],'child_identity':approved_profile['child_identity'],
        'fields':fields,'array_blocks':approved_profile['array_blocks']})
    doc,buffers,bound,registry,selected,source=binary_loader(request['source'])
    if hashlib.sha256(source).hexdigest()!=proof['source_sha256']:raise ValueError('Source changed while reading current fields')
    fsindex,topindex=proof['summary_path'];summary=doc.formsets[fsindex].forms[topindex]
    child=summary.children[proof['child_path'][-1]];row=request['row_number'];fsid=proof['source_formset_id']
    def walk(forms):
        for form in forms:
            yield form
            yield from walk(form.children)
    all_children=[f for f in walk(doc.formsets[fsindex].forms)if f.header.identifier.rstrip(b' ').upper()==b'F1099I']
    if len(all_children)!=1:
        raise ValueError('This prefix requires exactly one source F1099I copy; omitted copies cannot be assumed blank')
    table=next(t for t in summary.tables if t.identifier.rstrip(b' ')==b'BINT')
    if row!=1 or table.last_used_record_index!=1:
        raise ValueError('Only the existing single first-row BINT document profile is closed')
    traces=[]
    def read(form,path,form_id,plan,element):
        required={'reference','field_id','ordinal','kind','format','template_attributes'}
        if type(plan)is not dict or set(plan)!=required:raise ValueError('Exact approved field plan required')
        template=registry.resolve(fsid,form_id,selected[fsid,form_id])
        declared=[f for f in template.fields if f.field_id==plan['field_id']]
        if len(declared)!=1 or tuple(getattr(declared[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(plan[k]for k in('ordinal','kind','format','template_attributes')):
            raise ValueError('Current complete metadata differs from approved field')
        fid=plan['field_id'].encode().ljust(32,b' ')
        entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
        if len(entries)>1:raise ValueError('Ambiguous full-ID source D2 entry')
        ordinal=entries[0].source_field_index if entries else None
        node=find_value(form.hash_state,ordinal,element)if ordinal is not None else None
        trace=dict(field_id=plan['field_id'],reference=plan['reference'],document_path=list(path),
            source_ordinal=ordinal,current_ordinal=plan['ordinal'],element_index=element,
            source_storage='D2_absent'if ordinal is None else'hash_node_absent'if node is None else'stored')
        if node is not None:
            bindings=[b for b in bound.bindings.get(tuple(path),())if b.field_id==fid and b.element_index==element]
            if len(bindings)!=1 or bindings[0].source_field_index!=ordinal or bindings[0].current_field_index!=plan['ordinal']:
                raise ValueError('Source-to-current full-ID binding differs')
            binding=bindings[0]
            if (node.kind_byte,node.flag10)!=(plan['kind'],plan['format'])or(binding.source_kind,binding.source_format)!=(node.kind_byte,node.flag10):
                raise ValueError('Stored source kind/format differs from current approved metadata')
            allowed_action=binding.native_action in('preserve','requires_additional_scalar_codec')or(
                binding.native_action=='drop_empty_storage'and not node.specific_attributes&1)or(
                binding.native_action=='requires_string_or_identity_context'and node.kind_byte==7)
            if not allowed_action:
                raise ValueError('Native source conversion or array recovery is unclosed')
            if node.specific_attributes not in(0,1,2,3,8,9,10,11):
                raise ValueError('Only ordinary Used/Computed/Override masks are supported')
            trace.update(kind=node.kind_byte,FV_attributes=node.specific_attributes,raw64=str(node.raw),
                packed_exponent=node.exponent_byte,format_flag10=node.flag10,flag11=node.flag11,value_header=node.header,
                source_binding_native_action=binding.native_action)
        trace['present']=node is not None and bool(node.specific_attributes&1)
        traces.append(trace)
        return node,trace
    def amount(node):
        if node is None:return None
        return current_numeric_input(StoredCents(node.kind_byte,node.raw,node.specific_attributes,
            node.header,node.flag10,node.flag11,node.exponent_byte))
    row_label='owned-summary-row:'+str(row);copy_label='owned-source-copy:'+':'.join(map(str,proof['child_path']))
    supplied={4273:{row_label:Decimal(row)}}
    for plan in inputs:
        node,trace=read(child,proof['child_path'],'F1099I',plan,0);ref=plan['reference']
        if ref==9389:
            value=None
            if trace['present']:
                if node.kind_byte!=10 or node.header or node.flag10 or node.flag11:raise ValueError('Ordinary current kind10 HCOPYNUM required')
                if not 1<=node.raw<=65520:raise ValueError('HCOPYNUM must be an explicit finite positive stored number')
                value=Decimal(node.raw)
            trace['HCOPYNUM_is_not_header_word7c']=True
        elif plan['kind']==11:value=amount(node)
        elif ref in(9393,9412)and plan['kind']==7:
            value=current_string_input(node,table=child.string_table,table_id=child.table_id)
        else:
            raise ValueError('Unknown selected input type or source reference')
        trace['supplied_value']=(dict(type='StringValue_bytes',hex=value.hex(),present=True)if type(value)is bytes
            else None if value is None else format(value,'f'))
        supplied[ref]={copy_label:value}
    prior={}
    for plan in outputs:
        node,trace=read(summary,proof['summary_path'],'FSCHB',plan,row)
        attrs=node.specific_attributes if node is not None else 0
        if attrs&8:raise ValueError('Prior output override requires the exterior native assignment protocol')
        value=amount(node)
        prior[plan['reference']]={row_label:dict(value=value,computed=bool(attrs&2),overridden=False,itemized=False)}
        trace['prior_value']=None if value is None else format(value,'f')
    if set(supplied)!={4273,*[x['reference']for x in inputs]}:
        raise ValueError('No missing or invented leaf inputs permitted')
    return dict(inputs=supplied,prior_values=prior,current_field_trace=traces,owner_proof=proof,
        row_label=row_label,source_label=copy_label,
        owned_labels_are_native_UUIDs=False,native_record_inventory_verified=False,
        actual_array_proof=proof['actual_array_proof'],
        complete_interest_adjustment_chain=False,can_commit_to_source=False)


def project(request,*,binary_loader,approved_profile,program,expected_program_sha256):
    snapshot=read_snapshot(request,binary_loader=binary_loader,approved_profile=approved_profile)
    engine=Prefix(program,expected_sha256=expected_program_sha256,inputs=snapshot['inputs'],prior_values=snapshot['prior_values'])
    result=engine.run()
    def json_values(value):
        if type(value)is Decimal:return format(value,'f')
        if type(value)is dict:return {str(k):json_values(v)for k,v in value.items()}
        if type(value)is list:return [json_values(v)for v in value]
        return value
    writes=[]
    by_ref={x['reference']:x for x in approved_profile['output_fields']}
    for assignment in engine.assignments:
        plan=by_ref[assignment['reference']]
        trace=next(t for t in snapshot['current_field_trace']if t['reference']==assignment['reference'])
        writes.append(dict(field_id=plan['field_id'],element_index=request['row_number'],
            reference=assignment['reference'],computed_value=json_values(assignment['computed_value']),
            proposed_value=json_values(assignment['result']),retained_existing_Used=assignment['retained'],
            target_node_exists=trace['source_storage']=='stored',
            target_origin='loaded_current_source'if trace['source_storage']=='stored'else'current_source_field_absent',
            target_form_exists_in_source=True,can_commit_to_source=False))
    return dict(source_sha256=snapshot['owner_proof']['source_sha256'],program_content_sha256=expected_program_sha256,
        source_origin_authority_external_to_request=True,comparison_only=True,writeback_allowed=False,
        original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0,
        roots=json_values(result),proposed_row_writes=writes,
        actual_array_proof=snapshot['actual_array_proof'],
        root_domains_are_owned_existing_row_projection=True,
        current_strings_are_copied_bytes_for_IsNotBlank_only=True,
        present_supplementary_inputs=[t['field_id']for t in snapshot['current_field_trace']if t['reference']in(9386,9387,9388,9390,9392,9393,9395,9398,9402,9412,9436,9438)and t['present']],
        current_field_trace=snapshot['current_field_trace'],evaluated_references=engine.trace,
        owned_labels_are_native_UUIDs=False,native_record_inventory_verified=False,
        not_computed=['full interest adjustments','EE bond exclusion','FSCHB.L4 final total','F1040/R2 final tax','native scheduler/global queue'])
