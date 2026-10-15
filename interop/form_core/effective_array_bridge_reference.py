"""One effective registry supplies both current fields and actual array blocks."""
from collections.abc import Mapping
import re
from .effective_registry_fields_reference import Carrier,register_records,UnsupportedProfile
from .effective_wire_bridge_reference import effective_wire_templates
from .effective_array_payload_reference import effective_array_payloads,array_source_report

def build_effective_templates_and_arrays(ordered_complete_resource_maps,selected,*,field_factory,template_factory):
    if not isinstance(selected,Mapping):raise UnsupportedProfile('explicit selected target mapping')
    carriers=[];identities={};order=[]
    for item in ordered_complete_resource_maps:
        if type(item) is not tuple or len(item)!=2:raise UnsupportedProfile('ordered SHA/resource-map tuples')
        digest,resources=item
        if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}',digest):raise UnsupportedProfile('explicit SHA256 identity')
        key=digest.encode('ascii')
        if key in identities:raise UnsupportedProfile('duplicate carrier SHA')
        carriers.append(Carrier(key,resources));identities[key]=digest;order.append(digest)
    targets=[]
    for key,value in selected.items():
        if type(key) is not tuple or len(key)!=2 or type(value) is not tuple or len(value)!=2:
            raise UnsupportedProfile('selected (fs,form):(SHA,RID) mapping')
        targets.append((*key,*value))
    registry=register_records(carriers)
    templates,report=effective_wire_templates(registry,carrier_sha256_by_key=identities,
        registry_order=order,selected_targets=tuple(targets),field_factory=field_factory,template_factory=template_factory)
    forms={(fs.identifier.rstrip(b' ').decode('ascii'),f.identifier.rstrip(b' ').decode('ascii')):f
           for fs in registry.formsets for f in fs.forms}
    arrays={};array_report=[]
    for fsid,fid in selected:
        value=effective_array_payloads(registry,forms[fsid,fid])
        arrays[fsid,fid]=value;blocks=array_source_report(value)
        for block in blocks:
            key=bytes.fromhex(block.pop('carrier_key_hex')) if block['present'] else None
            block['carrier_sha256']=identities[key] if key is not None else None
        array_report.append(dict(formset_id=fsid,form_id=fid,blocks=blocks))
    report['selected_array_templates']=array_report
    report['array_definitions_source']='same explicit effective registry; complete decoded2000/2001 payloads'
    return templates,report,arrays
