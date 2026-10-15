"""Independent scalar amount adapter; contains no vendor bytes or resources.

The caller binds a decoded ValueHash node to actual field metadata and supplies
its independent FV attributes. No raw payload can establish field presence.
Only native kinds 11 and 12 are admitted. This adapter does not parse a tax file.
"""
from dataclasses import dataclass
from decimal import Decimal

class UnsupportedAmount(ValueError):pass

@dataclass(frozen=True)
class AmountDecode:
    status:str
    value:Decimal|None
    present:bool
    signed_raw:int
    scale:int
    raw_exponent_byte:int
    raw_header:int
    raw_fv_attributes:int
    override:bool
    computed:bool

def uint(value,bits,label):
    if type(value)is not int or not 0<=value<1<<bits:raise UnsupportedAmount(label+' must be an explicit uint'+str(bits))
    return value

def decode_amount(*,kind_byte,raw64,exponent_byte,fv_attributes,value_header=0,source_error=0):
    """Decode little-endian raw64 or an unsigned integer carrying its bits.

    Original ConvertToFixPoint selects scale2 for kind11 and scale0 for kind12.
    The stored exponent byte is retained but is not their scale. It is used by
    the original generic kind25 path, which this function deliberately refuses.
    Error/overflow outcomes never become zero. A present numeric raw0 is zero;
    an unused payload is retained for diagnostics and produces value=None.
    """
    uint(kind_byte,8,'kind_byte');uint(exponent_byte,8,'exponent_byte')
    uint(fv_attributes,16,'fv_attributes');uint(value_header,8,'value_header');uint(source_error,16,'source_error')
    if kind_byte not in(11,12):raise UnsupportedAmount('only actual scalar kind11/12 metadata binding is supported')
    if isinstance(raw64,bytes):
        if len(raw64)!=8:raise UnsupportedAmount('raw64 requires exactly eight little-endian bytes')
        raw64=int.from_bytes(raw64,'little',signed=False)
    uint(raw64,64,'raw64')
    signed=raw64 if raw64<1<<63 else raw64-(1<<64)
    scale=2 if kind_byte==11 else 0
    present=bool(fv_attributes&1)
    result=dict(present=present,signed_raw=signed,scale=scale,raw_exponent_byte=exponent_byte,raw_header=value_header,raw_fv_attributes=fv_attributes,override=bool(fv_attributes&8),computed=bool(fv_attributes&2))
    if source_error:return AmountDecode('source_error',None,**result)
    # LowSetValue's validation path can set value-header80 after committing.
    # Preserve the record and refuse an ordinary monetary value for review.
    if value_header&0x80:return AmountDecode('diagnostic_header',None,**result)
    if not present:return AmountDecode('unused',None,**result)
    # Original IsOverflow recognizes +/-INT64_MAX, and a second pair only at
    # exponent0. Construction excludes INT64_MIN too; do not expose it as money.
    if signed in(-(1<<63),-(1<<63)+1,(1<<63)-1)or(abs(signed)==999999999999999999 and exponent_byte==0):
        return AmountDecode('reserved_or_overflow',None,**result)
    # Original CheckOverflows imposes a normal display bound on kind12. This
    # adapter does not turn its non-normal result into a regular review amount.
    if kind_byte==12 and abs(signed)>99999999999999:
        return AmountDecode('display_overflow',None,**result)
    return AmountDecode('value',Decimal(signed).scaleb(-scale),**result)

def amount_as_text(decoded):
    if not isinstance(decoded,AmountDecode):raise UnsupportedAmount('decoded amount required')
    return None if decoded.value is None else format(decoded.value,'f')
