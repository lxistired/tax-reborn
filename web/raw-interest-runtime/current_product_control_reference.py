"""Actual existing same-source TKEHAVE.PRODUCT -> source control comparison."""
import hashlib
from current_string_input_reference import current_string_input
from strict_actual_array_interest_reference import _raw_header_ids
from interop.derived_form.value_hash_wire_reference import find_value
from current_bank_values_reference import project_normal_adjustments
from finite_product_control_reference import ProductControl


def project_product_control(request,*,binary_loader,approved_profile,approved_entries,approved_targets,
        bank_program,bank_sha256,approved_product,control_program,control_sha256):
    loaded=binary_loader(request['source']);doc,buffers,bound,registry,selected,wire=loaded
    def same_loader(source):
        if source!=request['source']:raise ValueError('Source changed within Product control read')
        return loaded
    if type(approved_product)is not dict or set(approved_product)!={'identity','field'}:raise ValueError('Trusted exact Product source identity required')
    plan=approved_product['field'];keys={'reference','form_id','field_id','ordinal','kind','format','template_attributes'}
    if type(plan)is not dict or set(plan)!=keys or tuple(plan[k]for k in('form_id','field_id','ordinal','kind','format','template_attributes'))!=('TKEHAVE','PRODUCT',178,7,0,0):raise ValueError('Exact reviewed Product metadata required')
    fsindex=request['summary_path'][0];fs=doc.formsets[fsindex];fsid=fs.header.identifier.decode().rstrip(' ')
    roots=[(i,f)for i,f in enumerate(fs.forms)if f.header.identifier.ljust(32,b' ')==b'TKEHAVE'.ljust(32,b' ')]
    if len(roots)!=1:raise ValueError('One existing same-FormSet TKEHAVE root required; artifact name is not Product supply')
    index,form=roots[0];path=(fsindex,index);rawid,parent=_raw_header_ids(form)
    if rawid.ljust(32,b' ')!=b'TKEHAVE'.ljust(32,b' ')or parent is not None or form.header.word7c!=0:raise ValueError('Exact current TKEHAVE copy0 root required')
    if tuple(selected.get((fsid,'TKEHAVE'),()))!=tuple(approved_product['identity']):raise ValueError('Current Product template identity differs')
    key=(fs.header.identifier,form.header.identifier)
    if bound.context.form_factories.get(key)!='value_form'or bound.context.table_factories.get(key)!='value_table':raise ValueError('Explicit caller ValueForm/ValueTable factory required')
    fields=[f for f in registry.resolve(fsid,'TKEHAVE',approved_product['identity']).fields if f.field_id=='PRODUCT']
    if len(fields)!=1 or(fields[0].ordinal,fields[0].kind,fields[0].format,fields[0].attributes)!=(178,7,0,0):raise ValueError('Current Product metadata differs')
    fid=b'PRODUCT'.ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
    if len(entries)!=1:raise ValueError('Complete source Product full-ID D2 required')
    ordinal=entries[0].source_field_index;bindings=[b for b in bound.bindings.get(path,())if b.field_id==fid or b.current_field_index==178]
    if len(bindings)!=1:raise ValueError('One existing current Product binding required')
    b=bindings[0];node=find_value(form.hash_state,ordinal,0)
    if node is None or(b.field_id,b.source_field_index,b.current_field_index,b.element_index,b.source_kind,b.source_format,b.fv_attributes)!=(fid,ordinal,178,0,7,0,node.specific_attributes)or(node.kind_byte,node.flag10)!=(7,0):raise ValueError('Exact source/current Product scalar binding required')
    if b.native_action not in('preserve','requires_string_or_identity_context'):raise ValueError('Unclosed Product conversion')
    value=current_string_input(node,table=form.string_table,table_id=form.table_id)
    if value is None:raise ValueError('Existing Used Product source required; Unused/absence cannot mean TURBOTAX or false')
    bank=project_normal_adjustments(request,binary_loader=same_loader,approved_profile=approved_profile,approved_entries=approved_entries,
        approved_targets=approved_targets,program=bank_program,expected_program_sha256=bank_sha256)
    digest=hashlib.sha256(wire).hexdigest()
    if bank['source_sha256']!=digest:raise ValueError('Product and bank graph must use one source snapshot')
    facts={**bank['same_source_graph_values'],plan['reference']:value}
    engine=ProductControl(control_program,expected_sha256=control_sha256,facts=facts);roots=engine.run()
    return dict(source_sha256=digest,roots=roots,source_Product_trace=dict(document_path=list(path),field_id='PRODUCT',current_ordinal=178,
        source_ordinal=ordinal,present=True,value_hex=value.hex(),FV_attributes=node.specific_attributes,source_raw64=str(node.raw),
        document_file_copy=form.header.file_copy,runtime_copy_number=form.header.word7c,source_template_identity=list(approved_product['identity'])),
        evaluated_control_references=engine.trace,upstream_bank=bank,complete_selected_control_graph=True,
        source_Product_is_loaded_current_input=True,TKEHAVE_Product_producer_or_native_defaults_executed=False,
        ThereAreAdjustments14873_recomputed=False,source_complete_calculation=False,
        native_record_inventory_verified=False,owned_labels_are_native_UUIDs=False,comparison_only=True,writeback_allowed=False,
        original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
