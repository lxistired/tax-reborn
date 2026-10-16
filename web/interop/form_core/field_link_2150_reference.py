"""Source-selected complete LE2150/offset0 fields and linked-form descriptors.

No active Lock, native Form vector, FV, FindForm, setter or permission is
constructed. Same-registry object identity and exact complete source bytes are
required. Both ID bytes are retained; the second ID is not assigned a meaning.
"""
from dataclasses import dataclass
import hashlib,struct
from .effective_registry_fields_reference import Registry,CompiledForm,field_template
from .field_template_reference import UnsupportedProfile,read_id
@dataclass(frozen=True)
class LinkFieldRecord:
    field_ordinal:int
    first_id:bytes
    second_id:bytes
    offset:int
    source_wire:bytes
@dataclass(frozen=True)
class LinkFieldBody:
    source_wire:bytes
    records:tuple
@dataclass(frozen=True)
class LinkFieldSource:
    form:object
    source:object
    visited:tuple
    body:object

def parse_body(payload):
    if type(payload)is not bytes or len(payload)<2:raise UnsupportedProfile('Complete LE2150 count and records required')
    count=struct.unpack_from('<H',payload)[0];p=2;rows=[]
    for _ in range(count):
        begin=p
        if p+2>len(payload):raise UnsupportedProfile('Truncated2150 field index')
        ordinal=struct.unpack_from('<H',payload,p)[0];p+=2
        first,p=read_id(payload,p);second,p=read_id(payload,p)
        rows.append(LinkFieldRecord(ordinal,first,second,begin,payload[begin:p]))
    if p!=len(payload):raise UnsupportedProfile('Complete2150 body refuses unconsumed tail')
    return LinkFieldBody(payload,tuple(rows))

def preserve_body(body):
    if type(body)is not LinkFieldBody or parse_body(body.source_wire)!=body:raise UnsupportedProfile('Unmodified complete2150 source body required')
    return body.source_wire

def effective_field_links(registry,form):
    if type(registry)is not Registry or type(form)is not CompiledForm or not any(form is f for fs in registry.formsets for f in fs.forms):raise UnsupportedProfile('Exact same-registry compiled form object required')
    maps={c.key:c.resources for c in registry.carriers};visited=[]
    for home in form.homes:
        s=home.source;visited.append(s)
        if s.carrier_key not in maps:raise UnsupportedProfile('Complete registered source maps required')
        if(2150,s.resource_id)in maps[s.carrier_key]:return LinkFieldSource(form,s,tuple(visited),parse_body(maps[s.carrier_key][2150,s.resource_id]))
    return LinkFieldSource(form,None,tuple(visited),None)

def link_field_descriptor(registry,source,ordinal):
    if type(ordinal)is not int or not 0<ordinal<65536 or type(source)is not LinkFieldSource:raise UnsupportedProfile('Exact existing current U16 field ordinal required')
    # Re-select the source from this exact Registry to prevent detached or
    # cross-form records from borrowing another owner's authority.
    actual=effective_field_links(registry,source.form)
    if actual!=source:raise UnsupportedProfile('Detached or changed2150 source selection')
    fields,_=field_template(registry,source.form);matches=[f for f in fields.fields if f.ordinal==ordinal]
    if len(matches)!=1 or matches[0].kind!=22:raise UnsupportedProfile('Declared currentkind22 field required')
    if source.body is None:raise UnsupportedProfile('Stored attribute absence is not active current defaults')
    # The enum0 loop stops at the first index >= the requested index. It does
    # not scan past a larger index to find a later unsorted duplicate.
    row=next((r for r in source.body.records if r.field_ordinal>=ordinal),None)
    if row is None or row.field_ordinal!=ordinal:raise UnsupportedProfile('No2150 record before native enum0 lookup stop')
    rows=[r for r in source.body.records if r.field_ordinal==ordinal]
    field=matches[0]
    return dict(field_id_hex=field.identifier.hex(),current_ordinal=ordinal,kind=field.kind,compiled_format=field.format,compiled_attributes=field.attributes,first_form_id_hex=row.first_id.hex(),second_id_hex_uninterpreted=row.second_id.hex(),record_offset=row.offset,record_hex=row.source_wire.hex(),body_sha256=hashlib.sha256(source.body.source_wire).hexdigest(),carrier_key_hex=source.source.carrier_key.hex(),RID=source.source.resource_id,metadata_type=source.source.metadata_type,duplicate_field_records=len(rows),selection='enum0 first ordinal >= requested; equality required in same effective Form',native_FindForm_executed=False,native_current_FV_available=False,native_inventory_verified=False,native_permission=False)
