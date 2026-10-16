"""Same-registry ordinary modern TaxML naming descriptors, independently written.

1525/7000/2310/2315 are read from complete verified maps in real home order.
This does not initialize the native registry or certify an active FV inventory,
factory, checksum, writer, setter or source-edit permission. XML and resource
bytes are retained; descriptors do not authorize relocation or serialization.
"""
from dataclasses import dataclass
import hashlib,re,struct
from .effective_registry_fields_reference import Registry,CompiledForm,CompiledFormSet,field_template
from .field_template_reference import UnsupportedProfile

BASE_URL='http://www.intuit.com/Ctg/Pta/TurboTax/'
MAX_RESOURCE=8*1024*1024

@dataclass(frozen=True)
class SelectedAttribute:
    attribute_type:int
    owner:object
    source:object
    payload:object
    visited:tuple

@dataclass(frozen=True)
class MappingEntry:
    key:object
    version:int
    strings:tuple
    normalization:object
    payload_offset:int
    source_bytes:bytes

@dataclass(frozen=True)
class MappingList:
    hidden:bool
    offset_width:int
    entries:tuple
    source_payload:bytes

@dataclass(frozen=True)
class FormSetNames:
    identifier:bytes
    parts:tuple
    element_name:str
    namespace:str
    tps_prefix:str
    cid_formset:str
    parts_source:SelectedAttribute
    cid_source:SelectedAttribute

@dataclass(frozen=True)
class FieldNames:
    form_identifier:bytes
    field_identifier:bytes
    current_ordinal:int
    element_name:str
    hidden:bool
    kind:int
    compiled_format:int
    field_source:object
    mapping_source:SelectedAttribute
    mapping:object
    mapping_found:bool
    lookup_code:int # Local Lock/GetFieldData phase only; outer GetCidMapping returns bool.
    cid_form:str=''
    cid_table:str=''
    cid_field:str=''
    reader_extra:str=''

def select_attribute(registry,owner,attribute_type):
    if type(registry)is not Registry or type(attribute_type)is not int or not 0<=attribute_type<=65535:
        raise UnsupportedProfile('Explicit same-registry attribute request')
    valid=(type(owner)is CompiledFormSet and any(owner is fs for fs in registry.formsets))or(
        type(owner)is CompiledForm and any(owner is f for fs in registry.formsets for f in fs.forms))
    if not valid:raise UnsupportedProfile('Exact same-registry compiled owner identity')
    maps={c.key:c.resources for c in registry.carriers};visited=[]
    for record in owner.homes:
        home=record.source;visited.append(home);key=(attribute_type,home.resource_id)
        if key in maps[home.carrier_key]:
            payload=maps[home.carrier_key][key]
            if type(payload)is not bytes or len(payload)>MAX_RESOURCE:
                raise UnsupportedProfile('Exact bounded decoded attribute bytes')
            return SelectedAttribute(attribute_type,owner,home,payload,tuple(visited))
    return SelectedAttribute(attribute_type,owner,None,None,tuple(visited))

def read_att_string(wire,position):
    if type(wire)is not bytes or not 0<=position<len(wire):raise UnsupportedProfile('Truncated attribute string')
    size=wire[position];position+=1
    if size==255:
        if position+2>len(wire):raise UnsupportedProfile('Truncated extended U16 attribute string')
        size=struct.unpack_from('<H',wire,position)[0];position+=2
    end=position+size
    if end>len(wire):raise UnsupportedProfile('Truncated attribute string body')
    return wire[position:end],end

def parse_string_list(payload):
    if type(payload)is not bytes or not 2<=len(payload)<=MAX_RESOURCE:
        raise UnsupportedProfile('Exact bounded LE string-list attribute')
    count=struct.unpack_from('<H',payload)[0];position=2;strings=[]
    for _ in range(count):value,position=read_att_string(payload,position);strings.append(value)
    if position!=len(payload):raise UnsupportedProfile('Unconsumed string-list bytes')
    return tuple(strings)

def native_id_string(identifier):
    """zpID.GetString exact bytes before first ASCII space among32 bytes.

    It is not rstrip and does not itself stop at NUL. The ordinary XML adapter
    below separately refuses noncanonical/ambiguous IDs instead of losing them.
    """
    if type(identifier)is not bytes or len(identifier)!=32:raise UnsupportedProfile('Exact32-byte zpID')
    return identifier.split(b' ',1)[0]

def _text(value):
    if type(value)is not bytes or any(b<32 or b>126 for b in value):
        raise UnsupportedProfile('Finite printable ASCII metadata; no NUL/encoding normalization')
    return value.decode('ascii')

def _name(value):
    text=_text(value)
    if not re.fullmatch('[A-Za-z_][A-Za-z0-9_.-]{0,255}',text):raise UnsupportedProfile('Finite ordinary XML local name')
    return text

def ordinary_xml_id(identifier):
    token=native_id_string(identifier)
    if token.ljust(32,b' ')!=identifier:raise UnsupportedProfile('Internal-space ID suffix cannot be silently lost')
    return _name(token)

def formset_names(registry,formset):
    parts=select_attribute(registry,formset,1525)
    if parts.payload is None:raise UnsupportedProfile('1525 absent; native runtime FormSetID fallback is not supplied')
    strings=parse_string_list(parts.payload)
    if len(strings)<3:raise UnsupportedProfile('Finite1525 profile requires all three explicit strings')
    prefix=_name(strings[0]);element=_name(strings[1]+strings[2])
    cid=select_attribute(registry,formset,7000)
    if cid.payload is None:cid_name=''
    else:
        values=parse_string_list(cid.payload)
        # Actual getter requests zero-based20 and clears on returned error or
        # exception. A too-short selected list yields the native empty string.
        cid_name=_text(values[20])if len(values)>20 else''
    return FormSetNames(formset.identifier,strings,element,BASE_URL+element,prefix,cid_name,parts,cid)

def parse_mapping_list(payload,*,hidden):
    if type(hidden)is not bool or type(payload)is not bytes or not 2<=len(payload)<=MAX_RESOURCE:
        raise UnsupportedProfile('Exact bounded modern mapping payload and explicit visibility')
    count=struct.unpack_from('<H',payload)[0]
    if count>32767:raise UnsupportedProfile('Finite signed16 native binary-search count')
    if count==0:
        if len(payload)!=2:raise UnsupportedProfile('No trailing empty mapping bytes')
        return MappingList(hidden,0,(),payload)
    if len(payload)<4:raise UnsupportedProfile('Complete adaptive offset table')
    # OffsetTable enum4 is adaptive: native chooses U16 when the first U16
    # offset equals2+count*2, otherwise U32. Width4 is not enum4's fixed width.
    width=2 if struct.unpack_from('<H',payload,2)[0]==2+2*count else 4
    header=2+count*width
    if header>len(payload):raise UnsupportedProfile('Truncated mapping offset table')
    offsets=struct.unpack_from('<'+('H'if width==2 else'I')*count,payload,2)
    if offsets[0]!=header or any(a>=b for a,b in zip(offsets,offsets[1:]))or offsets[-1]>=len(payload):
        raise UnsupportedProfile('Finite exact nonoverlapping offset table, no orphan prefix')
    entries=[];previous=0;seen=set()
    for index,start in enumerate(offsets):
        end=offsets[index+1]if index+1<count else len(payload);record=payload[start:end];p=0
        if hidden:key=None
        else:
            if len(record)<2:raise UnsupportedProfile('Complete mapping field index')
            key=struct.unpack_from('<H',record)[0];p=2
            if not previous<key<=65535:raise UnsupportedProfile('Strictly ordered unique nonzero current field indices')
            previous=key
        if p>=len(record):raise UnsupportedProfile('Complete mapping version')
        version=record[p];p+=1
        if version not in((2,3,4)if hidden else(3,4,5)):
            raise UnsupportedProfile('Only closed modern mapping versions')
        string_count=(5 if version==2 else 6)if hidden else(4 if version==3 else 5)
        strings=[]
        for _ in range(string_count):value,p=read_att_string(record,p);strings.append(value)
        norm=None
        if version>=(4 if hidden else 5):
            if p+2>len(record):raise UnsupportedProfile('Complete mapping normalization word')
            norm=struct.unpack_from('<H',record,p)[0];p+=2
        if p!=len(record):raise UnsupportedProfile('Unconsumed mapping bytes; no unknown tails')
        if hidden:
            key=strings.pop(0)
            if not key or key in seen:raise UnsupportedProfile('Finite unique nonempty hidden field IDs')
            seen.add(key)
        entries.append(MappingEntry(key,version,tuple(strings),norm,start,record))
    return MappingList(hidden,width,tuple(entries),payload)

def field_names(registry,form,field_identifier):
    select_attribute(registry,form,1900) # identity check; actual source below may be hidden1901
    template,sources=field_template(registry,form)
    fields=[f for f in template.fields if f.identifier==field_identifier]
    if len(fields)!=1:raise UnsupportedProfile('Exact unique current full field ID')
    field=fields[0];name=ordinary_xml_id(field.identifier)
    mapping_source=select_attribute(registry,form,2315 if field.hidden else 2310)
    if mapping_source.payload is None:
        entry=None;code=0xca
    else:
        mappings=parse_mapping_list(mapping_source.payload,hidden=field.hidden)
        key=native_id_string(field.identifier)if field.hidden else field.ordinal
        if field.hidden and any(e.key!=key and e.key.lower()==key.lower()for e in mappings.entries):
            raise UnsupportedProfile('Unproven native case comparison must not grant a mismatched hidden mapping')
        entry=next((e for e in mappings.entries if e.key==key),None)
        code=0 if entry is not None or field.hidden else 0xc8
    values=tuple(_text(value)for value in entry.strings[:4])if entry else('','','','')
    return FieldNames(form.identifier,field.identifier,field.ordinal,name,field.hidden,field.kind,field.format,
        sources[1 if field.hidden else 0],mapping_source,entry,entry is not None,code,*values)

def source_report(selected):
    if type(selected)is not SelectedAttribute:raise UnsupportedProfile('Selected attribute required')
    def home(h):return dict(carrier_key_hex=h.carrier_key.hex(),resource_id=h.resource_id,metadata_type=h.metadata_type)
    return dict(attribute_type=selected.attribute_type,source=home(selected.source)if selected.source else None,
        visited_homes=[home(h)for h in selected.visited],bytes=len(selected.payload)if selected.payload is not None else None,
        sha256=hashlib.sha256(selected.payload).hexdigest()if selected.payload is not None else None,
        active_native_cache=False,native_factory_acceptance=False,source_edit_permission=False)
