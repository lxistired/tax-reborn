"""Exact cold compiled FormSet7000 string18/13 supply; no native cache claim."""
from dataclasses import dataclass,field
import hashlib
from interop.form_core.effective_registry_fields_reference import Registry,parse_id_record,fixed_id,UnsupportedProfile

@dataclass(frozen=True)
class CompiledIdentity:
    formset_id:bytes
    mct:bytes
    tax_year:bytes
    source_home:object
    source_payload_sha256:str
    compiled_formset:object
    cold_getter_branch_only:bool=field(default=True,init=False)
    native_runtime_cache_verified:bool=field(default=False,init=False)
    native_template_pointer_verified:bool=field(default=False,init=False)
    active_source_snapshot_allowed:bool=field(default=False,init=False)
    writeback_allowed:bool=field(default=False,init=False)

def read_compiled_identity(registry,compiled_formset):
    if type(registry)is not Registry or not any(fs is compiled_formset for fs in registry.formsets):
        raise UnsupportedProfile('Exact FormSet object from the same compiled registry required')
    fs=compiled_formset
    if fs.primary is None or not fs.primary.strings or fixed_id(fs.primary.strings[0])!=fs.identifier:
        raise UnsupportedProfile('Original primary ID must correspond to the compiled dictionary identity')
    carriers={c.key:c.resources for c in registry.carriers};homes={}
    for home in fs.homes:
        ref=home.source;resources=carriers.get(ref.carrier_key)
        if resources is None:raise UnsupportedProfile('All FormSet homes must belong to this registry')
        if (7000,ref.resource_id)in resources:
            homes[ref.carrier_key,ref.resource_id]=(ref,resources[7000,ref.resource_id])
    if len(homes)!=1:
        raise UnsupportedProfile('Finite cold getter requires one complete unambiguous7000 source')
    source,payload=next(iter(homes.values()));record=parse_id_record(payload,source)
    if len(record.strings)<=18:
        raise UnsupportedProfile('Actual7000 string13 and string18 are both required')
    mct,year=record.strings[18],record.strings[13]
    if not 1<=len(mct)<=254 or any(v<33 or v>126 for v in mct):
        raise UnsupportedProfile('Finite exact printable ASCII MCT without NUL/space/locale conversion')
    if len(year)!=4 or any(v<48 or v>57 for v in year):
        raise UnsupportedProfile('Finite four-digit year; other native strings/errors not modeled')
    return CompiledIdentity(fs.primary.strings[0],mct,year,source,hashlib.sha256(payload).hexdigest(),fs)
