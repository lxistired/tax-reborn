"""Bound existing normal kind13 whole-number source corrections.

Only signed32, exponent0, header0, format0, flag11=0 and ordinary Used1 storage
is editable. Same-registry2160 lists provide the Bounds component. Native date,
pick/alias/default/author/validation events and the original engine do not run.
"""
import hashlib,re
from dataclasses import replace
from interop.form_core.field_limits_body_reference import check_kind13_bounds


def describe_integer(form,node,spec,selection):
    value=node.raw if node.raw<1<<63 else node.raw-(1<<64)
    result=dict(status='whole_number_profile_unsupported',text=str(value),editable=False,number_kind='whole_number')
    if not node.specific_attributes&1:return dict(result,status='unused',text=None)
    if node.header or node.exponent_byte or node.flag10 or node.flag11 or node.specific_attributes!=1 or spec.attributes!=0 or not -(1<<31)<=value<1<<31:
        return result
    if selection is None or selection.payload is None:
        return dict(result,status='whole_number_limits_unavailable')
    lookup=selection.lookup(spec.ordinal);entry=lookup.entry
    error=check_kind13_bounds(node,entry.limits)if entry else 0
    source=selection.source
    limits=dict(present=True,entry_present=entry is not None,
        minimum=entry.limits.minimum if entry and entry.limits.flags&1 else None,
        maximum=entry.limits.maximum if entry and entry.limits.flags&2 else None,
        resource_id=source.resource_id,carrier_sha256=source.carrier_key.decode(),
        payload_sha256=hashlib.sha256(selection.payload).hexdigest(),
        exact_body_sha256=hashlib.sha256(entry.body).hexdigest()if entry else None,
        exact_body_hex=entry.body.hex()if entry else None,
        active_cache_verified=False,complete_native_validation=False)
    return dict(result,status='whole_number_outside_template_bounds'if error else'whole_number',
        editable=not error,template_bounds=limits)


def corrected_integer_bits(text,node,limits):
    if type(text)is not str or re.fullmatch(r'-?[0-9]{1,10}',text)is None:
        raise ValueError('Enter a whole number without decimal places.')
    value=int(text)
    if not -(1<<31)<=value<1<<31:raise ValueError('Whole number exceeds the supported signed32 range.')
    if limits is None or limits.payload is None:raise ValueError('The saved template limits must be available before correcting this whole number.')
    bits=value&((1<<64)-1);entry=limits.lookup(node.field_index).entry
    error=check_kind13_bounds(replace(node,raw=bits),entry.limits)if entry else 0
    if error:raise ValueError('Whole number is outside the saved template range.')
    return bits
