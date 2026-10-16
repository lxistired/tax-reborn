"""Select actual decoded2000/2001 payloads from an explicit effective registry.

The existing strict carrier reader and effective modern registration must run
first. No resource IO, cache, decompressor, native current-registry assertion,
field/row allocation, UUID creation or App import is performed here.
"""
from dataclasses import dataclass
import hashlib
import struct
from .effective_registry_fields_reference import Registry,CompiledForm
from .field_template_reference import UnsupportedProfile,read_id

@dataclass(frozen=True)
class ArrayRecord:
    identifier: bytes
    first_field: int
    last_field: int
    element_limit: int
    flags: int
    byte27: int
    encoded_id: bytes
    source_metadata: bytes
    global_index: int

@dataclass(frozen=True)
class ArrayBlock:
    attribute_type: int
    source: object
    records: tuple
    source_payload: object
    consumed: int

@dataclass(frozen=True)
class EffectiveArrays:
    blocks: tuple
    @property
    def records(self):
        return tuple(record for block in self.blocks for record in block.records)
    def construct(self,array_factory):
        """Build83 descriptors; exact bytes and byte27 remain in these blocks."""
        if not callable(array_factory):raise UnsupportedProfile('explicit owned array constructor')
        return tuple(tuple(array_factory(identifier=r.identifier,first_field=r.first_field,
            last_field=r.last_field,element_limit=r.element_limit,flags=r.flags)
            for r in block.records) for block in self.blocks)

def parse_array_payload(payload,*,start_index=1,require_all=True):
    """Modern Mac hostLE attribute payload, distinct from .tax stream scalars.

    Native decoding copies all three U16s and both bytes without validating
    ranges. This helper preserves them. A consumer must apply its own stricter
    ordinary range/shape guards before using the descriptors as current arrays.
    """
    if type(payload) is not bytes or len(payload)<2:raise UnsupportedProfile('complete LE array payload')
    if type(start_index) is not int or not 1<=start_index<=65536 or type(require_all) is not bool:
        raise UnsupportedProfile('explicit one-based U16 index and whole-payload flag')
    count=struct.unpack_from('<H',payload)[0]
    if start_index+count-1>65535:raise UnsupportedProfile('finite global array index wrap refused')
    p=2;records=[]
    for offset in range(count):
        begin=p;identifier,p=read_id(payload,p);encoded=payload[begin:p]
        if p+8>len(payload):raise UnsupportedProfile('truncated array metadata')
        metadata=payload[p:p+8];a,b,c,d,e=struct.unpack('<HHHBB',metadata);p+=8
        records.append(ArrayRecord(identifier,a,b,c,d,e,encoded,metadata,start_index+offset))
    if require_all and p!=len(payload):raise UnsupportedProfile('unconsumed array payload bytes')
    return tuple(records),p

def effective_array_payloads(registry,form,*,require_all=True):
    """Ordinary cache-empty successful lookup: first present home per block.

    Missing2000/2001 is an authoritative absence only because the caller supplied
    complete decoded resource maps. Empty-present payloads are invalid, while
    a present U16zero is a real empty block and stops fallback. Cached objects,
    non-missing IO errors, wrapper/deferred data states and native allocation
    errors are outside this successful static subset.
    """
    if not isinstance(registry,Registry) or not isinstance(form,CompiledForm):
        raise UnsupportedProfile('explicit effective registry and compiled form')
    if not any(form is candidate for fs in registry.formsets for candidate in fs.forms):
        raise UnsupportedProfile('form must belong to the exact registry snapshot')
    carriers={c.key:c.resources for c in registry.carriers};blocks=[];start=1
    for attribute_type in (2000,2001):
        source=None;payload=None
        for home in form.homes:
            key=attribute_type,home.source.resource_id
            resources=carriers[home.source.carrier_key]
            if key in resources:
                source=home.source;payload=resources[key];break
        records=();consumed=0
        if payload is not None:
            records,consumed=parse_array_payload(payload,start_index=start,require_all=require_all)
        blocks.append(ArrayBlock(attribute_type,source,records,payload,consumed));start+=len(records)
    return EffectiveArrays(tuple(blocks))

def array_source_report(value):
    """JSON-safe record provenance; caller can replace carrier keys with SHAs."""
    if not isinstance(value,EffectiveArrays):raise UnsupportedProfile('effective array result')
    result=[]
    for block in value.blocks:
        source=block.source
        result.append(dict(attribute_type=block.attribute_type,present=source is not None,
            carrier_key_hex=source.carrier_key.hex() if source else None,
            resource_id=source.resource_id if source else None,
            metadata_type=source.metadata_type if source else None,
            payload_bytes=len(block.source_payload) if block.source_payload is not None else None,
            payload_sha256=hashlib.sha256(block.source_payload).hexdigest() if block.source_payload is not None else None,
            consumed=block.consumed,records=[dict(identifier_hex=r.identifier.hex(),
                first_field=r.first_field,last_field=r.last_field,element_limit=r.element_limit,
                flags=r.flags,byte27=r.byte27,global_index=r.global_index,
                encoded_id_hex=r.encoded_id.hex(),source_metadata_hex=r.source_metadata.hex())
                for r in block.records]))
    return result
