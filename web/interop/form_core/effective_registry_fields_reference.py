"""Prepared modern Mac resource registration and effective field selection.

Caller supplies a complete ordered carrier resource map. No filesystem scan,
XPRF decompression, native registry, runtime options, or implicit carrier order
is implemented. Strict ordinary modern metadata guards are independent limits.
Every contributing metadata record and ordered home reference remains retained.
"""
from dataclasses import dataclass,replace
from types import MappingProxyType
from collections.abc import Mapping
from .field_template_reference import load_field_template,UnsupportedProfile

@dataclass(frozen=True)
class Carrier:
    key: bytes
    resources: Mapping

@dataclass(frozen=True)
class HomeReference:
    carrier_key: bytes
    resource_id: int
    metadata_type: int

@dataclass(frozen=True)
class IDRecord:
    source: HomeReference
    strings: tuple[bytes,...]
    source_payload: bytes

@dataclass(frozen=True)
class CompiledForm:
    identifier: bytes
    version: int
    primary: IDRecord|None
    homes: tuple[IDRecord,...]

@dataclass(frozen=True)
class CompiledFormSet:
    identifier: bytes
    version: int
    primary: IDRecord|None
    homes: tuple[IDRecord,...]
    forms: tuple[CompiledForm,...]

@dataclass(frozen=True)
class Registry:
    carriers: tuple[Carrier,...]
    formsets: tuple[CompiledFormSet,...]
    scanned_records: tuple[IDRecord,...]


def fixed_id(value):
    if type(value) is not bytes or not 1<=len(value)<=32 or any(c<33 or c>126 for c in value):
        raise UnsupportedProfile('finite printable modern ID required')
    return value.ljust(32,b' ')


def decimal_u16(value):
    if not value or any(c<48 or c>57 for c in value):raise UnsupportedProfile('ordinary positive decimal version required')
    number=int(value)
    if not 1<=number<=65535:raise UnsupportedProfile('nonzero U16 version required')
    return number


def parse_id_record(payload,source):
    if type(payload) is not bytes or len(payload)<2:raise UnsupportedProfile('complete LE ID payload required')
    count=int.from_bytes(payload[:2],'little');position=2;strings=[]
    for _ in range(count):
        if position>=len(payload):raise UnsupportedProfile('truncated ID string')
        size=payload[position];position+=1
        if position+size>len(payload):raise UnsupportedProfile('truncated ID string')
        strings.append(payload[position:position+size]);position+=size
    if position!=len(payload):raise UnsupportedProfile('unconsumed ID payload')
    return IDRecord(source,tuple(strings),payload)


def scan_carrier(carrier):
    if not isinstance(carrier,Carrier) or type(carrier.key) is not bytes or not carrier.key or not isinstance(carrier.resources,Mapping):
        raise UnsupportedProfile('explicit complete prepared carrier required')
    rid=1;typ=18000;records=[]
    for _ in range(200000):
        key=(typ,rid)
        if key in carrier.resources:
            if not 18000<=typ<19000:raise UnsupportedProfile('11000 or extended native scan path is not implemented')
            records.append(parse_id_record(carrier.resources[key],HomeReference(carrier.key,rid,typ)))
            typ+=1
        elif typ==18000:typ=18500
        elif typ==18500:typ=11000
        elif typ==11000:return tuple(records)
        else:
            rid+=1;typ=18000
            if rid>65535:raise UnsupportedProfile('native RID wrap is not implemented')
    raise UnsupportedProfile('finite prepared scan bound exceeded')


def _modern_format(value):
    # Original ParseVersionString special-cases 2007.5 to 4; otherwise ToUINT32.
    # Strict subset here, no assumption about arbitrary native numeric syntax.
    if value not in (b'4',b'5',b'2007.5'):raise UnsupportedProfile('ordinary compiler format4/5 metadata required')


def register_records(carriers):
    snapshots=[]
    for c in carriers:
        if not isinstance(c,Carrier) or type(c.key) is not bytes or not c.key or not isinstance(c.resources,Mapping):
            raise UnsupportedProfile('complete prepared carrier required')
        resources=dict(c.resources)
        for key,value in resources.items():
            if type(key) is not tuple or len(key)!=2 or any(type(x) is not int or not 0<=x<=65535 for x in key) or type(value) is not bytes:
                raise UnsupportedProfile('U16 resource keys and exact decoded bytes required')
        snapshots.append(Carrier(c.key,MappingProxyType(resources)))
    carriers=tuple(snapshots)
    if len({c.key for c in carriers})!=len(carriers):raise UnsupportedProfile('unique ordered carrier keys required')
    records=tuple(r for c in carriers for r in scan_carrier(c));sets={}
    for record in records:
        typ=record.source.metadata_type;strings=record.strings;is_form=typ<18500
        need=4 if is_form else 2
        if len(strings)<need:raise UnsupportedProfile('insufficient identity/version metadata')
        fsid=fixed_id(strings[1] if is_form else strings[0]);fsversion=decimal_u16(strings[3] if is_form else strings[1])
        previous=sets.get(fsid)
        if previous is None or previous.version<fsversion:
            current=CompiledFormSet(fsid,fsversion,None,(),())
        else:current=previous
        if not is_form and fsversion>=current.version:
            if len(strings)<3:current=replace(current,homes=current.homes+(record,))
            else:
                if len(strings)<9:raise UnsupportedProfile('finite full FormSet metadata requires9 strings')
                _modern_format(strings[7])
                if current.primary is not None:raise UnsupportedProfile('native duplicate FormSet ID data home statusD1')
                current=replace(current,primary=record,homes=(record,)+current.homes)
        if is_form:
            fid=fixed_id(strings[0]);version=decimal_u16(strings[2]);forms={f.identifier:f for f in current.forms};old=forms.get(fid)
            if old is None or old.version<version:form=CompiledForm(fid,version,None,())
            else:form=old
            if version>=form.version:
                if len(strings)<5:form=replace(form,homes=form.homes+(record,))
                else:
                    if len(strings)<19:raise UnsupportedProfile('finite full Form metadata requires19 strings')
                    _modern_format(strings[16]);form=replace(form,primary=record,homes=(record,)+form.homes)
                forms[fid]=form
            current=replace(current,forms=tuple(forms[k] for k in sorted(forms)))
        sets[fsid]=current
    return Registry(carriers,tuple(sets[k] for k in sorted(sets)),records)


def field_template(registry,form,*,template_swap=False):
    resources={c.key:c.resources for c in registry.carriers};selected=[];sources=[]
    for typ in (1900,1901):
        value=None;source=None
        for home in form.homes:
            key=(typ,home.source.resource_id);carrier=resources[home.source.carrier_key]
            if key in carrier:
                value=carrier[key];source=home.source
                if not value:raise UnsupportedProfile('zero-length present attribute is outside selected field profile')
                break
        selected.append(value);sources.append(source)
    return load_field_template(*selected,template_swap=template_swap),tuple(sources)

