"""Actual146 zccPersisUUID raw U8-length body; no current Entity UUID setter.

This class uses its own Load/Store, not the147 shared UUIDBase body. Native
Load adds NUL and uses strlen before setPersistentUUID. This helper preserves
all declared source bytes, including embeddedNUL, without claiming that the
native setter accepts or activates them. The body has no stream references.
"""
from dataclasses import dataclass
from ..form_core.field_template_reference import UnsupportedProfile
NAME=b'zccPersisUUID'

@dataclass(frozen=True)
class LegacyUUIDBody:
 data:bytes
 source_wire:bytes
 @property
 def c_string_prefix(self):return self.data.split(b'\0',1)[0]
 @property
 def native_setter_executed(self):return False

@dataclass(frozen=True)
class LoadedLegacyUUID:
 body:LegacyUUIDBody
 consumed:int

def load_legacy_uuid_body_bytes(wire,position=0):
 if type(wire)is not bytes or type(position)is not int or not 0<=position<len(wire):raise UnsupportedProfile('Complete type146 raw length byte')
 size=wire[position];end=position+1+size
 if end>len(wire):raise UnsupportedProfile('Complete type146 declared U8 payload')
 raw=wire[position:end]
 return LoadedLegacyUUID(LegacyUUIDBody(raw[1:],raw),len(raw))

def load_legacy_uuid_body(wire):
 loaded=load_legacy_uuid_body_bytes(wire)
 if loaded.consumed!=len(wire):raise UnsupportedProfile('Exact entire type146 raw body')
 return loaded.body

def preserve_legacy_uuid_body(body):
 if not isinstance(body,LegacyUUIDBody)or load_legacy_uuid_body(body.source_wire)!=body:raise UnsupportedProfile('Unchanged exact source type146 body')
 return body.source_wire

def encode_owned_legacy_uuid_body(data):
 """Own fixture only. No runtime UUID registration or native Store invoked."""
 if type(data)is not bytes or len(data)>255:raise UnsupportedProfile('Own type146 payload0..255 bytes; native large-string lowU8 truncation not generalized')
 return bytes([len(data)])+data
