"""Finite Mac-shaped monetary XML reader and exact text patch, independently written.

Names and CID mappings come from the same verified decoded registry. Envelope
attributes and present form copies remain explicit caller-owned context. This
does not create native forms, infer missing/default values, run a native factory
or accept the default encrypted PersistenceContainer. Other field kinds,
itemization, PII assessment, linked values and persistent XML objects are not
silently replaced by empty structures.
"""
from dataclasses import dataclass
from decimal import Decimal
import hashlib,re
from xml.parsers import expat
from .native_taxml_names_reference import (
    field_names,formset_names,field_template,ordinary_xml_id,source_report,BASE_URL,
)
from .field_template_reference import UnsupportedProfile
from .taxml_money_reference import MoneyValue,render_taxml_money
from .native_document_filter_reference import selected_filter
from .native_taxml_decimal_reference import render_dec1,parse_dec1

TD=BASE_URL+'TaxDataType'
ROOT=BASE_URL+'TaxReturns'
MAX_BYTES=8*1024*1024
_NAME=re.compile(r'[A-Za-z_][A-Za-z0-9_.-]{0,255}\Z')
_CENT=re.compile(r'-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,2})?\Z')
_DOLLAR=re.compile(r'-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{0,2})?\Z')

@dataclass(frozen=True)
class FormContext:
    compiled_form:object
    attributes:tuple
    # Present allowed fields, by complete32-byte ID. No allocated/current node
    # or absent wire field is inferred from this list.
    field_ids:tuple

@dataclass(frozen=True)
class FormSetContext:
    compiled_formset:object
    attributes:tuple
    forms:tuple

@dataclass(frozen=True)
class EntityContext:
    element_name:str
    attributes:tuple
    formsets:tuple

@dataclass(frozen=True)
class MoneyField:
    key:tuple
    current_ordinal:int
    kind:int
    text:str
    amount:Decimal
    attributes:tuple
    value_attributes:tuple
    text_start:int
    text_end:int
    can_edit:bool
    unresolved:tuple
    field_metadata_source:object
    mapping_source:object

@dataclass(frozen=True)
class MoneyDocument:
    source_bytes:bytes
    source_sha256:str
    registry:object
    contexts:tuple
    fields:tuple
    filter_profile:str='null_filter'

class _Node:
    def __init__(self,name,attrs,start,open_end):
        self.name=name;self.attrs=attrs;self.start=start;self.open_end=open_end
        self.end_start=None;self.end=None;self.children=[];self.text=''

def _fail(reason):raise UnsupportedProfile(reason)

def _attrs(values,allowed,required):
    if type(values)is not tuple or any(type(x)is not tuple or len(x)!=2 or
       any(type(v)is not str for v in x) for x in values):_fail('Explicit immutable header pairs required')
    d=dict(values)
    if len(d)!=len(values) or not required<=d.keys() or not d.keys()<=allowed:
        _fail('Unknown or missing finite Mac TaxML envelope attribute')
    if any('\0'in k or '\0'in v for k,v in values):_fail('NUL in explicit envelope')
    return d

def _unsigned(text,maximum):
    return type(text)is str and re.fullmatch(r'0|[1-9][0-9]{0,9}',text)is not None and int(text)<=maximum

def _end_tag(wire,start):
    # Expat has validated the token; this bounded scan only locates its exact
    # closing byte. Quoted greater-than bytes cannot terminate a start tag.
    quote=None
    for i in range(start,len(wire)):
        b=wire[i]
        if quote:
            if b==quote:quote=None
        elif b in (34,39):quote=b
        elif b==62:return i+1
    _fail('Unterminated XML token')

def _parse(wire):
    if type(wire)is not bytes or not 0<len(wire)<=MAX_BYTES:_fail('Bounded exact UTF8 XML bytes required')
    try:text=wire.decode('utf-8-sig')
    except UnicodeDecodeError:_fail('Unsupported XML encoding')
    if '\0'in text or re.search(r'<!\s*(?:DOCTYPE|ENTITY)',text,re.I):_fail('DTD/entity declarations refused')
    d=re.match(r'\s*<\?xml\s+[^?]*encoding\s*=\s*[\'"]([^\'"]+)',text,re.I)
    if d and d[1].lower() not in ('utf-8','utf8'):_fail('Only explicit UTF8 XML')
    p=expat.ParserCreate(namespace_separator=' ');stack=[];roots=[]
    def start(name,attrs):
        at=p.CurrentByteIndex;node=_Node(name,dict(attrs),at,_end_tag(wire,at))
        if stack:stack[-1].children.append(node)
        else:roots.append(node)
        stack.append(node)
        if len(stack)>8:_fail('Unmodeled nested TaxML context')
    def end(name):
        node=stack.pop();at=p.CurrentByteIndex
        if wire[node.open_end-2:node.open_end]==b'/>':_fail('Finite profile requires explicit end tags')
        node.end_start=at;node.end=_end_tag(wire,at)
    def chars(value):
        if stack:stack[-1].text+=value
    def reject(*args):_fail('DTD/entity/CDATA construct refused in finite monetary XML')
    p.StartElementHandler=start;p.EndElementHandler=end;p.CharacterDataHandler=chars
    p.StartDoctypeDeclHandler=reject;p.EntityDeclHandler=reject
    p.ExternalEntityRefHandler=reject;p.StartCdataSectionHandler=reject
    try:p.Parse(wire,True)
    except expat.ExpatError as e:_fail('Invalid XML: '+str(e))
    if stack or len(roots)!=1:_fail('One complete XML root required')
    return roots[0]

def _structural(node,name,attrs):
    if node.name!=name or node.attrs!=attrs or node.text.strip():
        _fail('Unbound Mac TaxML envelope name, attributes or structural text')

def monetary_field_attributes(names):
    """Actual ordinary unfiltered FieldNameReader attributes, format0 only.

    PII/cache/filter suppliers remain outside this helper. An isPII attribute
    is refused by this profile rather than being manufactured from a callback.
    """
    if names.kind not in (11,12,13) or names.compiled_format!=0:
        _fail('Only current metadata cent/dollar/dec1 format0 is source-bound here')
    out={'tpsType':{11:'cent',12:'dollar',13:'dec1'}[names.kind],'tpsSubType':'default'}
    for key,value in [('cidForm',names.cid_form),('cidTable',names.cid_table),('cidField',names.cid_field)]:
        if value:out[key]=value
    return out

def load_money_document(wire,registry,contexts,*,filter_profile='null_filter'):
    """Read all bytes in the explicitly selected ordinary Mac XML subset.

    Caller supplies exact envelope facts and copied-form inventory, not field
    ordinals/types/CID strings. The latter always derive from the same registry.
    Unknown XML objects or attributes block this finite operation globally.
    """
    policy=selected_filter(filter_profile)
    if filter_profile=='sanitizer_filter':_fail('Sanitized field/default semantics remain outside this monetary source profile')
    if type(contexts)is not tuple or not contexts:_fail('Explicit entity contexts required')
    root=_parse(wire);_structural(root,ROOT+' TaxReturns',{})
    if len(root.children)!=len(contexts):_fail('Unbound entity count')
    fields=[];keys=set();entity_ids=set()
    for ei,(entity,ec)in enumerate(zip(root.children,contexts)):
        if type(ec)is not EntityContext or not _NAME.fullmatch(ec.element_name):_fail('Explicit ordinary entity name required')
        ea=_attrs(ec.attributes,{'taxYear','uuid','tpsEngineVersion'},{'taxYear','uuid','tpsEngineVersion'})
        if ea['tpsEngineVersion']!='9.15.0':_fail('Actual fixed native engine-version text required by this profile')
        if ea['uuid']in entity_ids:_fail('Duplicate entity UUID context')
        entity_ids.add(ea['uuid']);_structural(entity,BASE_URL+ec.element_name+' '+ec.element_name,ea)
        if len(entity.children)!=len(ec.formsets):_fail('Unbound FormSet inventory')
        fs_ids=set()
        for fsnode,fsc in zip(entity.children,ec.formsets):
            if type(fsc)is not FormSetContext:_fail('Explicit FormSet context required')
            fs=fsc.compiled_formset;names=formset_names(registry,fs)
            if fs.identifier in fs_ids:_fail('Duplicate FormSet context')
            fs_ids.add(fs.identifier)
            fa=_attrs(fsc.attributes,{'checksum','dataVersion','sharedForAllDataVersion','sharedForFSDataVersion','formsetAttribute','showSmartWorksheets','implementationVersion','uuid'},{'checksum','dataVersion','formsetAttribute','showSmartWorksheets','implementationVersion'})
            if not _unsigned(fa['formsetAttribute'],65535)or fa['showSmartWorksheets']not in ('true','false'):
                _fail('Exact U16 FormSet attributes and ordinary boolean text required')
            fa.update({'tpsType':'formset','tpsPrefix':names.tps_prefix})
            if names.cid_formset:fa['cidFormSet']=names.cid_formset
            _structural(fsnode,names.namespace+' '+names.element_name,fa)
            if len(fsnode.children)!=len(fsc.forms):_fail('Unbound form-copy inventory')
            copies=set()
            for formnode,fc in zip(fsnode.children,fsc.forms):
                if type(fc)is not FormContext or not any(fc.compiled_form is f for f in fs.forms):_fail('Exact same-registry FormSet member required')
                form=fc.compiled_form;name=ordinary_xml_id(form.identifier)
                ha=_attrs(fc.attributes,{'copyNum','fileCopyNum','porIndex','formCopyAttributes','uuid'},{'fileCopyNum','porIndex'})
                if not _unsigned(ha['fileCopyNum'],0xffffffff):_fail('Exact U32 file-copy identity required')
                if any(k in ha and not _unsigned(ha[k],65535)for k in ('copyNum','porIndex','formCopyAttributes')):
                    _fail('Exact U16 form-copy header fields required')
                identity=(form.identifier,int(ha['fileCopyNum']))
                if identity in copies:_fail('Duplicate form/file-copy context')
                copies.add(identity);ha['tpsType']='form';_structural(formnode,names.namespace+' '+name,ha)
                if type(fc.field_ids)is not tuple or len(set(fc.field_ids))!=len(fc.field_ids):_fail('Unique full field IDs required')
                template,_=field_template(registry,form)
                declared={f.identifier:f for f in template.fields}
                bindings={}
                for fid in fc.field_ids:
                    n=field_names(registry,form,fid);bindings[n.element_name]=n
                seen=set()
                for fn in formnode.children:
                    label=fn.name.removeprefix(names.namespace+' ')
                    if fn.name!=names.namespace+' '+label or label not in bindings or label in seen:_fail('Unbound or duplicate field element')
                    seen.add(label);n=bindings[label]
                    if declared[n.field_identifier].attributes!=0:
                        _fail('Selected ordinary scalar metadata attributes must be zero; native pass excludes bit0x40')
                    attrs=monetary_field_attributes(n)
                    if policy is not None and policy.debug_slot_return:
                        attrs.update({'field':str(n.current_ordinal),'elem':'0'})
                    _structural(fn,names.namespace+' '+n.element_name,attrs)
                    if len(fn.children)!=1:_fail('Itemization, aliases or attached child readers require separate context')
                    v=fn.children[0]
                    if v.name!=TD+' value'or v.children:_fail('Only ordinary monetary td:value supported')
                    # Source Used0 remains an explicit stored field, with no
                    # current-value or edit permission. Other flags need their
                    # own runtime semantics and block this selected profile.
                    if v.attrs not in ({},{'used':'false'}):_fail('Nonordinary value flags or change-data require separate context')
                    rx=_CENT if n.kind==11 else _DOLLAR
                    if n.kind==13:parse_dec1(v.text)
                    elif not rx.fullmatch(v.text):_fail('Unsupported exact monetary text')
                    amount=Decimal(v.text)
                    if n.kind==12 and amount!=amount.to_integral_value():_fail('Fractional whole-dollar value')
                    if n.kind!=13 and abs(amount)>Decimal(10**9):_fail('Selected finite ordinary currency bound exceeded')
                    raw=wire[v.open_end:v.end_start]
                    if raw!=v.text.encode('ascii'):_fail('Escaped, commented or normalized monetary text cannot be patched')
                    key=(ea['uuid'],fs.identifier,form.identifier,int(ha['fileCopyNum']),n.field_identifier)
                    if key in keys:_fail('Duplicate complete monetary field identity')
                    keys.add(key);unused=v.attrs.get('used')=='false'
                    fields.append(MoneyField(key,n.current_ordinal,n.kind,v.text,amount,tuple(fn.attrs.items()),tuple(v.attrs.items()),v.open_end,v.end_start,not unused,('unused_value',)if unused else(),n.field_source,source_report(n.mapping_source)))
    return MoneyDocument(wire,hashlib.sha256(wire).hexdigest(),registry,contexts,tuple(fields),filter_profile)

def patch_money_document(document,key,new_coefficient):
    """One existing ordinary value, exact other bytes, complete guarded reparse."""
    if type(document)is not MoneyDocument:_fail('Loaded finite monetary document required')
    if hashlib.sha256(document.source_bytes).hexdigest()!=document.source_sha256:_fail('Changed source identity')
    checked=load_money_document(document.source_bytes,document.registry,document.contexts,filter_profile=document.filter_profile)
    matches=[f for f in checked.fields if f.key==key]
    if len(matches)!=1 or not matches[0].can_edit:_fail('One existing Used1 ordinary monetary field required')
    field=matches[0];text=render_dec1(new_coefficient)if field.kind==13 else render_taxml_money(MoneyValue(field.kind,new_coefficient))
    corrected=document.source_bytes[:field.text_start]+text.encode('ascii')+document.source_bytes[field.text_end:]
    reopened=load_money_document(corrected,document.registry,document.contexts,filter_profile=document.filter_profile)
    expected=[(f.key,text if f.key==key else f.text,f.attributes,f.value_attributes)for f in checked.fields]
    actual=[(f.key,f.text,f.attributes,f.value_attributes)for f in reopened.fields]
    if actual!=expected:_fail('Complete monetary XML readback differs outside selected text')
    return corrected,reopened
