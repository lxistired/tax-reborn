"""Finite stored Entity14D original-format(version1) byte reader/preserver.

No native Load, SetValue, cleanup, migration or current-cache operation is run.
Only complete BE scalar/count/length framing is accepted. Nonzero string lengths
must end in exactly one NUL; the native C-string assignment's unsafe/ambiguous
unterminated or embedded-NUL forms are refused rather than imitated.
"""
from dataclasses import dataclass
import struct

from .cx_string_wire_reference import UnsupportedProfile
NAME=b'TpsInstanceToMefInstanceMapPO'
CLASS_ID=0x14D
MAX_BYTES=4*1024*1024
MAX_ROWS=65535

@dataclass(frozen=True)
class StoredPair:
    tps_address:bytes
    mef_xpath:bytes

@dataclass(frozen=True)
class LegacyStoredBody:
    rows:tuple
    source_body:bytes
    version:int=1
    native_Load_executed:bool=False
    native_SetValue_executed:bool=False
    native_cleanup_executed:bool=False
    native_14F_transfer_executed:bool=False
    native_current_cache_verified:bool=False

def _field(wire,position):
    if position+2>len(wire):raise UnsupportedProfile('Complete original-format U16 string length required')
    count=struct.unpack_from('>H',wire,position)[0];position+=2
    end=position+count
    if end>len(wire):raise UnsupportedProfile('Complete original-format declared string block required')
    raw=wire[position:end]
    if not count:return b'',end
    if raw[-1:]!=b'\0' or b'\0'in raw[:-1]:
        raise UnsupportedProfile('Finite complete C-string requires a single final NUL')
    return raw[:-1],end

def load_legacy_body(wire):
    if type(wire)is not bytes or not 6<=len(wire)<=MAX_BYTES:
        raise UnsupportedProfile('Exact bounded complete original-format Entity14D body required')
    version,count=struct.unpack_from('>HI',wire)
    if version!=1 or count>MAX_ROWS:raise UnsupportedProfile('Finite original-format version1/count guard')
    position=6;rows=[];left=set();right=set()
    for unused in range(count):
        tps,position=_field(wire,position);mef,position=_field(wire,position)
        if tps in left or mef in right:raise UnsupportedProfile('Finite one-to-one saved keys; duplicate either side refused')
        left.add(tps);right.add(mef);rows.append(StoredPair(tps,mef))
    if position!=len(wire):raise UnsupportedProfile('Complete original-format body; unknown tail refused')
    return LegacyStoredBody(tuple(rows),wire)

def typed_legacy_body_or_none(wire):
    if type(wire)is not bytes or len(wire)<2:raise UnsupportedProfile('Complete Entity14D version required')
    if wire[:2]!=b'\0\1':return None
    return load_legacy_body(wire)

def preserve_legacy_body(body):
    if type(body)is not LegacyStoredBody or load_legacy_body(body.source_body)!=body:
        raise UnsupportedProfile('Complete untampered original stored body required')
    return body.source_body

def relocation_evidence(class_name,wire,*,owner_level,source_owner_key,target_owner_key):
    if type(class_name)is not bytes or class_name!=NAME or owner_level!='entity':
        raise UnsupportedProfile('Exact Entity14D class/scope required')
    if type(source_owner_key)is not bytes or not source_owner_key or len(source_owner_key)>MAX_BYTES or type(target_owner_key)is not bytes or source_owner_key!=target_owner_key:
        raise UnsupportedProfile('Exact same parsed original Entity owner required')
    body=load_legacy_body(wire)
    return dict(class_id=CLASS_ID,class_name=NAME.decode('ascii'),version=1,owner_level='entity',stored_rows=len(body.rows),
        complete_body_validated=True,source_body_position_independent=True,source_body_contains_physical_offsets=False,
        source_body_contains_StringTable_handles=False,same_source_owner_required=True,owner_reassignment_allowed=False,
        native_Load_executed=False,native_SetValue_executed=False,native_cleanup_executed=False,
        native_14F_transfer_executed=False,native_current_cache_verified=False,native_inventory_verified=False,native_execution_count=0)

def encode_owned_legacy_body(rows,*,zero_length_empty=True):
    """Owned fixture framing only. The native Store currently emits version2/3."""
    if type(rows)is not tuple or len(rows)>MAX_ROWS or type(zero_length_empty)is not bool:
        raise UnsupportedProfile('Explicit owned immutable pair tuple/empty encoding required')
    out=bytearray(struct.pack('>HI',1,len(rows)))
    for row in rows:
        if type(row)is not StoredPair:raise UnsupportedProfile('Exact owned byte pair required')
        for value in (row.tps_address,row.mef_xpath):
            if type(value)is not bytes or len(value)>65534 or b'\0'in value:raise UnsupportedProfile('Finite owned exact C-string bytes required')
            raw=b''if not value and zero_length_empty else value+b'\0'
            out.extend(struct.pack('>H',len(raw)));out.extend(raw)
            if len(out)>MAX_BYTES:raise UnsupportedProfile('Finite body budget')
    wire=bytes(out);load_legacy_body(wire);return wire
