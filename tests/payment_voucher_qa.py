"""Independent IRS TY2025 paper-voucher synthetic facts and field oracles."""
from pathlib import Path
import io,json
from pypdf import PdfReader

P='topmostSubform[0].Page1[0].'
FIXTURE=Path(__file__).resolve().parents[1]/'fixtures/payment_voucher_2025.json'

def cases():return json.loads(FIXTURE.read_text())['cases']

def return_for(engine,case):
    d=engine.default_return();d['name']='Synthetic voucher '+case['name']
    d['taxpayer'].update(age=40,birth_date='1985-06-01',valid_ssn=True,valid_tin=True)
    d['eligibility'].update(full_year_us_resident=True,filing_status_confirmed=True,all_income_reported=True,no_amt_preferences=True,capital_gains_eligible=True,eitc_not_applicable=True)
    d['niit'].update(eligibility_confirmed=True,deductions_confirmed=True);d['amt']['eligibility_confirmed']=True
    d['w2']=[dict(engine.ROW_DEFAULTS['w2'],employer='Synthetic employer',wages=str(case['wages']),medicare_wages=str(case['wages']),federal_withholding=str(case['withholding']))]
    d['interest']=[dict(engine.ROW_DEFAULTS['interest'],payer='Synthetic bank',taxable='1000')]
    d['dividends']=[dict(engine.ROW_DEFAULTS['dividends'],payer='Synthetic fund',ordinary='1000',capital_gain_distributions=case['capital'])]
    d['estimated_penalty'].update(enabled=True,prior_year_tax='0',prior_year_agi='0',prior_year_full_12_months=True,prior_year_tax_verified=True,no_prior_year_tax_full_year_resident_confirmed=True,actual_payment_records_confirmed=True)
    d['identity'].update(first_name='Synthetic',middle_initial='A',last_name='Taxpayer',ssn='012345678',address='100 Example Street',apt='2B',city='Example City',state='IL',zip='60000')
    d['filing_details'].update(digital_asset_answer='no',main_home_us_answer='yes',balance_due_payment_method='check_money_order',paper_payment_confirmed=True)
    d['filing_details']['official_form_facts']['schedule_b'].update(foreign_account_answer='no',fbar_required_answer='no',foreign_trust_answer='no',facts_confirmed=True)
    return d

def verify_packet(pdf,amount,official_forms):
    reader=PdfReader(io.BytesIO(pdf));fields=reader.get_fields();expected={}
    # Fixed identities match the public printed2025 voucher rows and widgets,
    # independently of official_forms.MAP. There is no widget f1_4.
    for suffix,value in [('f1_1[0]','012345678'),('f1_3[0]',amount),('f1_5[0]','Synthetic A'),
        ('f1_6[0]','Taxpayer'),('f1_9[0]','100 Example Street'),('f1_10[0]','2B'),
        ('f1_11[0]','Example City'),('f1_12[0]','IL'),('f1_13[0]','60000')]:
        keys=[k for k in fields if k.startswith('f1040v_')and k.endswith('.'+P+suffix)]
        assert len(keys)==1,(suffix,keys);expected[keys[0]]=value
    logical=official_forms.verify_official_pdf(pdf,expected)
    manifest=json.loads(reader.metadata['/TaxRebornPacketManifest']);pages=official_forms.verify_packet_pages(pdf,manifest)
    voucher=[i for i in manifest['instances']if i['form_id']=='f1040v'];assert len(voucher)==1 and voucher[0]['required_pages']==[1,2]
    assert not manifest['filing_packet_ready']
    return {'canonical_and_widget_fields':logical['verified_fields'],'pages':len(reader.pages),
        'voucher_pages':2,'page_identities_verified':pages['page_identities_verified'],'expected_fields':expected,'manifest':manifest}
