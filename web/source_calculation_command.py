"""App command boundary for local finite source comparison; zero source writes.

Authority is an App-owned bundled hash/selector configuration. The request
cannot upload claims or grant commit permission. Original resources arrive
only from the user's selected local files, in the current worker message.
"""
from pathlib import Path
from decimal import Decimal
import base64
import json
import hashlib
import tax_engine
import binary_tax
from interop.form_core.native_amount import decode_amount
from interop.form_core.hash_structure_reference import validate_document_hashes
from source_calculation_request import calculate_request
import normal_wage_projection_reference as wages
import source_calculation_reference as chain

_AUTHORITY = json.loads(Path(__file__).with_name('source-calculation-authority.json').read_text())


def _prepare(payload):
    if type(payload) is not dict or set(payload) != {'source', 'source_profile_id', 'calculation_carriers'}:
        raise ValueError('Select the current source document and local calculation resources.')
    pid = payload['source_profile_id']
    if type(pid) is not str or pid not in _AUTHORITY:
        raise ValueError('Choose an App-approved local calculation profile.')
    authority = _AUTHORITY[pid]
    rows = payload['calculation_carriers']
    if type(rows) is not list or not 1 <= len(rows) <= 32:
        raise ValueError('Select all files required by the approved profile.')
    carriers=[];total=0
    for row in rows:
        if type(row) is not dict or set(row) != {'name','base64','sha256'}:
            raise ValueError('Invalid local resource file.')
        if type(row['base64']) is not str or len(row['base64']) > 128*1024*1024:
            raise ValueError('Resource exceeds the supported size.')
        try: wire=base64.b64decode(row['base64'],validate=True)
        except Exception as error: raise ValueError('Invalid resource file encoding.') from error
        total+=len(wire)
        if total>192*1024*1024:raise ValueError('Selected resources exceed the supported total size.')
        carriers.append(chain.CarrierBytes(row['name'],wire,row['sha256']))
    profile=wages.prepare_profile(tuple(carriers),authority['chain_claim'],authority['wage_claim'])
    return pid,profile


def inspect_source(payload):
    pid,profile=_prepare(payload)
    report,doc,buffers,bound=binary_tax._inspect(payload['source'])
    validate_document_hashes(doc)
    fsid=_AUTHORITY[pid]['wage_claim']['raw_form']['formset_id']
    matches=[(i,fs) for i,fs in enumerate(doc.formsets) if fs.header.identifier==fsid.encode()]
    if len(matches)!=1:raise ValueError('The source needs one exact approved form set.')
    index,fs=matches[0]
    relevant=set(profile.chain_profile.forms)|{'FW2'}
    selected={(row['formset_id'],row['form_id']):(row['carrier_sha256'],row['resource_id'])
        for row in payload['source']['profile']['templates']}
    for form in fs.forms:
        fid=form.header.identifier.decode()
        if fid not in relevant:continue
        expected=_AUTHORITY[pid]['wage_claim']['raw_form'] if fid=='FW2' else next(
            row for row in _AUTHORITY[pid]['chain_claim']['selected_forms'] if row['form_id']==fid)
        if selected.get((fsid,fid))!=(expected['carrier_sha256'],expected['resource_id']):
            raise ValueError('Current source template differs from this approved calculation profile.')
    def has_nested(form):return any(child.header.identifier.decode() in relevant or has_nested(child) for child in form.children)
    if any(has_nested(form) for form in fs.forms):raise ValueError('This comparison does not support nested wage/current calculation forms.')
    present=[form.header.identifier.decode() for form in fs.forms]
    if 'FW2' not in present:raise ValueError('Load a source with an existing wage form.')
    known=set(present)&set(profile.chain_profile.forms)
    if any(present.count(fid)!=1 for fid in known):raise ValueError('More than one current copy needs a separately reviewed selector.')
    facts=[]
    for form in report['binary_archive']['forms']:
        if form['path'][0]!=index:continue
        for value in form['fields']:
            facts.append({'form':form['form_id'],'document_file_copy':form['file_copy'],
                'field':value['field_id'],'amount':value['text'],'status':value['status'],
                'used':bool(value['specific_attributes']&1),'override':bool(value['specific_attributes']&8),
                'source_ordinal':value.get('source_ordinal',value['ordinal']),
                'current_ordinal':value.get('current_ordinal',value['ordinal']),
                'kind':value['kind'],'FV_attributes':value['specific_attributes']})
    return {'status':'source_ready_for_explicit_context_review','source_sha256':report['source_sha256'],
        'source_profile_sha256':report['wire_profile_sha256'],
        'source_profile_id':pid,'formset_id':fsid,'loaded_fields':facts,
        'current_form_identities':[{'form':form.header.identifier.decode(),'document_file_copy':form.header.file_copy,
            'runtime_copy_number':form.header.word7c,'source_path':[index,n]}
            for n,form in enumerate(fs.forms) if form.header.identifier.decode() in relevant],
        'prepared_absent_forms':sorted(set(profile.chain_profile.forms)-known),
        'resources_verified':len(payload['calculation_carriers']),
        'resource_bytes':sum(len(base64.b64decode(row['base64'])) for row in payload['calculation_carriers']),
        'profile_provenance_scope':profile.chain_profile.provenance_scope,
        'source_carrier_limit':9,'calculation_carriers_are_a_separate_channel':True,
        'unclosed_supplies':['Raw interest/dividend aggregation and summary freshness',
            'Deduction and payment producers','Filing status eligibility','Native factory/template/FixupFields and dependency queue'],
        'source_modified':False,'writeback_allowed':False,'comparison_only':True}


def _return_hash(value):
    if type(value) is not dict:raise ValueError('Provide the complete current App return.')
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def current_app_snapshot(value):
    digest=_return_hash(value)
    result=tax_engine.calculate_return(value)
    if _return_hash(value)!=digest:raise ValueError('Current App input changed during calculation.')
    return {'current_return_sha256':digest,'result':result,'input_unchanged':True}


def compare_source(payload):
    keys={'request','expected_source_profile_sha256','current_app_return','expected_current_app_return_sha256','comparison_acknowledged'}
    if type(payload) is not dict or set(payload)!=keys:
        raise ValueError('Use the reviewed source request and complete current App return.')
    if type(payload['comparison_acknowledged']) is not bool:
        raise ValueError('Explicit comparison-pair confirmation required.')
    if binary_tax.prep.canonical_hash(payload['request']['source']['profile'])!=payload['expected_source_profile_sha256']:
        raise ValueError('Source metadata profile changed since comparison review.')
    app=payload['current_app_return'];current_hash=payload['expected_current_app_return_sha256']
    if app is None:
        if current_hash is not None:raise ValueError('A current App hash needs the full matching return.')
        current_snapshot=None
    else:
        if payload['comparison_acknowledged'] is not True:
            raise ValueError('Confirm this source/current App return pair and the reviewed context differences.')
        if _return_hash(app)!=current_hash:raise ValueError('Current App return changed since comparison review.')
        current_snapshot=current_app_snapshot(app)
    result=calculate_request(payload['request'],approved_profiles=_AUTHORITY,
        binary_loader=binary_tax._context,amount_decoder=decode_amount)
    existing=current_snapshot['result']['summary'] if current_snapshot else {}
    def amount(value):
        if value is None:return None
        if type(value) not in (str,int):raise ValueError('Comparison amounts require exact decimal values.')
        out=Decimal(value)
        if not out.is_finite() or abs(out)>10**9:raise ValueError('Comparison amount exceeds the supported range.')
        return out
    current={key:amount(existing[key]) for key in ('total_tax','amount_owed','refund','payments','taxable_income') if key in existing}
    source_tax=amount(result['calculation']['final_tax_L57'])
    source_owed=amount(result['calculation']['final_owed_L69'])
    paid=result['calculation']['current_fields']['F1040']['L65']
    source_payments=amount(paid['amount']) if paid and paid['attributes']&1 else None
    if (source_tax is not None and source_tax<0) or (source_payments is not None and source_payments<0):
        raise ValueError('Source tax/payment result is outside the supported nonnegative comparison range.')
    source_balance=source_tax-source_payments if source_tax is not None and source_payments is not None else None
    current_balance=current['total_tax']-current['payments'] if current else None
    comparison={'current_app_summary':{key:None if value is None else str(value) for key,value in current.items()},
        'source_total_tax':None if source_tax is None else str(source_tax),
        'source_amount_owed':None if source_owed is None else str(source_owed),
        'source_payments':None if source_payments is None else str(source_payments),
        'source_signed_balance':None if source_balance is None else str(source_balance),
        'current_app_signed_balance':None if current_balance is None else str(current_balance),
        'total_tax_difference':None if source_tax is None or current.get('total_tax') is None else str(source_tax-current['total_tax']),
        'amount_owed_difference':None if source_owed is None or current.get('amount_owed') is None else str(source_owed-current['amount_owed']),
        'payments_difference':None if source_payments is None or current.get('payments') is None else str(source_payments-current['payments']),
        'signed_balance_difference':None if source_balance is None or current_balance is None else str(source_balance-current_balance),
        'balance_definition':'total tax minus payments; positive owed, negative overpaid',
        'source_signed_balance_is_comparison_derived':True,
        'source_refund_not_calculated':True,'current_App_result_unchanged':True,
        'current_App_summary_source':'calculated_from_complete_current_App_return' if app is not None else 'not_connected',
        'current_App_return_sha256':current_hash,'source_current_return_pair_acknowledged':payload['comparison_acknowledged'] is True,
        'source_profile_sha256':payload['expected_source_profile_sha256'],
        'identical_input_context_or_engine_parity_asserted':False}
    return {'status':'local_source_comparison','comparison':comparison,'source_calculation':result,
        'source_modified':False,'writeback_allowed':False,'comparison_only':True,
        'original_resource_files_bundled':False,'IRS_engine_replaced':False,
        'IRS_engine_called_for_complete_current_return':app is not None}
