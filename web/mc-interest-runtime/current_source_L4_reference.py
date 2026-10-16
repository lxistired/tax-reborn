"""Actual current source ->14725/14873/EE/CS113/ADJUST -> bounded L2/L4.

This orders independently written finite models. No native schedule, row UUID,
newkey/storage write or source summary freshness is implied. In particular a
retained current UserEntered result is retained, never called a fresh formula.
"""
import hashlib
from current_all_interest_reference import project_all_interest_sources
from current_adjustment_presence_reference import recalculate_adjustment_presence
from current_information_projection_reference import project_information
from current_interest_tail_reference import read_tail_priors
from finite_interest_total_reference import TotalTail
from numeric_current_input_reference import StoredCents,current_numeric_input
from interop.derived_form.value_hash_wire_reference import find_value
from interop.form_core.hash_structure_reference import validate_document_hashes


def read_saved_adjustments(loaded,path,*,approved_field):
 doc,buffers,bound,registry,selected,wire=loaded
 if getattr(bound,'document',None)is not doc or type(path)not in(list,tuple)or len(path)!=2 or any(type(i)is not int or i<0 for i in path):raise ValueError('Same validated loaded current manual source required')
 validate_document_hashes(doc);path=tuple(path);fs=doc.formsets[path[0]];form=fs.forms[path[1]];fsid=fs.header.identifier.decode().rstrip(' ')
 if approved_field!={'reference':4263,'form_id':'FSCHB','field_id':'L1C','ordinal':28,'kind':11,'format':0,'template_attributes':3652}:raise ValueError('Exact authenticated original manual ADJUST field required')
 identity=selected.get((fsid,'FSCHB'));template=registry.resolve(fsid,'FSCHB',identity);fields=[f for f in template.fields if f.field_id=='L1C']
 if len(fields)!=1 or tuple(getattr(fields[0],k)for k in('ordinal','kind','format','attributes'))!=(28,11,0,3652):raise ValueError('Manual ADJUST current metadata differs')
 key=(fs.header.identifier,form.header.identifier);arrays=[a for block in bound.arrays[key]for a in block if a.identifier.ljust(32,b' ')==b'ADJUST'.ljust(32,b' ')]
 if len(arrays)!=1 or(arrays[0].first_field,arrays[0].last_field,arrays[0].element_limit,arrays[0].flags)!=(27,28,65520,49):raise ValueError('Exact actual ADJUST array required')
 fid=b'L1C'.ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
 if len(entries)>1:raise ValueError('Ambiguous full-ID manual amount source')
 ordinal=entries[0].source_field_index if entries else None;records=[b for b in bound.bindings.get(path,())if b.field_id==fid or b.current_field_index==28];values={};trace=[]
 for b in records:
  if b.field_id!=fid or b.current_field_index!=28 or b.source_field_index!=ordinal or not 1<=b.element_index<=65520:raise ValueError('Exact manual amount source/current row binding required')
  node=find_value(form.hash_state,ordinal,b.element_index)
  if node is None or(node.kind_byte,node.flag10,b.source_kind,b.source_format,b.fv_attributes)!=(11,0,11,0,node.specific_attributes):raise ValueError('Manual amount reachable source/current node differs')
  if b.native_action not in('preserve','requires_additional_scalar_codec','drop_empty_storage')or node.specific_attributes not in(0,1,2,3,8,9,10,11):raise ValueError('Manual amount current protocol unclosed')
  value=current_numeric_input(StoredCents(node.kind_byte,node.raw,node.specific_attributes,node.header,node.flag10,node.flag11,node.exponent_byte));label='owned-saved-ADJUST-row:'+str(b.element_index)
  if label in values:raise ValueError('Duplicate saved manual adjustment row')
  values[label]=value;trace.append(dict(document_path=list(path),field_id='L1C',source_ordinal=ordinal,current_ordinal=28,element_index=b.element_index,present=bool(node.specific_attributes&1),FV_attributes=node.specific_attributes,raw64=str(node.raw),value=value))
 if len(values)>64:raise ValueError('Finite saved manual adjustment domain exceeded')
 tables=[t for t in form.tables if t.identifier.ljust(32,b' ')==b'ADJUST'.ljust(32,b' ')]
 if len(tables)>1:raise ValueError('Ambiguous saved manual table')
 if tables:
  byid={e.identifier:e.source_field_index for e in form.derived_tail.field_map.entries}
  if(tables[0].word28,tables[0].word2a)!=(byid.get(b'L1CD'.ljust(32,b' ')),ordinal):raise ValueError('Saved manual table endpoints need exact full-ID source binding')
 return dict(values=values,current_saved_field_trace=trace,saved_table_present=bool(tables),saved_D2_field_present=ordinal is not None,empty_is_observed_saved_storage_only=not values,native_record_inventory_verified=False)


def project_source_L4(request,*,binary_loader,authorities,programs):
 if type(authorities)is not dict or set(authorities)!={'all_sources','product','manual_adjustment','information_identity','information_fields','information_section','tail_targets'}:raise ValueError('Complete externally authenticated current L4 authorities required')
 if type(programs)is not dict or set(programs)!={'all_sources','presence','tail'}or type(programs['tail'])is not dict or set(programs['tail'])!={'model','sha256'}:raise ValueError('Complete externally authenticated current L4 programs required')
 loaded=binary_loader(request['source']);digest=hashlib.sha256(loaded[-1]).hexdigest()
 def same_loader(source):
  if source!=request['source']:raise ValueError('Source changed within current L4 projection')
  return loaded
 sources=project_all_interest_sources(request,binary_loader=same_loader,authorities=authorities['all_sources'],programs=programs['all_sources']);a=authorities['all_sources']['scalar'];bank_request={k:v for k,v in request.items()if k!='source_formset_index'}
 presence=recalculate_adjustment_presence(bank_request,binary_loader=same_loader,approved_bank_profile=a['bank_profile'],approved_entries=a['bank_entries'],approved_targets=a['bank_targets'],approved_OID=a['OID'],approved_product=authorities['product'],programs=programs['presence'])
 information=project_information(bank_request,binary_loader=same_loader,approved_identity=authorities['information_identity'],approved_fields=authorities['information_fields'],approved_section=authorities['information_section'])
 prior=read_tail_priors(bank_request,binary_loader=same_loader,approved_profile=a['bank_profile'],approved_targets=authorities['tail_targets']);manual=read_saved_adjustments(loaded,request['summary_path'],approved_field=authorities['manual_adjustment'])
 if any(x['source_sha256']!=digest for x in(sources,presence,information,prior)):raise ValueError('Every L4 producer must use one identical source snapshot')
 inputs={14725:sources['roots'][14725],14873:presence['roots'][14873],4263:manual['values'],15167:sources['fresh_EE_15167'],9801:information['projected_input_9801']};tp=programs['tail'];engine=TotalTail(tp['model'],expected_sha256=tp['sha256'],inputs=inputs,scalar_priors=prior['scalar_priors'],uniform_amt_prior=prior['uniform_AMT_prior']);roots=engine.run()
 return dict(source_sha256=digest,roots=roots,source_projections=sources,adjustment_presence_projection=presence,information_section_projection=information,saved_manual_adjustment_projection=manual,current_tail_prior_trace=prior['scalar_prior_trace'],uniform_AMT_prior=prior['uniform_AMT_prior'],proposed_graph_assignments=engine.assignments,evaluated_tail_references=engine.trace,actual_internal_producer_values=inputs,
  all_intermediate_values_derived_from_current_source_and_authenticated_programs=True,no_manual_amount_or_Boolean_cutpoints=True,original_L4_from_bounded_current_source_recomputed=True,current_scalar_INPUT10770_fresh_reaggregation=False,saved_ADJUST_rows_freshly_rebuilt_from_new_adjustments=False,caller_owned_explicit_producer_order=True,native_dependency_schedule_executed=False,
  native_record_inventory_verified=False,native_qualified_UUID_mapping_executed=False,BINT_to_INT_row_identity_verified=False,TPS_output_conversion_executed=False,native_post_Load_defaults_executed=False,all_original_taxpayer_return_recomputed=False,R2_F1040_join_executed=False,comparison_only=True,writeback_allowed=False,original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
