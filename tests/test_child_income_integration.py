"""Independent IRS TY2025 parent-return and original-paper-field checks.

Synthetic identities only. Expected amounts below are literal IRS worksheet
results, not snapshots derived from the implementation or vendor graphs.
"""
from copy import deepcopy
import io
import unittest
from pypdf import PdfReader
import tax_engine as engine
import forms
import official_forms
from tests.test_child_income import row


def prepared():
    return deepcopy(next(x['data'] for x in engine.demo_returns()
                         if x['name']=='Synthetic parent and child income'))


def record(data):
    return {'data':data,'result':engine.calculate_return(data)}


class ChildIncomeIntegrationTests(unittest.TestCase):
    def test_independent_parent_tax_and_investment_chain(self):
        result=engine.calculate_return(prepared())
        self.assertTrue(result['can_prepare'],result['blocking_issues'])
        # Allocated 195 qualified +325 capital +780 ordinary; full child
        # interest/dividends4000 must not be included a second time.
        for line,value in {'2a':0,'2b':0,'3a':195,'3b':195,'7a':325,'8':780,
                           '9':201300,'11b':201300,'15':185550,'16':37467,
                           '24':37516,'35a':12484}.items():
            with self.subTest(line=line):self.assertEqual(result['lines'][line],value)
        self.assertEqual(result['schedules']['form_8960']['form_lines']['7'],780)
        self.assertEqual(result['schedules']['form_8960']['form_lines']['8'],1300)
        self.assertEqual(result['schedules']['form_8960']['tax'],49)
        self.assertEqual(result['schedules']['form_6251']['form_lines']['10'],37467)

    def test_child_tax_is_part_of_regular_comparator_before_amt(self):
        d=prepared();d['eligibility']['no_amt_preferences']=False
        d['amt'].update(iso_adjustment='100000',eligibility_confirmed=True)
        r=engine.calculate_return(d)
        self.assertTrue(r['can_prepare'],r['blocking_issues'])
        # AMTI301300 - exemption88100 =213200; ordinary212680 at26%
        # plus520 preferred at15% =55375 TMT. Compare with regular37467.
        self.assertEqual(r['schedules']['form_6251']['form_lines']['9'],55375)
        self.assertEqual(r['schedules']['form_6251']['form_lines']['10'],37467)
        self.assertEqual(r['schedules']['form_6251']['tax'],17908)
        self.assertEqual(r['lines']['24'],55424)
        self.assertEqual(r['lines']['37'],5424)

    def test_eic_tax_exempt_child_income_blocks_investment_limit(self):
        d=prepared();d['w2'][0].update(wages='10000',social_security_wages='10000',medicare_wages='10000',social_security_withholding='620',medicare_withholding='145')
        d['eligibility']['eitc_not_applicable']=False
        d['eitc'].update(claim=True,eligibility_confirmed=True,not_qualifying_child_of_another=True,no_disallowed_claim_history=True,main_home_us_half_year=True)
        d['child_income_election']['children']=[row(taxable_interest='4000',tax_exempt_interest='12000')]
        r=engine.calculate_return(d)
        self.assertTrue(r['can_prepare'],r['blocking_issues'])
        self.assertEqual(r['lines']['2a'],0)
        self.assertEqual(r['lines']['8'],1300)
        self.assertEqual(r['lines']['27a'],0)
        self.assertEqual(r['schedules']['form_8814']['eitc_other_investment_income'],13300)
        self.assertTrue(any('investment' in x for x in r['schedules']['schedule_eic']['ineligible_reasons']))

    def test_investment_interest_excludes_child_qualified_and_capital(self):
        d=prepared();d['itemized'].update(investment_interest='2000',force_itemized=True)
        d['eligibility']['itemized_eligible']=True
        d['niit']['investment_interest_eligible']=True
        r=engine.calculate_return(d)
        self.assertTrue(r['can_prepare'],r['blocking_issues'])
        self.assertEqual(r['schedules']['form_4952']['deduction'],780)
        self.assertEqual(r['schedules']['form_4952']['carryout'],1220)
        self.assertEqual(r['schedules']['schedule_a']['investment_interest'],780)

    def test_own_parent_payers_are_added_without_duplication(self):
        d=prepared();d['interest']=[dict(engine.ROW_DEFAULTS['interest'],payer='Parent bank',taxable='500')]
        d['dividends']=[dict(engine.ROW_DEFAULTS['dividends'],payer='Parent broker',ordinary='300',qualified='200',capital_gain_distributions='400')]
        d['eligibility'].update(qualified_dividends_eligible=True,capital_gains_eligible=True)
        r=engine.calculate_return(d)
        self.assertEqual(r['lines']['2b'],500);self.assertEqual(r['lines']['3a'],395)
        self.assertEqual(r['lines']['3b'],495);self.assertEqual(r['lines']['7a'],725)
        self.assertEqual(r['lines']['8'],780);self.assertEqual(r['lines']['11b'],202500)

    def test_per_child_official_copies_and_exact_split_fields(self):
        d=prepared();d['child_income_election']['children'].append(row(name='Second Synthetic Child',ssn='222222222',taxable_interest='4000'))
        p=official_forms.build_official_packet(record(d))
        child=[x for x in p['forms'] if x['id']=='f8814']
        self.assertEqual(len(child),2)
        self.assertTrue(p['verification']['widget_values_and_appearances_verified'])
        reader=PdfReader(io.BytesIO(p['pdf_bytes']));fields=reader.get_fields()
        prefix='topmostSubform[0].Page1[0].'
        def field(copy,key):
            matches=[v for k,v in fields.items() if k.startswith('f8814_'+str(copy)+'.') and k.endswith(prefix+key)]
            self.assertEqual(len(matches),1);return str(matches[0].get('/V',''))
        for copy,tin in ((0,'111111111'),(1,'222222222')):
            self.assertEqual(field(copy,'f1_04[0]'),tin)
            self.assertEqual(field(copy,'c1_1[0]'),'/1')
            self.assertEqual(field(copy,'f1_23[0]'),'135')
        self.assertEqual(field(0,'f1_13[0]'),'0');self.assertEqual(field(0,'f1_14[0]'),'150')
        self.assertEqual(field(0,'f1_15[0]'),'0');self.assertEqual(field(0,'f1_16[0]'),'250')
        # Below/skipped allocation fields are actually blank on copy2.
        self.assertEqual(field(1,'f1_14[0]'),'')
        self.assertEqual(engine.calculate_return(d)['schedules']['form_8814']['additional_tax'],270)

    def test_complete_parent_packet_reopened_values_widgets_and_annotation(self):
        d=prepared();r=record(d);status=forms.packet_status(r)
        self.assertTrue(status['paper_preparation_complete'],status['missing_facts'])
        blob=forms.paper_packet_pdf(r);reader=PdfReader(io.BytesIO(blob))
        self.assertEqual(len(reader.pages),12)
        fields=reader.get_fields()
        # Real1040line16 checkbox1 is c2_9, not dependent checkbox c2_1.
        boxes=[v for k,v in fields.items() if k.endswith('.Page2[0].c2_9[0]')]
        self.assertEqual(len(boxes),1);self.assertEqual(str(boxes[0].get('/V')),'/1')
        dpage=next(p for p in reader.pages if str(p.get('/TaxRebornForm',''))=='f1040sd')
        self.assertIn('Form 8814 - $325',dpage.extract_text())
        names=[str(v.get('/V','')) for k,v in fields.items() if k.startswith('f1040sb_')]
        self.assertIn('Form 8814',names);self.assertIn('195',names)
        supporting=official_forms.build_official_packet(r)
        self.assertEqual(next(f for f in supporting['forms'] if f['id']=='f1040s1')['line_values']['8z'],780)
        self.assertTrue(supporting['verification']['canonical_values_verified'])

    def test_child_confirmation_invalidation_preserves_record_and_blocks_return(self):
        d=prepared();d['child_income_election']['children'][0]['eligible_parent_confirmed']=False
        r=engine.calculate_return(d)
        self.assertFalse(r['can_prepare']);self.assertEqual(r['lines']['8'],0)
        self.assertEqual(r['lines']['3a'],0);self.assertEqual(r['lines']['7a'],0)
        self.assertFalse(forms.packet_status(record(d))['paper_preparation_complete'])

    def test_parent_broker_facts_are_not_invented_by_child_confirmation(self):
        d=prepared();d['filing_details']['official_form_facts']['schedule_b']['facts_confirmed']=False
        p=forms.packet_status(record(d))
        self.assertFalse(p['paper_preparation_complete'])
        self.assertTrue(any('ScheduleB' in x or 'Schedule B' in x for x in p['missing_facts']))

if __name__=='__main__':unittest.main()
