"""Finite ordinary kind8/subtype0 SSN -> source StringValue payload.

The same generic kind8 formatter proof used for TSSN applies by raw kind and
subtype, not by the field's name. Only canonical nine digits or present-empty
are supported. Native registry, formatter and exception paths do not execute.
"""
from interop.derived_form.string_wire_reference import read


def current_ssn_input(node,*,table,table_id):
    if node is None:return None
    attrs=node.specific_attributes
    if type(attrs)is not int or not 0<=attrs<=65535:raise ValueError('Actual U16 current attributes required')
    if not attrs&1:return None
    if attrs not in(1,3,9,11)or node.kind_byte!=8 or node.header or node.flag10 or node.flag11 or node.exponent_byte:raise ValueError('Ordinary kind8/header0/format0 finite source profile required')
    raw=node.raw
    if type(raw)is not int or not 0<=raw<1<<32 or type(table_id)is not int or not 0<=table_id<65535 or raw&65535!=table_id or(raw>>16)&65535==65535:raise ValueError('Exact same-form ordinary SSN string handle required')
    value=read(table,(raw>>16)&65535)
    if type(value)is not bytes or(value and(len(value)!=9 or any(c not in b'0123456789'for c in value))):raise ValueError('Canonical nine ASCII digits or present-empty SSN required')
    rendered=value[:3]+b'-'+value[3:5]+b'-'+value[5:]if value else b''
    # Original nativekind8 default read-transform(direction0) removes both
    # hyphens and slashes before the MEF StringValue is constructed.
    return rendered.replace(b'-',b'').replace(b'/',b'')
