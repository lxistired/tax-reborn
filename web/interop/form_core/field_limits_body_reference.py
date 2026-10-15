"""Standalone exact12-byte MacLE FieldLimits body and selected kind13 Bounds.

Independently written body subset extracted from90 without its allocator/events.
Unknown flag bits/inactive bytes are retained. No runtime callback/lookup or
money-scaling interpretation is performed. Native kind11/12 are not accepted.
"""
from dataclasses import dataclass
import struct
from .field_template_reference import UnsupportedProfile

@dataclass(frozen=True)
class FieldLimits:
    minimum:int
    maximum:int
    max_chars:int
    flags:int
    def to_bytes(self):
        for v in (self.minimum,self.maximum):
            if type(v)is not int or not -(1<<31)<=v<1<<31:raise UnsupportedProfile('Exact signed32 limits')
        for v in (self.max_chars,self.flags):
            if type(v)is not int or not 0<=v<=65535:raise UnsupportedProfile('Exact U16 flags/chars')
        return struct.pack('<iiHH',self.minimum,self.maximum,self.max_chars,self.flags)

def decode_field_limits(body):
    if type(body)is not bytes or len(body)!=12:raise UnsupportedProfile('Exact12-byte native MacLE FieldLimits body')
    return FieldLimits(*struct.unpack('<iiHH',body))

def check_kind13_bounds(node,limits):
    if not isinstance(limits,FieldLimits):raise UnsupportedProfile('Explicit exact FieldLimits body')
    limits.to_bytes()
    if node.kind_byte!=13:raise UnsupportedProfile('Only native kind13 raw integer bounds; no11/12 conversion')
    if type(node.raw)is not int or not 0<=node.raw<1<<64:raise UnsupportedProfile('Exact U64 raw bits')
    value=node.raw-(1<<64)if node.raw>>63 else node.raw
    if limits.flags&1 and value<limits.minimum:return 0x219
    if limits.flags&2 and value>limits.maximum:return 0x21a
    return 0
