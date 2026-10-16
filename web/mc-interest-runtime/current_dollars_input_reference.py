"""Finite Used kind12 -> original flavor3/subtype0 dollar text -> Numeric.

Kind12 is a signed whole-dollar coefficient. The packed exponent is not its
scale. This reference only accepts ordinary source-format0/header0 storage.
It does not execute the native formatter, conversion errors or defaults.
"""
from dataclasses import dataclass
from decimal import Decimal
import re


@dataclass(frozen=True)
class StoredDollars:
    kind:int
    raw64:int
    attributes:int
    header:int=0
    format_flag10:int=0
    flag11:int=0
    packed_exponent:int=0


def render_current_dollars(value):
    if value is None:return None
    if type(value)is not StoredDollars or type(value.attributes)is not int or not 0<=value.attributes<=65535:raise ValueError('Explicit decoded FV/U16 attributes required')
    if not value.attributes&1:return None
    if value.attributes not in(1,3,9,11):raise ValueError('Ordinary Used/Computed/Override source masks required')
    if(value.kind,value.header,value.format_flag10)!=(12,0,0)or type(value.raw64)is not int or not 0<=value.raw64<1<<64 or type(value.flag11)is not int or not 0<=value.flag11<=255 or type(value.packed_exponent)is not int or not 0<=value.packed_exponent<=255:raise ValueError('Ordinary kind12 header0/format0 current storage required')
    coefficient=value.raw64 if value.raw64<1<<63 else value.raw64-(1<<64)
    if abs(coefficient)>10**9:raise ValueError('Finite whole-dollar coefficient at most one billion required')
    # Original flavor3: no grouping. FormatDollars calls FormatNumber(scale0),
    # then appends a decimal point when none exists and subtype!=2.
    return str(coefficient)+'.'


def create_dollars_numeric_input(text):
    if text is None:return None
    if type(text)is not str or re.fullmatch(r'-?(?:0|[1-9][0-9]{0,9})\.',text)is None:raise ValueError('Exact canonical flavor3 whole-dollar lexeme required')
    value=Decimal(text[:-1])
    if abs(value)>Decimal(10**9):raise ValueError('Finite dollar input exceeded')
    return value


def current_dollars_input(value):return create_dollars_numeric_input(render_current_dollars(value))
