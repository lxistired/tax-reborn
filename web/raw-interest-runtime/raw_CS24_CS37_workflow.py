"""Confirmed same-source session for prospective interest adjustments.

The old observed-adjustment workflow remains byte-identical. This separate
session accepts no supplied temporary values and performs no source writes.
"""
import raw_interest_workflow as observed
import raw_CS24_CS37_request as prospective

_session = None
LIMITS = [
 'L4 and L8A are bounded interest projections, not final tax, refund or amount owed.',
 'Temporary adjustments are calculated from this source, then applied prospectively to the bounded interest path.',
 'Loaded fields, a calculated baseline using saved ADJUST, and the proposed result are separate values.',
 'Existing Used ADJUST amounts, including zero, are refused. Native blank deletion and temporary Override cases remain unsupported.',
 'Retained existing temporary operands are identified; they are not freshly recalculated.',
 'INPUT10770 uses retained storage; EE uses the qualified married-filing-separately normal-return condition.',
 'Native inventory, row UUID mapping, output admission, TPS writes, the dependency queue and full F1040 R2 are not run.',
 'This comparison cannot write the source or replace the App IRS calculation. Mobile support requires separate validation.'
]

def inspect_request(payload):
 global _session
 _session = None
 value = observed.inspect_request(payload)
 selection = {k:value[k] for k in ('source_sha256','summary_path','source_formset_index','row_number','field_id','need_native_row_uuid')}
 value = dict(value, limitations=LIMITS, calculation_mode='prospective_CS24_CS37')
 value.pop('inspection_token')
 fingerprint = observed._fingerprint(payload)
 token = observed._fingerprint(dict(pair=fingerprint,inspection=value))
 _session = dict(pair=fingerprint,selection=selection,token=token)
 return dict(inspection_token=token,**value)

def calculate_request(payload):
 if type(payload) is not dict or set(payload)!={'pair','inspection_token','confirmed'} or payload['confirmed'] is not True:
  raise ValueError('Confirm the current same-source inspection before comparison')
 if _session is None or payload['inspection_token']!=_session['token'] or observed._fingerprint(payload['pair'])!=_session['pair']:
  raise ValueError('Source or resources changed; inspect and confirm them again')
 pair=payload['pair'];selection=_session['selection']
 request=dict(source=pair['source'],local_resource=pair['local_resource'],expected_source_sha256=selection['source_sha256'],**{k:v for k,v in selection.items() if k!='source_sha256'})
 result=prospective.calculate_request(request)
 return dict(result=result,inspection_token=_session['token'],same_source_inspection_verified=True,comparison_only=True,writeback_allowed=False,physical_writes=0)
