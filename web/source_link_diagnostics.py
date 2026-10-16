"""Complete source bytes -> stored kind22/D7/2150/word7c consistency facts.

Fixed actual App loader; no loader, owner, descriptor or inventory callbacks.
The result never grants link editing or supplies active Form/FindForm success.
"""
import hashlib,json,struct
from collections import Counter
import binary_tax
from taxml_wire import read_xprf_resources
from interop.form_core.effective_registry_fields_reference import Carrier,register_records,field_template,UnsupportedProfile
from interop.form_core.field_link_2150_reference import effective_field_links,link_field_descriptor
from interop.derived_form.value_hash_wire_reference import find_value

sha=lambda b:hashlib.sha256(b).hexdigest()
def _json(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def _full(value):
 if type(value)is not bytes or not 0<len(value)<=32 or any(x<32 or x>126 for x in value)or value==b' '*len(value):raise UnsupportedProfile('Finite exact nonblank printable source ID required')
 return value.ljust(32,b' ')
def _path(path):return '/'.join(map(str,path))

def inspect_request(request):
 """Read-only diagnostic of each existing saved D7 record; no result writes."""
 if type(request)is not dict:raise UnsupportedProfile('Complete explicit source request required')
 captured=_json(request)
 doc,buffers,bound,app_registry,selected,wire=binary_tax._context(request)
 if request['profile']['format']not in('tax-reborn-binary-entity-profile-v5','tax-reborn-binary-entity-profile-v6'):
  raise UnsupportedProfile('Actual same-registry automatic arrays and full source-ID profile required')
 carriers=[]
 for item in request['carriers']:
  raw=binary_tax.prep.decode_blob(item['base64'],32*1024*1024)
  resources=read_xprf_resources(raw,item['sha256']);count=struct.unpack_from('<I',raw,12)[0]
  ranges=sorted((start,start+size)for _,_,start,size in(struct.unpack_from('<HHII',raw,16+i*12)for i in range(count)))
  if any(a[1]>b[0]for a,b in zip(ranges,ranges[1:])):raise UnsupportedProfile('Overlapping complete source resource ranges refused')
  carriers.append(Carrier(item['sha256'].encode('ascii'),resources))
 # This is an explicit source-bytes adapter into the copied exact Registry
 # class, not duck-typing the App Registry as a native compiled object.
 registry=register_records(tuple(carriers));forms=tuple(binary_tax.walk_forms(doc));by_path=dict(forms)
 reports=[];compiled={}
 def current(path,form):
  if path in compiled:return compiled[path]
  fs=doc.formsets[path[0]];fsid=_full(fs.header.identifier);fid=_full(form.header.identifier)
  fs_matches=[x for x in registry.formsets if x.identifier==fsid]
  if len(fs_matches)!=1 or fs_matches[0].version!=fs.header.template_version:raise UnsupportedProfile('Same source compiled FormSet ID/version required')
  matches=[x for x in fs_matches[0].forms if x.identifier==fid]
  if len(matches)!=1 or matches[0].primary is None:raise UnsupportedProfile('Same source complete current Form primary required')
  owner=matches[0];key=(fs.header.identifier.decode('ascii'),form.header.identifier.decode('ascii'))
  expected=selected.get(key)
  actual=(owner.primary.source.carrier_key.decode('ascii'),owner.primary.source.resource_id)
  if expected!=actual:raise UnsupportedProfile('Current Form primary must match this request selected identity')
  fields,_=field_template(registry,owner);app=app_registry.resolve(*key,expected)
  if tuple((f.identifier,f.ordinal,f.kind,f.format,f.attributes,f.hidden)for f in fields.fields)!=tuple((_full(f.field_id.encode('ascii')),f.ordinal,f.kind,f.format,f.attributes,f.hidden)for f in app.fields):
   raise UnsupportedProfile('Complete same-request current field dictionaries disagree')
  compiled[path]=(owner,fields);return owner,fields
 for containing_path,containing in forms:
  duplicates=Counter((l.form_id,l.file_copy,l.field_id,l.element_index)for l in containing.links)
  for index,link in enumerate(containing.links):
   report=dict(containing_path=_path(containing_path),link_index=index,containing_form_id_hex=containing.header.identifier.hex(),containing_file_copy_U32=containing.header.file_copy,containing_stored_word7c_U16=containing.header.word7c,descriptor_form_id_hex=link.form_id.hex(),descriptor_receiving_file_copy_U32=link.file_copy,descriptor_field_id_hex=link.field_id.hex(),element=link.element_index,original_D7_record_sha256=sha(link.metadata['source_wire']),loader_resolved_is_native_lookup=False,stored_consistent=False,writeback_allowed=False,native_permission=False)
   reports.append(report)
   def blocked(reason):report['status']=reason
   if duplicates[(link.form_id,link.file_copy,link.field_id,link.element_index)]!=1:blocked('duplicate_saved_link_coordinate');continue
   # Source-wide lookup is limited to this saved FormSet, not a runtime vector.
   receiving=[(p,f)for p,f in forms if p[0]==containing_path[0]and f.header.file_copy==link.file_copy]
   if len(receiving)!=1:blocked('saved_receiving_form_missing_or_ambiguous');continue
   path,form=receiving[0];report['receiving_path']=_path(path)
   if _full(form.header.identifier)!=_full(link.form_id):blocked('saved_descriptor_form_ID_mismatch');continue
   if link.metadata.get('source_element_u32')!=link.element_index:blocked('saved_element_U32_has_unmodeled_high_bits');continue
   owner,fields=current(path,form);full=_full(link.field_id);spec=[f for f in fields.fields if f.identifier==full]
   if len(spec)!=1 or spec[0].kind!=22:blocked('current_field_not_declared_kind22');continue
   spec=spec[0]
   try:descriptor=link_field_descriptor(registry,effective_field_links(registry,owner),spec.ordinal)
   except UnsupportedProfile as error:blocked('source2150_lookup_refused');report['detail']=str(error);continue
   report['descriptor2150']=descriptor
   if form.derived_tail is None:blocked('receiving_source_has_no_full_D2');continue
   entries=[e for e in form.derived_tail.field_map.entries if _full(e.identifier)==full]
   if len(entries)!=1:blocked('saved_full_D2_field_ID_missing_or_ambiguous');continue
   source_index=entries[0].source_field_index
   bindings=[b for b in bound.bindings.get(path,())if b.source_field_index==source_index and b.element_index==link.element_index]
   if len(bindings)!=1:blocked('saved_field_value_missing_or_ambiguous');continue
   binding=bindings[0]
   if binding.field_id!=full or binding.current_field_index!=spec.ordinal or binding.source_kind!=22 or binding.source_format!=spec.format:
    blocked('saved_full_D2_current_kind_format_mismatch');continue
   node=find_value(form.hash_state,source_index,link.element_index)
   if node is None:blocked('saved_FV_not_hash_reachable');continue
   report.update(source_field_index=source_index,current_field_index=spec.ordinal,source_FV_raw64=str(node.raw),source_FV_attrs=node.specific_attributes,source_FV_Used=bool(node.specific_attributes&1),source_FV_Override=bool(node.specific_attributes&8),source_FV_header=node.header,source_FV_format=node.flag10,source_FV_flag11=node.flag11,stored_link_copy_number_U16=node.raw&65535)
   if not node.specific_attributes&1:blocked('saved_FV_Used0_not_a_GetLinkedForm_value');continue
   if node.kind_byte!=22 or node.flag10!=spec.format:blocked('saved_FV_kind_format_mismatch');continue
   if bytes.fromhex(descriptor['first_form_id_hex'])!=_full(containing.header.identifier):blocked('source2150_containing_form_ID_mismatch');continue
   candidates=[(p,f)for p,f in forms if p[0]==containing_path[0]and _full(f.header.identifier)==bytes.fromhex(descriptor['first_form_id_hex'])and f.header.word7c==(node.raw&65535)]
   if len(candidates)!=1:blocked('saved_containing_ID_word7c_missing_or_ambiguous');continue
   if candidates[0][0]!=containing_path:blocked('saved_D7_owner_differs_from_FV_copy_number');continue
   report.update(status='consistent_saved_kind22_link',stored_consistent=True,identity_basis='complete saved same-FormSet D7/fullD2/FV/word7c plus same-request2150; not active Form inventory')
 assert captured==_json(request),'Read-only request changed'
 return dict(source_sha256=sha(wire),source_bytes=len(wire),profile_sha256=sha(_json(request['profile'])),ordered_carrier_sha256=[x['sha256']for x in request['carriers']],existing_saved_links=len(reports),stored_consistent_links=sum(x['stored_consistent']for x in reports),links=reports,complete_source_consumed=True,actual_App_context_executed_once=True,source_unchanged=True,comparison_only=True,not_editability_or_tax_completeness_proof=True,writeback_allowed=False,caller_metadata_origin_authenticated=False,saved_document_taxpayer_origin_verified=False,native_inventory_verified=False,native_FindForm_executed=False,native_Load_or_current_FV_verified=False,native_current_copyNum_verified=False,native_RecordUUID_or_FormUUID_association_verified=False,native_link_container_edits=False,native_Override_Used_sideeffects=False)
