"""Independent finite TaxML flavor3/subtype1 monetary renderer.

These are formatter results, not complete native Value/map serialization.
No original executable, XML writer, metadata defaults or callbacks run here.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class MoneyValue:
    kind: int
    signed_coefficient: int
    common_header: int=0
    scalar_format: int=0


def taxml_money_plan(kind):
    if type(kind)is not int or kind not in (11,12):raise ValueError('Only selected cent/dollar kinds are source-bound')
    return {'flavor':3,'subtype':1,'kind':kind,'callee':'FormatCents' if kind==11 else 'FormatDollars',
            'arguments':(False,True,False) if kind==11 else (False,True),
            'append_markers':False,'strip_trailing_spaces':True,
            'source_numeric_scale':2 if kind==11 else 0,
            'native_runtime_executed':False,'complete_TaxML_Value_serialized':False}


def render_taxml_money(value):
    if type(value)is not MoneyValue:raise ValueError('An explicit owned monetary value is required')
    taxml_money_plan(value.kind)
    n=value.signed_coefficient
    if type(n)is not int or type(value.common_header)is not int or type(value.scalar_format)is not int or value.common_header!=0 or value.scalar_format!=0:
        raise ValueError('Finite ordinary header0/format0 signed integer required')
    limit=10**11 if value.kind==11 else 10**9
    if abs(n)>limit:raise ValueError('Selected finite currency bound exceeded')
    sign='-' if n<0 else '';digits=str(abs(n))
    if value.kind==11:
        digits=digits.rjust(3,'0');return sign+digits[:-2]+'.'+digits[-2:]
    return sign+digits+'.'
