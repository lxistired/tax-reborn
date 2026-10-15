"""Independent read-only, source-bound shape for current Windows TaxML.

This is not a general native importer or an original-program acceptance result.
Every caller must explicitly bind the formset header and field metadata to its
owned registry. This reader records that supplied binding; the App must validate
its XPRF bytes independently before offering reviewed candidates. Unknown data
stays unresolved, source bytes stay intact, and no tax values are overwritten.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import datetime
import hashlib
import re
import uuid
import xml.etree.ElementTree as ET

BASE = 'http://www.intuit.com/Ctg/Pta/TurboTax/'
ROOT = '{'+BASE+'TaxReturns}TaxReturns'
TD = BASE+'TaxDataType'
PO = BASE+'PersistentObjects'
CURRENT_ENGINE_VERSION = '9.15.0'
BOX_FIELDS = ((1,'WAGES'),(2,'FEDTAX'),(3,'SSWAGES'),(4,'SSTAX'),(5,'MEDWAGES'),(6,'MEDTAX'))
TYPE = {4:'date',7:'text',8:'ssn',11:'cent',12:'dollar'}
FORMSET_HEADERS = frozenset({'tpsType','tpsSubType','cidFormSet','checksum','dataVersion','sharedForAllDataVersion','sharedForFSDataVersion','formsetAttribute','showSmartWorksheets','implementationVersion','uuid'})
FLAGS = frozenset({'roundedUp','roundedDown','ccToken','approx','valueAlias','valueAliasChgOK','error','used','computed','converted','override','itemized','dropAssigned','generalImport','computedExternally','convFromState','autoBlanked','fixedAssetImport','fieldNote','calcDefault','spouseAmount','jointAmount','clientEntered','isTainted'})
NCNAME = re.compile(r'[A-Za-z_][A-Za-z0-9_.-]{0,63}\Z')
MONEY = re.compile(r'-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,2})?\Z')
HASH = re.compile(r'[a-f0-9]{64}\Z')
MAX_BYTES = 8*1024*1024

class NativeWireError(ValueError):
    pass

def qname(name):
    if not isinstance(name,str) or not NCNAME.fullmatch(name):raise NativeWireError('unbound XML name')
    return '{'+BASE+name+'}'+name

@dataclass(frozen=True)
class FieldBinding:
    name: str
    metadata_kind: int
    metadata_format: int = 0

    def expected_headers(self):
        if not NCNAME.fullmatch(self.name) or len(self.name)>32 or self.metadata_kind not in TYPE:raise NativeWireError('unsupported metadata binding')
        if self.metadata_format == 0:
            subtype='any' if self.metadata_kind==7 else 'normal' if self.metadata_kind==8 else 'default'
        elif self.metadata_kind==4 and self.metadata_format==14:
            subtype='mmddyyyySlashesNonTaintable'
        else:raise NativeWireError('metadata format outside source-bound subset')
        return {'tpsType':TYPE[self.metadata_kind],'tpsSubType':subtype}

@dataclass(frozen=True)
class Profile:
    entity_name: str
    tax_year: int
    formset_name: str
    formset_headers: tuple[tuple[str,str],...]
    form_name: str
    fields: tuple[FieldBinding,...]
    owned_registry_sha256: str

    def validate(self):
        qname(self.entity_name);qname(self.formset_name)
        if not NCNAME.fullmatch(self.form_name) or len(self.form_name)>32 or type(self.tax_year) is not int or not 1800<=self.tax_year<=9999:raise NativeWireError('invalid profile identity')
        if not HASH.fullmatch(self.owned_registry_sha256):raise NativeWireError('explicit owned-registry binding required')
        headers=dict(self.formset_headers)
        if len(headers)!=len(self.formset_headers) or set(headers)-FORMSET_HEADERS or headers.get('tpsType')!='formset' or any(type(k) is not str or type(v) is not str for k,v in self.formset_headers):raise NativeWireError('invalid exact formset headers')
        if not {'tpsSubType','checksum','dataVersion','formsetAttribute','implementationVersion'}<=set(headers):raise NativeWireError('incomplete explicit formset header profile')
        if len({x.name for x in self.fields})!=len(self.fields):raise NativeWireError('duplicate field bindings')
        for x in self.fields:x.expected_headers()
        return self

@dataclass(frozen=True)
class FieldFact:
    field_name: str
    metadata_kind: int
    metadata_format: int
    wire_text: str
    raw_field_attrs: tuple[tuple[str,str],...]
    raw_value_attrs: tuple[tuple[str,str],...]
    parsed_decimal: Decimal | None
    parsed_iso_date: str | None
    unresolved: tuple[str,...]

@dataclass(frozen=True)
class FormFacts:
    owner: tuple[tuple[str,str],...]
    raw_form_attrs: tuple[tuple[str,str],...]
    fields: tuple[FieldFact,...]
    unresolved: tuple[str,...]

@dataclass(frozen=True)
class NativeBook:
    source: bytes = field(repr=False)
    source_sha256: str
    supplied_registry_sha256: str
    forms: tuple[FormFacts,...]
    unresolved: tuple[str,...]

    def original_bytes(self):
        if hashlib.sha256(self.source).hexdigest()!=self.source_sha256:raise NativeWireError('source identity changed')
        return self.source

    def w2_review_candidates(self, *, validated_registry_sha256):
        # The caller must actually validate owned XPRF bytes separately, not just
        # repeat an untrusted XML/header hash. This API offers review-only facts.
        if validated_registry_sha256!=self.supplied_registry_sha256:raise NativeWireError('App registry verification context does not match')
        if self.unresolved:return ()
        out=[]
        for f in self.forms:
            if f.unresolved or any(x.unresolved for x in f.fields) or dict(f.owner).get('form_name')!='FW2':continue
            fields={x.field_name:x for x in f.fields};boxes=[]
            for box,name in BOX_FIELDS:
                x=fields.get(name)
                if x is None or x.unresolved or x.metadata_kind!=11 or x.parsed_decimal is None:break
                boxes.append({'box':box,'field_id':name,'wire_text':x.wire_text,'amount_dollars':str(x.parsed_decimal),'original_kind':11,'raw_field_attrs':dict(x.raw_field_attrs),'raw_value_attrs':dict(x.raw_value_attrs)})
            else:out.append({'source_sha256':self.source_sha256,'source_owner':dict(f.owner),'boxes':boxes,'requires_review':True,'automatic_tax_overwrite':False,'native_acceptance_verified':False})
        return tuple(out)

def _xml(data):
    if not isinstance(data,bytes) or len(data)>MAX_BYTES:raise NativeWireError('bounded UTF8 bytes required')
    try:text=data.decode('utf-8-sig')
    except UnicodeDecodeError:raise NativeWireError('unsupported XML encoding') from None
    if '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise NativeWireError('DTD/entity/NUL unsupported')
    m=re.match(r'^\s*<\?xml\b([^?]*)\?>',text)
    if m:
        enc=re.search(r'encoding\s*=\s*[\'"]([^\'"]+)[\'"]',m[1],re.I)
        if enc and enc[1].lower() not in ('utf-8','utf8'):raise NativeWireError('nonUTF8 XML declaration')
    try:root=ET.fromstring(text,parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True,insert_pis=True)))
    except ET.ParseError:raise NativeWireError('invalid XML') from None
    nodes=0;stack=[(root,1)]
    while stack:
        e,depth=stack.pop();nodes+=1
        if nodes>100000 or depth>128:raise NativeWireError('XML depth/node bound exceeded')
        stack.extend((c,depth+1) for c in e)
    return root

def _integer(attrs,key,default=0):
    value=attrs.get(key,str(default))
    if not re.fullmatch(r'[0-9]{1,10}',value):raise NativeWireError('unsupported copy/ordering integer')
    result=int(value)
    if result>(0xffffffff if key=='fileCopyNum' else 0xffff):raise NativeWireError('copy/ordering range exceeded')
    return str(result)

def _read_field(e,binding,namespace):
    problems=[];value_attrs={};text='';decimal=None;date=None
    if e.tag!='{'+namespace+'}'+binding.name:problems.append('foreign_field_namespace')
    if e.attrib!=binding.expected_headers():problems.append('unbound_field_header')
    children=list(e)
    if len(children)!=1 or children[0].tag!='{'+TD+'}value':problems.append('unbound_nested_value_or_alias')
    else:
        v=children[0];value_attrs=dict(v.attrib);text=v.text or ''
        if list(v):problems.append('nested_value_content')
        if e.text and e.text.strip():problems.append('mixed_field_text')
        if v.tail and v.tail.strip():problems.append('mixed_value_tail')
        if any(k not in FLAGS for k in value_attrs):problems.append('unknown_value_attributes')
        if any(x not in ('true','false') for x in value_attrs.values()):problems.append('unsupported_boolean_lexical')
        if value_attrs.get('used')=='false':problems.append('unused_value')
        # Keep every source attr. True flags need explicit semantic review before
        # this bounded subset offers a complete six-box candidate.
        if any(val=='true' and key!='used' for key,val in value_attrs.items()):problems.append('nondefault_value_flags_require_review')
        if binding.metadata_kind in (11,12):
            if MONEY.fullmatch(text):
                try:
                    decimal=Decimal(text)
                    if binding.metadata_kind==12 and decimal!=decimal.to_integral_value():problems.append('fractional_dollar_kind_requires_review')
                except InvalidOperation:problems.append('invalid_amount')
            else:problems.append('unsupported_amount_text')
        elif binding.metadata_kind==4:
            try:
                if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',text):raise ValueError()
                dt=datetime.date.fromisoformat(text)
                if not 1800<=dt.year<=9999:raise ValueError()
                date=text
            except ValueError:problems.append('unsupported_date_wire')
    return FieldFact(binding.name,binding.metadata_kind,binding.metadata_format,text,tuple(e.attrib.items()),tuple(value_attrs.items()),decimal,date,tuple(problems))

def read_native_taxml(data,profile):
    return read_native_taxml_profiles(data,(profile,))

def read_native_taxml_profiles(data,profiles):
    """Read several explicitly bound form types in one shared XML context.

    Each form has its own registry and fields. Unknown siblings remain global
    blockers; matching copy numbers on different form types do not alias.
    """
    if not isinstance(profiles,(tuple,list)) or not 1<=len(profiles)<=100:raise NativeWireError('bounded explicit form profiles required')
    for item in profiles:item.validate()
    profile=profiles[0]
    context=(profile.entity_name,profile.tax_year,profile.formset_name,dict(profile.formset_headers))
    if any((p.entity_name,p.tax_year,p.formset_name,dict(p.formset_headers))!=context for p in profiles):raise NativeWireError('mixed unbound XML contexts')
    by_name={p.form_name:p for p in profiles}
    if len(by_name)!=len(profiles):raise NativeWireError('ambiguous form profile identity')
    registry_hash=profile.owned_registry_sha256 if len(profiles)==1 else hashlib.sha256('\n'.join(p.form_name+':'+p.owned_registry_sha256 for p in sorted(profiles,key=lambda p:p.form_name)).encode()).hexdigest()
    root=_xml(data);problems=[];forms=[];identities=set();entity_ids=set()
    if root.tag!=ROOT or root.attrib:return NativeBook(data,hashlib.sha256(data).hexdigest(),registry_hash,(),('unbound_root',))
    if root.text and root.text.strip():problems.append('mixed_root_text')
    fs_uri=BASE+profile.formset_name
    for entity in root:
        if entity.tag!=qname(profile.entity_name):problems.append('unbound_entity_namespace_or_type');continue
        if set(entity.attrib)!={'taxYear','uuid','tpsEngineVersion'} or entity.attrib.get('taxYear')!=str(profile.tax_year) or entity.attrib.get('tpsEngineVersion')!=CURRENT_ENGINE_VERSION:problems.append('unbound_entity_header');continue
        if (entity.text and entity.text.strip()) or (entity.tail and entity.tail.strip()):problems.append('mixed_entity_text')
        uid=entity.attrib['uuid']
        try:canonical=str(uuid.UUID(uid))
        except ValueError:problems.append('unbound_entity_uuid');continue
        if canonical in entity_ids:problems.append('duplicate_entity_uuid')
        entity_ids.add(canonical)
        for fs in entity:
            if fs.tag!=qname(profile.formset_name) or fs.attrib!=dict(profile.formset_headers):problems.append('unbound_formset_context');continue
            if (fs.text and fs.text.strip()) or (fs.tail and fs.tail.strip()):problems.append('mixed_formset_text')
            for form in fs:
                pending=[];attrs=dict(form.attrib)
                if (form.text and form.text.strip()) or (form.tail and form.tail.strip()):pending.append('mixed_form_text')
                form_profile=next((p for p in profiles if form.tag=='{'+fs_uri+'}'+p.form_name),None)
                if form_profile is None:problems.append('unmapped_form_or_namespace');continue
                bindings={x.name:x for x in form_profile.fields}
                if attrs.get('tpsType')!='form' or set(attrs)-{'tpsType','copyNum','fileCopyNum','porIndex'} or not {'fileCopyNum','porIndex'}<=set(attrs):pending.append('unbound_form_header')
                try:copy=_integer(attrs,'copyNum');filecopy=_integer(attrs,'fileCopyNum');order=_integer(attrs,'porIndex')
                except NativeWireError:pending.append('bad_copy_header');copy=filecopy=order='unresolved'
                key=(canonical,profile.formset_name,form_profile.form_name,copy,filecopy)
                if key in identities:problems.append('duplicate_form_copy_identity')
                identities.add(key)
                # Same logical copy but differing fileCopyNum remains ambiguous.
                if any(k[:4]==key[:4] and k[4]!=key[4] for k in identities):problems.append('ambiguous_file_copy_identity')
                facts=[];seen=set()
                for e in form:
                    if e.tail and e.tail.strip():pending.append('mixed_field_scope_tail')
                    if not isinstance(e.tag,str):pending.append('opaque_comment_or_instruction');continue
                    local=e.tag.rsplit('}',1)[-1];binding=bindings.get(local)
                    if binding is None:pending.append('unmapped_field_or_record');continue
                    if local in seen:pending.append('duplicate_field_identity')
                    seen.add(local);facts.append(_read_field(e,binding,fs_uri))
                owner=(('entity_uuid',canonical),('tax_year',str(profile.tax_year)),('formset_name',profile.formset_name),('form_name',form_profile.form_name),('copyNum',copy),('fileCopyNum',filecopy),('porIndex',order))
                forms.append(FormFacts(owner,tuple(attrs.items()),tuple(facts),tuple(pending)))
    if not forms:problems.append('no_bound_forms')
    return NativeBook(data,hashlib.sha256(data).hexdigest(),registry_hash,tuple(forms),tuple(dict.fromkeys(problems)))
