"""Finite stored Entity14D body(v1/v2/v3); raw-copy only, not current native map.

Unknown versions and compressed count0 remain opaque. Exact Entity class/scope
and same parsed source owner must be enforced by the document integration.
"""
from dataclasses import dataclass
from . import legacy_instance_map_entity_body_reference as legacy
from . import instance_map_entity_body_reference as compressed
from .cx_string_wire_reference import UnsupportedProfile

NAME=compressed.NAME
CLASS_ID=compressed.CLASS_ID

@dataclass(frozen=True)
class StoredPair:
    tps_address:bytes
    mef_xpath:bytes

@dataclass(frozen=True)
class StoredEntityMap:
    version:int
    rows:tuple
    source_body:bytes
    source_format:str
    native_Load_executed:bool=False
    native_SetValue_executed:bool=False
    native_cleanup_executed:bool=False
    native_14F_transfer_executed:bool=False
    native_current_cache_verified:bool=False
    native_inventory_verified:bool=False

def typed_entity_body_or_none(wire):
    if type(wire)is not bytes or len(wire)<2:raise UnsupportedProfile('Complete stored Entity14D version required')
    version=int.from_bytes(wire[:2],'big')
    if version==1:
        body=legacy.load_legacy_body(wire);kind='version1-length-framed'
    else:
        body=compressed.typed_entity_map_or_none(wire)
        if body is None:return None
        kind='version2-compressed-pairs'if version==2 else'version3-stored-no-payload'
    return StoredEntityMap(version,tuple(StoredPair(r.tps_address,r.mef_xpath)for r in body.rows),wire,kind)

def load_entity_body(wire):
    body=typed_entity_body_or_none(wire)
    if body is None:raise UnsupportedProfile('Opaque stored body has no finite typed or movement permission')
    return body

def preserve_entity_body(body):
    if type(body)is not StoredEntityMap or load_entity_body(body.source_body)!=body:
        raise UnsupportedProfile('Retain complete untampered stored Entity14D source bytes')
    return body.source_body

def load_named_entity_body(class_name,wire,*,owner_level):
    if type(class_name)is not bytes or class_name!=NAME or owner_level!='entity':
        raise UnsupportedProfile('Exact Entity14D wire class and scope required')
    return load_entity_body(wire)

def relocation_evidence(class_name,wire,*,owner_level,source_owner_key,target_owner_key):
    if(type(source_owner_key)is not bytes or not source_owner_key or len(source_owner_key)>4*1024*1024
       or type(target_owner_key)is not bytes or source_owner_key!=target_owner_key):
        raise UnsupportedProfile('Exact same parsed original source Entity owner required')
    body=load_named_entity_body(class_name,wire,owner_level=owner_level)
    return dict(class_id=CLASS_ID,class_name=NAME.decode('ascii'),version=body.version,stored_rows=len(body.rows),
        source_format=body.source_format,owner_level='entity',complete_body_validated=True,
        source_body_position_independent=True,source_body_contains_physical_offsets=False,
        source_body_contains_StringTable_handles=False,source_bytes_exactly_preserved=True,
        same_source_owner_required=True,owner_reassignment_allowed=False,row_editing_supported=False,
        native_Load_executed=False,native_SetValue_executed=False,native_cleanup_executed=False,
        native_14F_transfer_executed=False,native_current_cache_verified=False,native_inventory_verified=False)
