"""Whole source/raw -> owned current MC diagnostic; no native/audit files."""
from pathlib import Path
import json,base64,hashlib

def _read_source(request,authority):
    required={'source','expected_source_sha256','summary_path','source_formset_index','row_number','field_id','need_native_row_uuid','local_resource'}
    if type(request)is not dict or set(request)!=required:
        raise ValueError('Exact source, current field and local resources required; supplied amounts/cache/UUID/state are not accepted')
    from . import current_mapping_numeric_reference as mapping,raw_numeric_input_reference as policy
    from .current_numeric_leaf_reference import read_source_leaf
    from .raw_tke_xml_reference import read_xml_resource
    from .raw_tke_nodes_reference import read_node_table
    import binary_tax
    if Path(binary_tax.__file__).resolve().parent!=Path(__file__).resolve().parent.parent:
        raise ValueError('Fixed local binary source reader required')
    entry=request['local_resource']
    if type(entry)is not dict or set(entry)!={'base64','sha256'}or entry['sha256']!=mapping.CARRIER or type(entry['base64'])is not str or len(entry['base64'])>48*1024*1024:
        raise ValueError('One complete matching local calculation resource required')
    try:raw=base64.b64decode(entry['base64'],validate=True)
    except Exception as error:raise ValueError('Invalid local resource encoding')from error
    if hashlib.sha256(raw).hexdigest()!=mapping.CARRIER:raise ValueError('Local resource content does not match the supported source')
    definitions=read_xml_resource(raw,approved_carrier_sha256=mapping.CARRIER,approved_payload_sha256=mapping.PAYLOAD,resource_type=5017)
    if len(definitions)!=1 or definitions[0].decoded_sha256!=mapping.XML:raise ValueError('Exact complete Mapping declarations required')
    config=mapping.configuration(definitions[0].parse(),request['field_id'])
    table=read_node_table(raw,approved_carrier_sha256=policy.CARRIER,approved_payload_sha256=policy.NODE_PAYLOAD)
    schemas=read_xml_resource(raw,approved_carrier_sha256=policy.CARRIER,approved_payload_sha256=policy.SCHEMA_PAYLOAD,resource_type=5014)
    if len(schemas)!=1 or schemas[0].decoded_sha256!=policy.SCHEMA_XML:raise ValueError('Exact complete field schema required')
    node_id=config['mef_path'].replace('[uuid_1]','')
    input_policy=policy.derive_policy(table,schemas[0].parse(),request['field_id'],node_id)
    captured=[]
    def same_fixed_loader(source):
        if captured:raise ValueError('Unexpected second source parse refused')
        loaded=binary_tax._context(source);captured.append(loaded);return loaded
    current=read_source_leaf({k:v for k,v in request.items()if k!='local_resource'},binary_loader=same_fixed_loader,approved_profile=authority['bank_profile'])
    if current['current_field']['source_storage']!='stored':raise ValueError('Actual existing stored field required; missing is not zero')
    loaded=captured[0];document=loaded[0];path=current['current_field']['document_path']
    form=document.formsets[path[0]].forms[path[1]]
    for child_index in path[2:]:form=form.children[child_index]
    from .source_child_form_uuid_reference import source_child_form_uuid
    from .MC_path_UUID_reference import source_uuid_path
    uuid=source_child_form_uuid(form.derived_tail);candidate=source_uuid_path(config,uuid)
    result=dict(current_source=current,raw_mapping=config,raw_input_policy=input_policy,
        source_child_UUID_path_candidate=candidate,binary_context_calls=len(captured),
        no_prepared_UUID_path_amount_or_Boolean=True,original_runtime=0,physical_TPS_writes=0,
        native_GetMultiCopyInputValue_executed=False,native_Record_inventory_verified=False,
        comparison_only=True,writeback_allowed=False)
    return result,loaded

def _namespace(request,result,loaded,authority):
    PRIMARY=authority['primary_carrier_sha256'];RESOURCE=authority['local_resource_sha256']
    SOURCE_ORDER=tuple(authority['source_carrier_order'])
    doc,buffers,bound,app_registry,selected,wire=loaded
    if not any(item['sha256']==PRIMARY for item in request['source']['carriers']):
        raise ValueError('Source registry lacks required original fdidt primary carrier cf304949…; sourceabsence is not a namespace miss')
    if tuple(item['sha256'] for item in request['source']['carriers'])!=SOURCE_ORDER:
        raise ValueError('Exact original seven field carriers followed by fdidt primary required; no extra/reordered namespace authority')
    import taxml_wire
    from . import compiled_identity_runtime_adapter as identity_adapter
    from interop.form_core.effective_registry_fields_reference import Carrier,register_records
    from interop.form_core.effective_array_bridge_reference import build_effective_templates_and_arrays
    complete=[]
    for item in request['source']['carriers']:
        data=base64.b64decode(item['base64'],validate=True)
        complete.append((item['sha256'],taxml_wire.read_xprf_resources(data,item['sha256'])))
    if RESOURCE in [digest for digest,_ in complete]:raise ValueError('Distinct source and raw metadata carrier channels required by this finite receiver')
    data=base64.b64decode(request['local_resource']['base64'],validate=True)
    complete.append((RESOURCE,taxml_wire.read_xprf_resources(data,RESOURCE)))
    # A fixed independent metadata-registry construction order, never a claim
    # about the native global template registration order.
    registry=register_records(tuple(Carrier(d.encode('ascii'),m) for d,m in complete))
    source_fs=doc.formsets[request['source_formset_index']]
    matches=[fs for fs in registry.formsets if fs.identifier==source_fs.header.identifier.ljust(32,b' ')]
    if len(matches)!=1:raise ValueError('One exact same-source compiled FormSet required')
    primary=matches[0].primary
    if primary is None or (primary.source.carrier_key,primary.source.metadata_type,primary.source.resource_id)!=(PRIMARY.encode('ascii'),18500,1):
        raise ValueError('Effective primary must be the exact original fdidt18500/rid1, not merely present in the request')
    identity=identity_adapter.read_compiled_identity(registry,matches[0])
    if (identity.source_home.carrier_key,identity.source_home.resource_id,identity.source_payload_sha256)!=(RESOURCE.encode('ascii'),1,'ce51b6c95e9f466a941933966a84ac0f1e4afde4af0cc1a01eea6fffd81c7d10'):
        raise ValueError('Exact original fdittx7000/rid1 identity supplier required')
    namespace=result['raw_mapping']['tps_path'].split('$',1)[0].encode('ascii')
    if identity.mct!=namespace:raise ValueError('Exact original7000 MCT does not match raw Mapping namespace')
    templates,report,arrays=build_effective_templates_and_arrays(complete,selected,
        field_factory=taxml_wire.Field,template_factory=taxml_wire.Template)
    for template in templates:
        key=(template.formset_id,template.form_id)
        if template!=app_registry.resolve(*key,selected[key]):raise ValueError('Namespace metadata changes a selected current field template')
        if arrays[key]!=app_registry.array_payloads[key]:raise ValueError('Namespace metadata changes selected actual array definitions')
    result['owned_namespace_supply']=dict(status='constructed_from_actual_source_metadata',
        source_FormSet_identifier_hex=source_fs.header.identifier.hex(),MCT_hex=identity.mct.hex(),
        raw_Mapping_namespace_hex=namespace.hex(),primary_carrier_sha256=PRIMARY,
        source7000_carrier_sha256=RESOURCE,source7000_resource_type=7000,source7000_resource_id=identity.source_home.resource_id,
        source7000_payload_sha256=identity.source_payload_sha256,primary_ID_hex=identity.formset_id.hex(),
        resource_year_hex=identity.tax_year.hex(),source_header_checksum_or_declared_version=source_fs.header.template_version,
        compiled_FormSet_version=matches[0].version,these_version_fields_are_not_assumed_equal=True,
        original_selected_templates_preserved=len(templates),original_selected_arrays_preserved=len(arrays),
        independent_metadata_registry_carrier_order=[d for d,_ in complete],
        namespace_bound_to_same_parsed_source_FS=True,original_Source_document_bytes_unchanged=True,
        native_global_registry_or_current_FDI_lookup_verified=False,native_cache_miss_verified=False,
        native_record_inventory_verified=False,native_Record_UUID=None,complete_MC_input_computed=False,
        original_runtime=0,physical_TPS_writes=0,comparison_only=True,writeback_allowed=False)
    return result,loaded,registry,matches[0]

def _root_UUID(request,result,loaded,registry,compiled_fs):
    from .form_uuid_initialization_reference import compiled_uuid_policy,fresh_non_multiple_uuid,owned_form_address
    from .owned_MC_nodes_reference import source_inventory,get_forms,get_child_forms,project_selected
    from .normal_query_address_reference import owned_summary_query
    document,buffers,bound,app_registry,selected,wire=loaded
    if bound.document is not document:raise ValueError('Identical actual document/bindings required')
    child_path=tuple(result['current_source']['current_field']['document_path'])
    parent_path=tuple(request['summary_path'])
    parent_def=next((f for f in compiled_fs.forms if f.identifier==b'FSCHB'.ljust(32,b' ')),None)
    child_def=next((f for f in compiled_fs.forms if f.identifier==b'F1099I'.ljust(32,b' ')),None)
    if parent_def is None or child_def is None:raise ValueError('Both source compiled Form definitions required')
    parent_policy=compiled_uuid_policy(parent_def);child_policy=compiled_uuid_policy(child_def)
    if (parent_policy['compiled_type'],parent_policy['compiled_limit'])!=(1,1):
        raise ValueError('Exact authenticated FSCHB type1/limit1 required')
    if (child_policy['compiled_type'],child_policy['compiled_limit'])!=(4,0):
        raise ValueError('Exact authenticated F1099I type4/limit0 required')
    candidate=result['source_child_UUID_path_candidate']
    uuid=candidate['source_child_FormUUID149']['source_form_uuid'].encode('ascii')
    inventory=source_inventory(document,child_path,uuid)
    parents=get_forms(inventory,b'FSCHB'.ljust(32,b' '))
    if len(parents)!=1 or parents[0].source_path!=parent_path:
        raise ValueError('One exact same-source owned summary parent required')
    parent=parents[0]
    # This initializes only this independent receiver's parent string. It is
    # neither a claim about the native loaded Form+08 nor a missing149 default.
    parent.saved_form_uuid=fresh_non_multiple_uuid(parent_policy)
    children=get_child_forms(inventory,parent,b'F1099I'.ljust(32,b' '))
    if len(children)!=1 or children[0].source_path!=child_path:
        raise ValueError('Exactly one supported source child required; no unknown child UUID is defaulted')
    child=children[0]
    mct=bytes.fromhex(result['owned_namespace_supply']['MCT_hex'])
    form_path=mct+b'$'+owned_form_address(child)
    field_path=form_path+b'.'+request['field_id'].encode('ascii')
    if field_path.decode('ascii')!=candidate['prospective_tps_path']:
        raise ValueError('Constructed owned form address differs from actual source path candidate')
    from .normal_Mef_components_reference import same_label_cache_miss
    projection=same_label_cache_miss(result['raw_mapping'],field_path)
    owned=project_selected(inventory,parent_path,child_path,uuid,field_path,
        projection['conditional_MEF_path'].encode('ascii'),result['current_source']['direct_numeric_leaf'])
    query=owned_summary_query(result['raw_mapping'],owned)
    if query['owned_FindInstances_query']!='FDI$FSCHB:F1099I':raise ValueError('Exact normal form-only query required')
    result['owned_selected_MC_node_supply']=owned
    result['owned_normal_query_address']=query
    result['owned_Form_UUID_initialization']=dict(
        parent_compiled_policy=parent_policy,child_compiled_policy=child_policy,
        owned_parent_UUID_hex=parent.saved_form_uuid.hex(),owned_child_saved_FormUUID=uuid.decode('ascii'),
        owned_form_instance_path=form_path.decode('ascii'),owned_field_instance_path=field_path.decode('ascii'),
        matches_actual_source149_path_candidate=True,owned_form_enumeration_candidates=1,
        one_actual_source_context=True,actual_source_bytes_unchanged=True,
        own_initialization_scope='BaseC2 UUID string and source-derived IsMultiCopy initializer guard fragment only',
        all_other_unknown_UUIDs_remain_unknown=True,complete_InitializeValueForm_or_Load_executed=False,
        event_observers_and_default_suppliers_executed=False,native_loaded_parent_UUID_verified=False,
        native_FormSet_inventory_verified=False,native_FindInstances_executed=False,
        native_Record_UUID=None,original_runtime=0,physical_TPS_writes=0)
    result['complete_owned_GetMultiCopyInputValue']=False
    result['smallest_unclosed_suppliers']=[
        'complete owned Form initialization/Load and actual registered default/event effects beyond the bounded UUID fragment',
        'ordinary Concrete.v190 permissions/filter/current FT plus actual source-mode Refetch behavior',
        'actual full GetValuesHelper vector, MC-node mode and Unused Override emission',
        'GetMultiCopyValue constructor/recursive aggregation and complete input Error loop',
        'native active inventory/cache/queue and TPS commits remain outside the independently owned receiver']
    return result

def _MC(request,result):
    # Its strict exact8 request and one actual-v5 parse supply every source
    # Form/current D2/FV/Used/UUID/raw schema fact used below.
    from .owned_current_MC_value_reference import current_leaf_from_result,SourceInstance,OwnedCurrentMCReceiver,value_report
    from .MC_input_query_reference import query_from_schema
    from .normal_Mef_components_reference import same_label_cache_miss
    from .raw_tke_xml_reference import read_xml_resource
    leaf=current_leaf_from_result(result['current_source'])
    raw=base64.b64decode(request['local_resource']['base64'],validate=True)
    schemas=read_xml_resource(raw,approved_carrier_sha256='5e8db09dc9c4126c0cd85fe11ee7b02965a3b9e88db1075ba32efc4269e0bc2f',
        approved_payload_sha256='f027a36fba39d21e1ea9ca60e740c1b144e7e10440491500130bc7492da0ebdd',resource_type=5014)
    if len(schemas)!=1 or schemas[0].decoded_sha256!='712c753298e1f232949368e9d73ec6e999d3b5f15bbda70d69b9461442efb0d3':
        raise ValueError('Exact actual source schema required')
    query=query_from_schema(schemas[0].parse(),result['raw_input_policy'])
    if query['conditional_fresh_schema_SortKeyPresent']or query['conditional_same_schema_logical_key_extra_paths']:
        raise ValueError('Sorted/logical-key normal input is outside the current source receiver')
    tps=result['owned_Form_UUID_initialization']['owned_field_instance_path'].encode('ascii')
    projection=same_label_cache_miss(result['raw_mapping'],tps)
    mef=projection['conditional_MEF_path'].encode('ascii')
    node_id=query['typed_input_cache_198_key'].encode('ascii')
    ancestor=query['GetFullAncestorsInnerFirst'][0].encode('ascii')
    receiver=OwnedCurrentMCReceiver(node_id,ancestor,SourceInstance(tps,mef,leaf))
    value=receiver.get_value();again=receiver.get_value()
    if value is not again or receiver.source_enumerations!=1 or receiver.typed_cache_hits!=1:
        raise AssertionError('Owned cache did not retain actual computed shared value')
    report=value_report(value)
    if report['Error']:raise ValueError('Actual owned input Error prevents this supported source calculation path')
    result['owned_current_MC_input']=dict(
        status='executed_from_complete_same_source',supported_scope='single existing Used1 kind11 F1099I child in exact FSCHB owner',
        source_enumeration_complete_for_this_owned_scope=True,source_child_candidates=1,
        instance_vector=[dict(TPS_path=tps.decode('ascii'),MEF_path=mef.decode('ascii'),has_value=True,
            FV_attributes=result['current_source']['current_field']['FV_attributes'],value=result['current_source']['direct_numeric_leaf'])],
        MC_nodes=receiver.nodes.report(),value=report,typed_input_cache_key=node_id.decode('ascii'),
        owned_input_cache_entries=len(receiver.typed_values),owned_instance_cache_entries=len(receiver.instances.instances),
        owned_MC_node_cache_entries=len(receiver.instances.MC_nodes),source_enumerations=receiver.source_enumerations,
        initial_miss_is_constructed_owned_state=True,typed_cache_hits=receiver.typed_cache_hits,
        repeated_read_same_owned_value_reference=value is again,
        shallow_map_constructor_keeps_resolved_leaf_reference=next(iter(value.rows.values()))is leaf,
        own_Error_reduction_executed=True,whole_CalcAndRound_input_vector_or_output_not_executed=True,
        source_schema_query=query,one_actual_source_context=True,source_field_Used_Override_and_cents_preserved=True,
        stored14D_or14F_restored=False,native_active_cache_miss_or_snapshot_verified=False,
        native_FT_Refetch_permissions_filter_and_GetValuesHelper_executed=False,
        complete_native_Initialize_Load_events_or_inventory_verified=False,native_Record_UUID=None,
        original_runtime=0,physical_TPS_writes=0,comparison_only=True,writeback_allowed=False)
    result['complete_owned_GetMultiCopyInputValue']=False
    result['complete_owned_selected_current_input_projection']=True
    result['smallest_unclosed_suppliers']=[
        'Unused/absent field full MC-node/emission shape is refused; no blank/zero/default MC is invented',
        'native current FT/permission/filter/Refetch/active14F and complete native Form Load/events remain unexecuted',
        'other input nodes/AdditionalValues and whole CalcAndRound dependency vector require their actual source suppliers',
        'no native queue, current result-cache freshness, USER_ENTERED_ASSIGN prior or TPS output write is inferred']
    return result

def read_owned_request(request,authority):
    result,loaded=_read_source(request,authority)
    result,loaded,registry,compiled_fs=_namespace(request,result,loaded,authority)
    result=_root_UUID(request,result,loaded,registry,compiled_fs)
    result=_MC(request,result)
    result['format']='tax-reborn-owned-current-mc-source-report-v1'
    result['source_only_diagnostic']=True
    result['original_resource_bytes_in_report']=False
    result['whole_original_tax_or_IRS_result_computed']=False
    return result
