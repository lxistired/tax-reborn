"""Independent finite scalar parameter/index conversion contract.

No vendor I/O, native pointers, bytecode interpreter, rates or tax rules.
Runtime success and current scalar storage are caller-supplied. Function3's
whole kind10/12 range is exact through the 32-bit fixed-point bridge. Wider
native conversion is exposed separately as a bounded diagnostic mechanism.
"""
from dataclasses import dataclass
from decimal import Decimal

LIMIT=10**9
INT_MAX=(1<<31)-1

@dataclass(frozen=True)
class Numeric:
    kind: int
    amount: Decimal

@dataclass(frozen=True)
class ScalarParameter:
    kind: int
    present: bool
    amount: Decimal

@dataclass(frozen=True)
class Fix32Witness:
    mantissa: int
    scale: int
    saturation_error_code: int|None
    overflow_sentinel: bool
    reductions: int

def _whole(value, kinds=(10,12)):
    if (not isinstance(value,Numeric) or type(value.kind)is not int or value.kind not in kinds
            or type(value.amount)is not Decimal or not value.amount.is_finite()
            or value.amount!=value.amount.to_integral_value() or abs(value.amount)>LIMIT):
        raise ValueError('Explicit finite whole kind10/12 scalar within1e9 required')
    return int(value.amount)

def bigfixed_to_fix32(mantissa,scale):
    """Selected raw native bridge witness, scale0..9, excluding int64 minimum.

    Overflow uses signed +/-INT_MAX at scale0. Native code may call its
    registered error function with code9; this helper records the condition
    and never calls a callback. IsOverflowed also recognizes an exact native
    +/-INT_MAX,scale0 input even when Assign requested no error callback.

    During scale reduction the original machine code narrows a division
    remainder to U16 before its half comparison. That behavior is retained
    here; this function is deliberately not a general Decimal rounding API.
    """
    if (type(mantissa)is not int or not -(1<<63)<mantissa<(1<<63)
            or type(scale)is not int or not 0<=scale<=9):
        raise ValueError('Selected signed64 mantissa and scale0..9 required')
    magnitude=abs(mantissa);candidate=magnitude;remaining=scale;count=0
    if magnitude>INT_MAX and remaining:
        divisor_power=1
        while candidate>=1<<31 and remaining:
            divisor=10**min(divisor_power,9)
            quotient,remainder=divmod(magnitude,divisor)
            candidate=quotient+int((remainder&0xffff)>=5*10**(divisor_power-1))
            count+=1;divisor_power+=1;remaining-=1
    error=None
    if candidate>=1<<31:
        result=-INT_MAX if mantissa<0 else INT_MAX;remaining=0;error=9
    else:result=-candidate if mantissa<0 else candidate
    return Fix32Witness(result,remaining,error,remaining==0 and abs(result)==INT_MAX,count)

def whole_to_fix32(value):
    amount=_whole(value);result=bigfixed_to_fix32(amount,0)
    assert result.mantissa==amount and result.scale==0 and result.saturation_error_code is None and not result.overflow_sentinel
    return result

def assign_fixed32(target_kind,fixed):
    if (type(target_kind)is not int or target_kind not in(10,12) or not isinstance(fixed,Fix32Witness)
            or fixed.scale!=0 or fixed.saturation_error_code is not None or fixed.overflow_sentinel
            or type(fixed.mantissa)is not int or abs(fixed.mantissa)>LIMIT):
        raise ValueError('Exact finite nonoverflow scale0 fixed32 assignment required')
    return Numeric(target_kind,Decimal(fixed.mantissa))

def scalar_parameter_assign(target_kind,operand):
    """Normal scalar variant1 OpCodeUserProcParamAssign, targetkind10/12.

    This is assignment, distinct from CreateParameters: immediateFalse assigns
    a present zero. Null sets typed zero storage and presentFalse. Native
    strings/dates/references/errors and target header flags remain external.
    """
    if type(target_kind)is not int or target_kind not in(10,12):
        raise ValueError('Selected parameter kind10/12 required')
    if operand is None:return ScalarParameter(target_kind,False,Decimal(0))
    if type(operand)is bool:return ScalarParameter(target_kind,True,Decimal(int(operand)))
    result=assign_fixed32(target_kind,whole_to_fix32(operand))
    return ScalarParameter(result.kind,True,result.amount)

def array_index(value,ordinal,capacity=7):
    """Selected Function3 fixed arrays18/19/20, exact one-based1..7 only.

    Native consumers narrow the fixed mantissa to U16. The finite guard rejects
    fractions, overflow and aliases from wider values instead of reproducing
    unsupported narrowing/error behavior. Array allocation is not performed.
    """
    if type(ordinal)is not int or ordinal not in(18,19,20) or type(capacity)is not int or capacity!=7:
        raise ValueError('Selected existing fixed array18/19/20 capacity7 required')
    index=_whole(value,(10,))
    if not 1<=index<=capacity:raise ValueError('Selected exact one-based array index1..7 required')
    fixed=whole_to_fix32(value);assert fixed.mantissa==index and index==(index&0xffff)
    return index

def index_step(value,delta):
    """Normal OpCodeIndexIncrement/Decrement on existing kind10 storage."""
    old=_whole(value,(10,))
    if type(delta)is not int or delta not in(-1,1) or abs(old+delta)>LIMIT:
        raise ValueError('Finite existing index and one increment/decrement required')
    return ScalarParameter(10,True,Decimal(old+delta))
