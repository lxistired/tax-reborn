"""Finite current kind11 cents -> flavor3 text -> TKE NumericValue ingress.

This independently written reference models the ordinary successful numeric
branch. It does not recover native row UUIDs, run a native DataModel/cache,
apply FixupFields, or compute interest/dividend totals. Caller-owned metadata
must be authenticated separately from a request's self-reported claims.
"""
from dataclasses import dataclass
from decimal import Decimal
import re


@dataclass(frozen=True)
class StoredCents:
    kind: int
    raw64: int
    attributes: int
    header: int = 0
    format_flag10: int = 0
    flag11: int = 0
    packed_exponent: int = 0


def render_current_cents(record):
    """Missing/Unused is absent; Used zero is the present text '0.00'.

    FormatCents for flavor3 passes grouping=False, include_cents=True,
    marker=False. Kind11 fixes scale2; the packed exponent is preserved only.
    Used gates before kind/header/format/raw interpretation.
    """
    if record is None:
        return None
    if type(record) is not StoredCents or type(record.attributes) is not int or not 0<=record.attributes<=65535:
        raise ValueError('Explicit decoded current FV and U16 attributes required')
    if not record.attributes&1:
        return None
    if record.attributes not in (1,3,9,11):
        raise ValueError('Only ordinary Used/Computed/Override current masks are supported')
    if (type(record.kind) is not int or record.kind!=11 or type(record.raw64) is not int
            or not 0<=record.raw64<(1<<64) or record.header!=0 or record.format_flag10!=0
            or type(record.flag11) is not int or not 0<=record.flag11<=255
            or type(record.packed_exponent) is not int or not 0<=record.packed_exponent<=255):
        raise ValueError('Ordinary kind11 header0/current-format0 storage required')
    coefficient=record.raw64 if record.raw64<(1<<63) else record.raw64-(1<<64)
    if abs(coefficient)>10**11:
        raise ValueError('Finite cents magnitude at most one billion USD required')
    whole,cents=divmod(abs(coefficient),100)
    return ('-'if coefficient<0 else'')+str(whole)+'.'+str(cents).zfill(2)


def create_numeric_input(text):
    """Successful native NumericValue precision2 subset, no schema rounding.

    Native FromString admits more syntax and diagnostics. This reference only
    accepts the exact canonical lexeme emitted by the finite format3 renderer.
    Empty/blank is supplied through the separate presence gate, never numeric0.
    """
    if text is None:
        return None
    if type(text) is not str or re.fullmatch(r'-?(?:0|[1-9][0-9]{0,9})\.[0-9]{2}',text) is None:
        raise ValueError('Canonical flavor3 cents text or explicit absence required')
    value=Decimal(text)
    if abs(value)>Decimal(10**9):
        raise ValueError('Finite numeric input magnitude exceeded')
    return value


def current_numeric_input(record):
    return create_numeric_input(render_current_cents(record))


def read_interest_input_request(request, *, binary_loader, approved_metadata):
    """Actual decoded source owner/full-ID lookup, then numeric ingress.

    The source-qualified five-field profile currently has an existing-owner
    bridge only for direct F1099I children. This wrapper deliberately refuses
    native UUID requests and does not relabel this row identity as a UUID.
    """
    from summary_child_current_reference import read_request
    source=read_request(request,binary_loader=binary_loader,approved_metadata=approved_metadata)
    field=source['field'];record=None
    if 'raw64' in field:
        record=StoredCents(field['kind'],int(field['raw64']),field['FV_attributes'],field['value_header'],field['format_flag10'],field['uninterpreted_flag11'],field['packed_exponent'])
    text=render_current_cents(record);value=create_numeric_input(text)
    reference={'L1':9400,'L3':9401,'EXINT':9441}.get(request['field_id'])
    if reference is None:
        raise ValueError('Only the source-bound three F1099I fields are supported')
    return {'current_source':source,'graph_input_reference':reference,
        'rendered_text':text,'present':value is not None,'numeric_amount':None if value is None else format(value,'f'),
        'numeric_value_type':2,'numeric_read_precision':2,'schema_integer_does_not_round_this_input_to_whole_dollars':True,
        'native_row_UUID_verified':False,'native_DataModel_executed':False,
        'current_record_and_request_unchanged':True,'comparison_only':True,'can_commit_to_source':False,
        'unclosed':['native runtime row UUID','native current table/record initialization',
            'interest/dividend adjustment and total graph','automatic native queue/global parity']}
