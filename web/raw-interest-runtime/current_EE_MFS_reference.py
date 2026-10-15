"""Actual source current strings -> qualified MFS -> bounded EE output.

F8815 must exist. Its saved L14 is recorded as retained storage, never called a
fresh exclusion amount. No missing form, absent input or manual status is used.
"""
import hashlib
from current_string_input_reference import current_string_input
from strict_actual_array_interest_reference import _raw_header_ids
from finite_EE_MFS_reference import EEMFS
from literal_transform_reference import select_transform
from interop.derived_form.value_hash_wire_reference import find_value
from interop.form_core.hash_structure_reference import validate_document_hashes

def project_EE_MFS(request,*,binary_loader,approved_profiles,program,expected_program_sha256):
 if type(request)is not dict or set(request)!={'source','expected_source_sha256','source_formset_index','need_native_row_uuid'}or request['source'].get('profile',{}).get('format')!='tax-reborn-binary-entity-profile-v5':raise ValueError('Exact actual-v5 source EE request required; no prepared status or amount')
 if type(approved_profiles)is not dict or set(approved_profiles)!={'FINFOWKS','FPERSWKS','F8815'}:raise ValueError('Externally authenticated exact three form current metadata required')
 doc,buffers,bound,registry,selected,wire=binary_loader(request['source']);digest=hashlib.sha256(wire).hexdigest();idx=request['source_formset_index']
 if digest!=request['expected_source_sha256']or getattr(bound,'document',None)is not doc:raise ValueError('Same source/current EE binding snapshot required')
 receipt=validate_document_hashes(doc)
 if type(idx)is not int or not 0<=idx<len(doc.formsets)or request['need_native_row_uuid']is not False:raise ValueError('Existing same FormSet and owned comparison identity required')
 fs=doc.formsets[idx];fsid=fs.header.identifier.decode('ascii').rstrip(' ');values={};trace=[];identities=[]
 def walk(f,p):
  yield p,f
  for i,c in enumerate(f.children):yield from walk(c,p+(i,))
 for formid,profile in approved_profiles.items():
  if set(profile)!={'identity','runtime_copy','fields'}or type(profile['fields'])is not list or len(profile['fields'])!=(2 if formid=='FINFOWKS'else 1):raise ValueError('Exact EE form current profile protocol required')
  fid32=formid.encode().ljust(32,b' ');matches=[(p,f)for i,f in enumerate(fs.forms)for p,f in walk(f,(idx,i))if f.header.identifier.ljust(32,b' ')==fid32]
  if len(matches)!=1:raise ValueError('One existing '+formid+' source form required; missing is not native blank')
  path,form=matches[0];raw,parent=_raw_header_ids(form)
  if len(path)!=2 or raw.ljust(32,b' ')!=fid32 or parent is not None or form.header.word7c!=profile['runtime_copy']:raise ValueError('Exact EE source root/copy required; saved U32 file_copy is separate')
  identity=selected.get((fsid,formid))
  if tuple(identity or())!=tuple(profile['identity']):raise ValueError('EE current metadata identity differs from source witness')
  key=(fs.header.identifier,form.header.identifier)
  if bound.context.form_factories.get(key)!='value_form'or bound.context.table_factories.get(key)!='value_table':raise ValueError('Explicit caller ValueForm/ValueTable boundary required')
  template=registry.resolve(fsid,formid,identity);identities.append(dict(form_id=formid,document_path=list(path),document_file_copy=form.header.file_copy,runtime_copy_number=form.header.word7c,source_present=True))
  for p in profile['fields']:
   if set(p)!={'reference','form_id','field_id','ordinal','kind','format','template_attributes','runtime_copy','transforms'}or p['form_id']!=formid or p['runtime_copy']!=form.header.word7c:raise ValueError('Exact EE current field protocol required')
   fields=[f for f in template.fields if f.field_id==p['field_id']]
   if len(fields)!=1 or tuple(getattr(fields[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(p[k]for k in('ordinal','kind','format','template_attributes')):raise ValueError('Current EE field metadata differs from original source')
   sourceid=p['field_id'].encode().ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==sourceid]
   if len(entries)>1:raise ValueError('Ambiguous EE source full-ID D2 field')
   source=entries[0].source_field_index if entries else None;node=find_value(form.hash_state,source,0)if source is not None else None;bs=[b for b in bound.bindings.get(path,())if b.field_id==sourceid or b.current_field_index==p['ordinal']]
   if node is not None:
    if len(bs)!=1 or(bs[0].source_field_index,bs[0].current_field_index,bs[0].element_index,bs[0].source_kind,bs[0].source_format,bs[0].fv_attributes)!=(source,p['ordinal'],0,p['kind'],p['format'],node.specific_attributes)or(node.kind_byte,node.flag10)!=(p['kind'],p['format']):raise ValueError('Exact reachable current/source EE scalar hash binding required')
    if bs[0].native_action not in('preserve','requires_string_or_identity_context','requires_additional_scalar_codec')and not(bs[0].native_action=='drop_empty_storage'and not node.specific_attributes&1):raise ValueError('Unclosed EE current field conversion')
   elif bs:raise ValueError('Current EE binding points to missing source storage')
   ref=p['reference'];value=None
   if ref is not None:
    if p['kind']!=7 or p['format']!=0:raise ValueError('Exact source EE CString current kind required')
    if node is None:raise ValueError('Explicit present current EE status source required')
    value=current_string_input(node,table=form.string_table,table_id=form.table_id)
    if value is None:raise ValueError('Unused EE status is not an explicit selected status')
    if p['transforms']:
     if ref!=9723 or p['transforms']!=[['true','MFJ'],['false','MFS'],['false','HOH']]:raise ValueError('Exact original FileJoint literal transforms required')
     if value!=b'MFS':raise ValueError('Finite EE current source requires exact MFS literal')
     selected_transform=select_transform(value.decode('ascii'),p['transforms'],direction=0)
     if(selected_transform.action,selected_transform.value,selected_transform.match_index)!=('literal_match','false',1):raise ValueError('Original TPS-to-MEF MFS literal transform differs')
     value=False
    elif ref==9847 and value!=b'3'or ref==9803 and value!=b'Married':raise ValueError('Finite EE requires exact source-selected MFS and Married literals')
    if ref in values:raise ValueError('Duplicate EE current source reference')
    values[ref]=value
   elif formid!='F8815'or p['field_id']!='L14'or p['kind']!=12 or p['format']!=0 or p['transforms']:raise ValueError('Only exact source F8815 saved L14 identity may be retained without fresh calculation')
   trace.append(dict(reference=ref,form_id=formid,field_id=p['field_id'],document_path=list(path),source_ordinal=source,current_ordinal=p['ordinal'],source_node_exists=node is not None,present=False if node is None else bool(node.specific_attributes&1),FV_attributes=0 if node is None else node.specific_attributes,raw64=None if node is None else str(node.raw),fresh_input=ref is not None,value_hex=value.hex()if type(value)is bytes else None,value_boolean=value if type(value)is bool else None,stored_L14_is_not_fresh_exclusion=ref is None))
 engine=EEMFS(program,expected_sha256=expected_program_sha256,inputs=values);roots=engine.run()
 return dict(source_sha256=digest,roots=roots,current_field_trace=trace,current_form_identities=identities,evaluated_references=engine.trace,normal_return_invariant_proofs=engine.proofs,unresolved_references=sorted(engine.unresolved),hash_structure_validation=receipt,
  current_typed_inputs_from_source=True,fresh_filing_status_from_qualified_current_source=True,stored_F8815_L14_used_as_fresh=False,prepared_Boolean_or_amount_supplied=False,whole1263_cone_executed=False,native_dependency_schedule_executed=False,native_exception_allocation_or_explanation_sideeffects_executed=False,
  native_record_inventory_verified=False,native_qualified_UUID_mapping_executed=False,full14725_executed=False,full_L4_R2_executed=False,comparison_only=True,writeback_allowed=False,original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
