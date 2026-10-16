"""Owned finite object/late-tail/cache model. This has no document request API.

Entry values and node-memory bytes are explicitly resolved owned inputs. They
are not an observed native object, inventory, cache, NodeID or current value.
A copy stage is not a complete CalcAndRound or an authorized TPS write.
"""
from dataclasses import dataclass,field
from decimal import Decimal
import struct

@dataclass
class NumericState:
    coefficient: Decimal
    base_8_17: bytearray
    auxiliary_2c_33: bytes=b'\0'*8

@dataclass
class FlatNumericMC:
    rows: dict
    base_8_17: bytearray=field(default_factory=lambda:bytearray(16))
    user_entered_key_byte: int=0

def _key(key):
    if type(key)is not bytes or len(key)>4096:raise ValueError('Bounded exact byte ID required')
    return key

def _base(base):
    if type(base)is not bytearray or len(base)!=16:raise ValueError('Owned Value bytes+0x08..+0x17 (16B) required')

def _numeric(value):
    if type(value)is not NumericState:raise ValueError('Flat Numeric values only')
    _base(value.base_8_17)
    if type(value.coefficient)is not Decimal or not value.coefficient.is_finite()or abs(value.coefficient)>10**9:
        raise ValueError('Bounded exact numeric coefficient required')
    if type(value.auxiliary_2c_33)is not bytes or len(value.auxiliary_2c_33)!=8:raise ValueError('Exact Numeric auxiliary bytes required')

def _mc(value):
    if type(value)is not FlatNumericMC or type(value.rows)is not dict or len(value.rows)>64:raise ValueError('At most64 flat owned Numeric rows required')
    _base(value.base_8_17)
    if type(value.user_entered_key_byte)is not int or not 0<=value.user_entered_key_byte<=255:raise ValueError('Actual low byte required')
    for key,leaf in value.rows.items():_key(key);_numeric(leaf)

def copy_after_merge(merged,node_multi_copy_info):
    """Actual C1/C2 per-key clone, followed by actual node+8 info byte30."""
    _mc(merged)
    if type(node_multi_copy_info)is not bytes or len(node_multi_copy_info)!=0x31:
        raise ValueError('Explicit resolved NodeMultiCopyInfo bytes through30 required')
    rows={key:NumericState(value.coefficient,bytearray(value.base_8_17),value.auxiliary_2c_33)
          for key,value in sorted(merged.rows.items())}
    return FlatNumericMC(rows,bytearray(merged.base_8_17),node_multi_copy_info[0x30])

def apply_late_noop_tail(value,node_bytes):
    """Restricted late boundary at1019c2719, not a whole CalcAndRound call.

    Explanation-only processing, external postprocessor and node+80 condition
    are rejected. Input-error/explanation work before this boundary is not run.
    Numeric coefficient and opaque auxiliary state are unchanged.
    """
    _mc(value)
    if type(node_bytes)is not bytes or len(node_bytes)!=0x98:raise ValueError('Explicit resolved node bytes0..97 required')
    if node_bytes[0x71]==1:raise ValueError('Explanation-only producer is not executed')
    if struct.unpack_from('<Q',node_bytes,0x80)[0]:raise ValueError('Native value-condition/r13 producer is not supplied')
    process=node_bytes[0x94]==0
    if process and struct.unpack_from('<Q',node_bytes,0x40)[0]:raise ValueError('Concrete NodePostProcessing/rounder is not executed')
    drop=any(leaf.base_8_17[8]&0x80 for leaf in value.rows.values())
    computed_call=not drop and node_bytes[0x96]==0
    if computed_call:
        # MC.SetComputedBit delegates to every leaf. Its own base stays intact.
        for leaf in value.rows.values():leaf.base_8_17[8]=(leaf.base_8_17[8]&0xf7)|8
    # Node.GetPostProcessing returns actual NoPostProcessing only when+40NULL;
    # its Process moves ValuePtr, preserving the object reference.
    return dict(value=value,computed_setter_called=computed_call,
                final_process='NoPostProcessing'if process else'skipped_by_node94',
                cache_route='data_relevancy'if node_bytes[0x96]==1 or node_bytes[0x97]==1 else'output',
                input_error_stage_executed=False,whole_CalcAndRound_executed=False,
                resolved_node_memory_authenticated=False,native_inventory=False,native_TPS_writes=0)

class DuplicateNode(ValueError):pass

@dataclass
class OwnedCache:
    # DataModel stores a supplied TKECalcDataCache*. This object is a separately
    # owned model; constructing a view does not clear these maps.
    output: dict=field(default_factory=dict)
    data_relevancy: dict=field(default_factory=dict)

def _cache(cache):
    if type(cache)is not OwnedCache:raise ValueError('Explicit owned cache required')
    for mapping in(cache.output,cache.data_relevancy):
        if type(mapping)is not dict or len(mapping)>64:raise ValueError('Bounded owned cache maps required')
        for key,value in mapping.items():
            _key(key)
            if value is not None:_mc(value)

def cache_read(cache,node_id):
    """Normal map has precedence; a stored NULL is still a cache hit."""
    _cache(cache);_key(node_id)
    if node_id in cache.output:return True,cache.output[node_id],'output'
    if node_id in cache.data_relevancy:return True,cache.data_relevancy[node_id],'data_relevancy'
    return False,None,None

def cache_insert(cache,node_id,value,route):
    _cache(cache);_key(node_id)
    if value is not None:_mc(value)
    if route not in('output','data_relevancy'):raise ValueError('Exact cache route required')
    mapping=getattr(cache,route)
    if node_id in mapping:raise DuplicateNode('Duplicate NodeID: native helper throws, without replacement')
    if len(mapping)>=64:raise ValueError('Owned cache bound exceeded')
    mapping[node_id]=value
    return True

def native_request_or_commit(*_args,**_kwargs):
    raise ValueError('No native node/cache/current-value authentication or TPS commit is supplied')
