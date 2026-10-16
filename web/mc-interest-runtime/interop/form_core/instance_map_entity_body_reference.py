"""Finite stored Entity14D body, not native current map/legacy migration.

Native Store emits exact version3 for an empty stored inventory and version2
for nonempty compressed pairs. Native Load cleanup/Transfer are never executed.
Version1 original-format bodies and version2 count0 remain opaque for movement.
"""
from dataclasses import dataclass
import struct
from .instance_map_formset_body_reference import (
    StoredPair, load_stored_body as _load_pair_body, encode_owned_body as _encode_pair_body,
    MAX_BYTES, MAX_ROWS, UnsupportedProfile)

NAME=b'TpsInstanceToMefInstanceMapPO'
CLASS_ID=0x14D

@dataclass(frozen=True)
class StoredEntityBody:
    version:int
    rows:tuple
    decoded_payload:bytes
    source_body:bytes
    compression_chunks:tuple
    compression_endian:object
    native_cleanup_executed:bool=False
    native_14F_transfer_executed:bool=False
    native_current_cache_verified:bool=False

def load_stored_entity_body(wire):
    if type(wire)is not bytes or not 2<=len(wire)<=MAX_BYTES+8192:
        raise UnsupportedProfile('Exact bounded complete Entity14D body required')
    version=struct.unpack_from('>H',wire)[0]
    if version==3:
        if len(wire)!=2:raise UnsupportedProfile('Exact version3 empty stored body; unknown tail refused')
        return StoredEntityBody(3,(),b'',wire,(),None)
    if version!=2:
        raise UnsupportedProfile('Only stored version2 nonempty or exact version3 empty is supported')
    # Same source-proven row/compression grammar, separate class/version/owner.
    # The temporary header is decoder input only; original body is retained.
    parsed=_load_pair_body(b'\0\1'+wire[2:])
    return StoredEntityBody(2,parsed.rows,parsed.decoded_payload,wire,
                            parsed.source_compression_chunks,parsed.compression_endian)

def typed_entity_map_or_none(wire):
    if type(wire)is not bytes or len(wire)<2:
        raise UnsupportedProfile('Complete Entity14D version required')
    version=struct.unpack_from('>H',wire)[0]
    if version not in (2,3):return None
    if version==2:
        if len(wire)<6:raise UnsupportedProfile('Complete version2 count required')
        if struct.unpack_from('>I',wire,2)[0]==0:return None
    return load_stored_entity_body(wire)

def load_named_stored_entity_body(class_name,wire,*,owner_level):
    if type(class_name)is not bytes or class_name!=NAME or owner_level!='entity':
        raise UnsupportedProfile('Exact Entity14D descriptor/owner required')
    return load_stored_entity_body(wire)

def preserve_stored_entity_body(body):
    if type(body)is not StoredEntityBody or load_stored_entity_body(body.source_body)!=body:
        raise UnsupportedProfile('Complete untampered stored Entity14D body required')
    return body.source_body

def relocation_evidence(class_name,wire,*,owner_level,source_owner_key,target_owner_key):
    if (type(source_owner_key)is not bytes or not source_owner_key or len(source_owner_key)>MAX_BYTES
            or type(target_owner_key)is not bytes or source_owner_key!=target_owner_key):
        raise UnsupportedProfile('Retain the exact original source Entity owner')
    body=load_named_stored_entity_body(class_name,wire,owner_level=owner_level)
    return dict(class_id=CLASS_ID,class_name=NAME.decode('ascii'),owner_level='entity',version=body.version,
                stored_rows=len(body.rows),complete_body_validated=True,source_body_position_independent=True,
                source_body_contains_physical_offsets=False,source_body_contains_StringTable_handles=False,
                source_bytes_exactly_preserved=True,same_source_owner_required=True,owner_reassignment_allowed=False,
                native_cleanup_executed=False,native_14F_transfer_executed=False,native_current_cache_verified=False,
                native_inventory_verified=False,native_Clone_executed=False,native_execution_count=0)

def encode_owned_entity_body(rows,*,compressed=False):
    """Owned fixture framing only, not native runtime compressor byte parity."""
    if type(rows)is not tuple or type(compressed)is not bool:
        raise UnsupportedProfile('Explicit immutable owned pair tuple and compression flag')
    if not rows:return b'\0\3'
    wire=_encode_pair_body(rows,compressed=compressed)
    return b'\0\2'+wire[2:]
