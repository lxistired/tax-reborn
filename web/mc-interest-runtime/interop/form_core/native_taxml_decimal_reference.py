"""Selected native TaxML kind13/dec1 renderer, independently written.

This is a decimal coefficient with one implied fractional digit, not the
binary raw-integer editing API. Only nonoverflow, header0/FVformat0/current
compiledformat0 ordinary scalars are modeled; no native setter or factory runs.
"""
from decimal import Decimal
import re
from .field_template_reference import UnsupportedProfile
MAX_COEFFICIENT=99_999_999_999_999
_RX=re.compile(r'-?(?:0|[1-9][0-9]{0,12})\.[0-9]\Z')
def render_dec1(coefficient,*,header=0,value_format=0,compiled_format=0):
    if any(type(x)is not int or x!=0 for x in(header,value_format,compiled_format)):
        raise UnsupportedProfile('Only ordinary dec1 header0/FVformat0/currentformat0')
    if type(coefficient)is not int or abs(coefficient)>MAX_COEFFICIENT:
        raise UnsupportedProfile('Selected dec1 nonoverflow coefficient required')
    magnitude=abs(coefficient)
    return('-'if coefficient<0 else'')+str(magnitude//10)+'.'+str(magnitude%10)
def parse_dec1(text):
    if type(text)is not str or not _RX.fullmatch(text):
        raise UnsupportedProfile('Exact native dec1 text requires one fractional digit')
    coefficient=int(Decimal(text)*10)
    if render_dec1(coefficient)!=text:
        raise UnsupportedProfile('Noncanonical or overflowing native dec1 text')
    return coefficient
