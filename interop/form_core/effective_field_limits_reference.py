"""Actual2160 supplier over the same explicit effective registry as26.

Modern MacLE/cache-empty/complete decoded resource maps only. It does not assert
active native attribute-cache/initialization state, and missing2160 is never a
general App source-invalid decision. Original ordinary missing-key export guards
and90 unknown author/receiver boundaries remain outside this read-only module.
"""
from dataclasses import dataclass
import struct,hashlib
from .effective_registry_fields_reference import Registry,CompiledForm,field_template
from .field_template_reference import UnsupportedProfile
from .field_limits_body_reference import decode_field_limits,check_kind13_bounds

ATTRIBUTE_TYPE=2160

@dataclass(frozen=True)
class LimitHome:
    carrier_key:bytes
    resource_id:int
    metadata_type:object=None


@dataclass(frozen=True)
class LimitEntry:
    current_field_index:int
    body:bytes
    payload_offset:int
    limits:object

@dataclass(frozen=True)
class LimitLookup:
    resource_present:bool
    entry:object
    get_field_data_code:object
    cache_empty_lock_code:int
    cache_empty_CheckBounds_call_code:int
    source_validity_decision:object=None
    native_active_cache_verified:bool=False

@dataclass(frozen=True)
class EffectiveFieldLimits:
    form:object
    source:object
    payload:object
    entries:tuple
    def lookup(self,current_field_index):
        if type(current_field_index)is not int or not 1<=current_field_index<=65535:
            raise UnsupportedProfile('Explicit nonzero U16 current field index')
        if self.payload is None:
            # Specific cache-empty generic GetMajor profile only. No claim about
            # native preloaded defaults/cache or source validity is made here.
            return LimitLookup(False,None,None,0xca,0xca)
        lo=0;hi=len(self.entries)-1
        while lo<=hi:
            mid=(lo+hi)//2;entry=self.entries[mid]
            if entry.current_field_index==current_field_index:return LimitLookup(True,entry,0,0,0)
            if entry.current_field_index<current_field_index:lo=mid+1
            else:hi=mid-1
        # Real present list, including count0. Field missC8 is cleared by
        # CheckBounds; it is distinct from total attribute absence/LockCA.
        return LimitLookup(True,None,0xc8,0,0)

@dataclass(frozen=True)
class CurrentBoundsResult:
    state:str
    current_field_index:int
    lookup:object
    validation_error:object
    call_error:object
    source_validity_decision:object=None
    native_execution_count:int=0
    complete_CheckValueForErrors:bool=False

def parse_field_limits_payload(payload):
    if type(payload)is not bytes or len(payload)<2:raise UnsupportedProfile('Complete2160 LE count and entries')
    count=struct.unpack_from('<H',payload)[0]
    # Native binary search stores low/high as signed16; this selected ordinary
    # profile rejects32768+ to prevent an overflowing upper-end missing lookup.
    if count>32767:raise UnsupportedProfile('Finite signed16 binary-search count profile')
    if len(payload)!=2+14*count:raise UnsupportedProfile('Exact2160 count*(U16 field+12B body), no truncation/tail')
    entries=[];previous=0
    for index in range(count):
        p=2+14*index;field=struct.unpack_from('<H',payload,p)[0];body=payload[p+2:p+14]
        if field<=previous:raise UnsupportedProfile('Finite nonzero strictly ordered unique field indices')
        previous=field;entries.append(LimitEntry(field,body,p+2,decode_field_limits(body)))
    return tuple(entries)

def effective_field_limits(registry,form):
    if not isinstance(registry,Registry)or not isinstance(form,CompiledForm):
        raise UnsupportedProfile('Explicit modern effective registry and compiled form')
    if not any(form is candidate for fs in registry.formsets for candidate in fs.forms):
        raise UnsupportedProfile('Exact same effective registry snapshot form identity')
    resources={c.key:c.resources for c in registry.carriers}
    homes=tuple(LimitHome(h.source.carrier_key,h.source.resource_id,h.source.metadata_type)for h in form.homes)
    return select_field_limits_from_homes(homes,resources,form_identity=form)

def select_field_limits_from_homes(ordered_homes,complete_resource_maps,*,form_identity):
    """Trusted ordered-datahome adapter; maps must already be fully verified.

    Callers bind the form identity and all carrier/source hashes externally.
    Native active-cache/deferred/error states are still outside this subset.
    No scanner order, RID or missing resource is guessed by this interface.
    """
    from collections.abc import Mapping
    if type(ordered_homes)is not tuple or not isinstance(complete_resource_maps,Mapping):
        raise UnsupportedProfile('Explicit immutable ordered homes and complete trusted decoded maps')
    for home in ordered_homes:
        if not isinstance(home,LimitHome)or type(home.carrier_key)is not bytes or not home.carrier_key or type(home.resource_id)is not int or not 0<=home.resource_id<=65535:
            raise UnsupportedProfile('Exact declared carrier key and U16 home RID')
        if home.carrier_key not in complete_resource_maps or not isinstance(complete_resource_maps[home.carrier_key],Mapping):
            raise UnsupportedProfile('Every ordered home needs its complete verified carrier map')
        key=(ATTRIBUTE_TYPE,home.resource_id);complete=complete_resource_maps[home.carrier_key]
        if key in complete:
            payload=complete[key]
            return EffectiveFieldLimits(form_identity,home,payload,parse_field_limits_payload(payload))
    return EffectiveFieldLimits(form_identity,None,None,())

def limits_source_report(selection):
    if not isinstance(selection,EffectiveFieldLimits):raise UnsupportedProfile('Selected limits result')
    source=selection.source
    return dict(attribute_type=ATTRIBUTE_TYPE,present=source is not None,
        carrier_key_hex=source.carrier_key.hex()if source else None,
        resource_id=source.resource_id if source else None,
        metadata_type=source.metadata_type if source else None,
        payload_sha256=hashlib.sha256(selection.payload).hexdigest()if selection.payload is not None else None,
        payload_bytes=len(selection.payload)if selection.payload is not None else None,
        entries=[dict(current_field_index=e.current_field_index,payload_offset=e.payload_offset,
            body_hex=e.body.hex())for e in selection.entries],
        profile='explicit cache-empty/complete decoded maps; active cache/initialization unknown',
        missing_resource_is_App_source_invalid=False)

def check_current_bounds(selection,current_field_index,node):
    """Bounds-only read, with actual FV Used gate; no events or source writes.

    The caller provides an actual current ordinal/node view. Saved/source IDs
    require the full-ID bridge below; numeric ordinal equality is not assumed.
    Used0 storage stays storage even if nonzero; explicit Used1 numeric0 checks.
    Computed-only Used values skip native checker admission as90 established.
    """
    if not isinstance(selection,EffectiveFieldLimits):raise UnsupportedProfile('Explicit effective limits selection')
    if node is None:return CurrentBoundsResult('no_allocated_current_node',current_field_index,None,None,None)
    if node.field_index!=current_field_index:raise UnsupportedProfile('Current view key must match explicit current ordinal; use source binding')
    if not node.specific_attributes&1:return CurrentBoundsResult('allocated_unused',current_field_index,None,None,None)
    if node.specific_attributes&10==2:return CurrentBoundsResult('computed_checker_skipped',current_field_index,None,None,None)
    if node.specific_attributes&8:raise UnsupportedProfile('Existing Override scalar correction remains blocked')
    lookup=selection.lookup(current_field_index)
    if lookup.cache_empty_CheckBounds_call_code:
        return CurrentBoundsResult('attribute_absent_cache_empty_CA_active_state_unknown',current_field_index,lookup,None,0xca)
    if lookup.entry is None:return CurrentBoundsResult('present_list_no_entry_C8_cleared',current_field_index,lookup,0,0)
    if node.kind_byte!=13:raise UnsupportedProfile('Selected90 kind13 Bounds arithmetic only; no numeric conversion invented')
    error=check_kind13_bounds(node,lookup.entry.limits)
    return CurrentBoundsResult('bounds_only_checked',current_field_index,lookup,error,0)

def check_source_binding_bounds(registry,form,selection,binding,node):
    """Read-only source/current full-ID join; keeps source node untouched."""
    if selection.form is not form:raise UnsupportedProfile('Same effective form selection required')
    if not any(form is candidate for fs in registry.formsets for candidate in fs.forms):
        raise UnsupportedProfile('Same registry required')
    current=binding.current_field_index
    template,_=field_template(registry,form,template_swap=False)
    fields=[f for f in template.fields if f.ordinal==current]
    if len(fields)!=1 or fields[0].identifier!=binding.field_id:
        raise UnsupportedProfile('Full field ID must match the effective current ordinal')
    if node.field_index!=binding.source_field_index or node.element_index!=binding.element_index:
        raise UnsupportedProfile('Exact original source node key required')
    if (node.kind_byte,node.flag10,node.specific_attributes)!=(binding.source_kind,binding.source_format,binding.fv_attributes):
        raise UnsupportedProfile('Source binding kind/format/FVattrs must match current source node')
    if (node.kind_byte,node.flag10)!=(fields[0].kind,fields[0].format):
        raise UnsupportedProfile('Source/current kind or format conversion is not supplied')
    from dataclasses import replace
    return check_current_bounds(selection,current,replace(node,field_index=current))
