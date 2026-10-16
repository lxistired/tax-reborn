"""Owned UI session binding around the unchanged frozen167 calculation API.

Inspection and calculation are separate user actions. Each action loads one
fresh document context. No source bytes, form nodes or IRS result are mutated.
"""
import base64,hashlib,json
from decimal import Decimal
import binary_tax
import raw_interest_request as fixed
from interop.derived_form.value_hash_wire_reference import find_value
from numeric_current_input_reference import StoredCents,current_numeric_input

_session=None
PROGRAM_SHA=fixed._AUTHORITY['resource']['carrier_sha256']
FIELD_SHA=fixed._AUTHORITY['L8A_field']['carrier_sha256']
LIMITS=[
 'L4 and L8A are bounded interest projections, not final tax, refund or amount owed.',
 'The EE calculation uses the qualified married-filing-separately normal-return invariant.',
 'INPUT10770 uses retained current storage; its upstream aggregation is not freshly run.',
 'ADJUST4263 uses saved adjustments; it is not rebuilt from the new temporary adjustments.',
 'Native inventory, row UUID mapping, dependency queue, TPS output conversion and full F1040 R2 are not run.',
 'This interface cannot write the source or replace the App IRS calculation. Mobile memory has not been validated.'
]

def _fingerprint(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()

def _pair(payload):
 if type(payload)is not dict or set(payload)!={'source','local_resource','field_resource'}:raise ValueError('Exact inspected source and two complete caller-local resource files required')
 fixed._bytes(payload['local_resource'],PROGRAM_SHA)
 supplied=fixed._bytes(payload['field_resource'],FIELD_SHA)
 source=payload['source']
 if type(source)is not dict or source.get('container')!='binary_entity' or source.get('profile_acknowledged')is not True or source.get('profile',{}).get('format')!='tax-reborn-binary-entity-profile-v5':raise ValueError('Inspect an acknowledged complete v5 binary source for this bounded comparison')
 matches=[r for r in source.get('carriers',[])if type(r)is dict and r.get('sha256')==FIELD_SHA]
 if len(matches)!=1 or fixed._bytes(matches[0],FIELD_SHA)!=supplied:raise ValueError('The selected F1040 file must be the exact file already bound in source.carriers')
 return source

def _stored(loaded,path,field):
 doc,buffers,bound,registry,selected,wire=loaded
 form=doc.formsets[path[0]].forms[path[1]];fs=doc.formsets[path[0]]
 fsid=fs.header.identifier.decode('ascii').rstrip(' ');formid=form.header.identifier.decode('ascii').rstrip(' ')
 template=registry.resolve(fsid,formid,selected[(fsid,formid)])
 specs=[s for s in template.fields if s.field_id==field]
 if len(specs)!=1:raise ValueError('Unique current field definition required for inspection')
 spec=specs[0];fid=field.encode().ljust(32,b' ')
 if(spec.kind,spec.format,spec.is_array)not in((11,0,False),(12,0,False)):raise ValueError('Exact ordinary scalar interest field metadata required')
 entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
 if len(entries)>1:raise ValueError('Unique full-ID current field binding required')
 source_index=entries[0].source_field_index if entries else None
 node=None if source_index is None else find_value(form.hash_state,source_index,0)
 bindings=[b for b in bound.bindings.get(tuple(path),())if b.field_id==fid or b.current_field_index==spec.ordinal]
 if len(bindings)>1:raise ValueError('Unique scalar preview source/current binding required')
 value=None;used=False;attrs=None
 if node is not None:
  if node.kind_byte!=spec.kind or node.header!=0 or node.flag10!=0 or node.specific_attributes not in(0,1,2,3,8,9,10,11):raise ValueError('Unsupported stored interest field protocol')
  if len(bindings)!=1:raise ValueError('Reachable scalar preview needs one full-ID binding')
  b=bindings[0]
  if(b.field_id,b.source_field_index,b.current_field_index,b.element_index,b.source_kind,b.source_format,b.fv_attributes)!=(fid,source_index,spec.ordinal,0,node.kind_byte,node.flag10,node.specific_attributes)or b.native_action not in('preserve','requires_additional_scalar_codec','drop_empty_storage'):raise ValueError('Preview source/current full-ID binding differs')
  signed=node.raw if node.raw<1<<63 else node.raw-(1<<64)
  attrs=node.specific_attributes;used=bool(attrs&1)
  if field=='L4':
   if attrs not in(0,1,2,3):raise ValueError('Current L4 prior with Override needs unsupported native exterior assignment')
   amount=current_numeric_input(StoredCents(node.kind_byte,node.raw,attrs,node.header,node.flag10,node.flag11,node.exponent_byte))
   value=None if amount is None else str(amount)
  else:
   if node.flag11 not in(0,204)or abs(signed)>10**9:raise ValueError('Current L8A prior exceeds the fixed field-section protocol')
   if used:value=str(Decimal(signed))
 elif bindings:raise ValueError('Preview bindings without reachable scalar storage refused')
 return dict(field=field,document_path=list(path),document_file_copy_U32=form.header.file_copy,runtime_copy_number_U16=form.header.word7c,current_ordinal=spec.ordinal,source_ordinal=source_index,stored_node_present=node is not None,Used=used,Override=bool((attrs or 0)&8),attributes=attrs,kind=None if node is None else node.kind_byte,value=value,status='stored Used value'if used else'stored Unused value'if node is not None else'storage absent')

def inspect_request(payload):
 global _session
 _session=None
 source=_pair(payload);loaded=binary_tax._context(source)
 doc,buffers,bound,registry,selected,wire=loaded
 if getattr(bound,'document',None)is not doc:raise ValueError('One same-source bound document required')
 summaries=[(fi,i)for fi,fs in enumerate(doc.formsets)for i,f in enumerate(fs.forms)if f.header.identifier.ljust(32,b' ')==b'FSCHB'.ljust(32,b' ')and f.header.parent is None]
 if len(summaries)!=1:raise ValueError('Exactly one root FSCHB source is supported')
 path=summaries[0];targets=[(path[0],i)for i,f in enumerate(doc.formsets[path[0]].forms)if f.header.identifier.ljust(32,b' ')==b'F1040'.ljust(32,b' ')]
 if len(targets)!=1:raise ValueError('Exactly one same-formset existing F1040 source is required')
 target=doc.formsets[path[0]].forms[targets[0][1]]
 if target.header.parent is not None or target.header.word7c!=0:raise ValueError('Root F1040 runtime copy0 is required')
 result=dict(source_sha256=hashlib.sha256(wire).hexdigest(),summary_path=list(path),source_formset_index=path[0],row_number=1,field_id='L1',need_native_row_uuid=False,program_resource_sha256=PROGRAM_SHA,field_resource_sha256=FIELD_SHA,current_fields=[_stored(loaded,path,'L4'),_stored(loaded,targets[0],'L8A')],limitations=LIMITS,binary_context_calls=1,comparison_only=True,writeback_allowed=False,physical_writes=0)
 token=_fingerprint(dict(pair=_fingerprint(payload),inspection=result))
 _session=dict(pair=_fingerprint(payload),selection={k:result[k]for k in('source_sha256','summary_path','source_formset_index','row_number','field_id','need_native_row_uuid')},token=token)
 return dict(inspection_token=token,**result)

def calculate_request(payload):
 if type(payload)is not dict or set(payload)!={'pair','inspection_token','confirmed'}or payload['confirmed']is not True:raise ValueError('Confirm the current same-source inspection before comparison')
 if _session is None or payload['inspection_token']!=_session['token']or _fingerprint(payload['pair'])!=_session['pair']:raise ValueError('Source or resources changed; inspect and confirm them again')
 pair=payload['pair'];selection=_session['selection']
 # The fixed API revalidates both resources and loads the document once.
 request=dict(source=pair['source'],local_resource=pair['local_resource'],expected_source_sha256=selection['source_sha256'],**{k:v for k,v in selection.items()if k!='source_sha256'})
 result=fixed.calculate_request(request)
 return dict(result=result,inspection_token=_session['token'],same_source_inspection_verified=True,comparison_only=True,writeback_allowed=False,physical_writes=0)
