"""IRS TY2025 literal DOB/age/death boundary acceptance, not vendor oracles.

Sources: p596 Rule11 (DOB range and death examples), p501 age65 standard
deduction, i1040gi Schedule1A death examples; f8880 Jan1 lower-age boundary.
"""
from copy import deepcopy
import io
import unittest
import tax_engine as engine
import tax_extended as extended
import forms
from pypdf import PdfReader


def prepared(dob='2001-01-01'):
    value=deepcopy(next(row['data'] for row in engine.demo_returns() if row['name']=='Synthetic EIC birthday boundary'))
    value['taxpayer']['birth_date']=dob
    value['schedule_1a']['eligibility_confirmed']=True
    value['elderly_credit'].update(enabled=True,eligibility_confirmed=True,nontaxable_benefits_confirmed=True)
    return value


class PersonDateTests(unittest.TestCase):
    def test_p596_exact_published_DOB_range_reaches_1040_and_refund(self):
        for dob,credit in [('1960-12-31',0),('1961-01-01',649),('1961-01-02',649),
                           ('2000-12-31',649),('2001-01-01',649),('2001-01-02',0)]:
            with self.subTest(dob=dob):
                result=engine.calculate_return(prepared(dob))
                self.assertTrue(result['can_prepare'],result['blocking_issues'])
                self.assertEqual(result['lines']['27a'],credit)
                self.assertEqual(result['lines']['33'],1000+credit)
                self.assertEqual(result['lines']['35a'],1000+credit)

    def test_january1_1961_is_both_senior_and_EIC_eligible(self):
        data=prepared('1961-01-01');data['taxpayer']['age']=35
        normalized=engine.normalized(data);self.assertEqual(normalized['taxpayer']['age'],65)
        result=engine.calculate_return(data)
        policy=result['person_age_rules']['taxpayer']
        self.assertEqual(policy['calendar_age'],64)
        self.assertEqual(policy['day_before_birthday_age'],65)
        self.assertTrue(policy['senior_age65']);self.assertTrue(policy['no_child_eic_age_eligible'])
        self.assertEqual(result['lines']['12e'],17750)
        self.assertEqual(result['lines']['13b'],6000)
        self.assertEqual(result['lines']['27a'],649)

    def test_either_joint_spouse_can_meet_the_DOB_age_test(self):
        data=prepared('2001-01-02');data['filing_status']='mfj'
        data['spouse']['birth_date']='1961-01-01'
        result=engine.calculate_return(data);self.assertEqual(result['lines']['27a'],649)
        data['spouse']['birth_date']='1960-12-31'
        self.assertEqual(engine.calculate_return(data)['lines']['27a'],0)
        data['taxpayer']['birth_date']='2001-01-01'
        self.assertEqual(engine.calculate_return(data)['lines']['27a'],649)

    def test_death_age25_day_before_p596_literal_example(self):
        for death,credit in [('2025-02-12',0),('2025-02-13',649),('2025-02-14',649)]:
            data=prepared('2000-02-14');data['taxpayer']['death_date']=death
            result=engine.calculate_return(data)
            self.assertEqual(result['lines']['27a'],credit)
            self.assertFalse(result['can_prepare'])
            self.assertTrue(any('Final decedent return' in row for row in result['blocking_issues']))

    def test_death_age65_EIC_birthday_and_senior_day_before_differ(self):
        for death,eic,standard,senior in [('2025-02-12',649,15750,0),
                                        ('2025-02-13',649,17750,6000),
                                        ('2025-02-14',0,17750,6000)]:
            data=prepared('1960-02-14');data['taxpayer']['death_date']=death
            result=engine.calculate_return(data)
            self.assertEqual(result['lines']['27a'],eic)
            self.assertEqual(result['lines']['12e'],standard)
            self.assertEqual(result['lines']['13b'],senior)

    def test_joint_death_spouse_age_is_at_death_not_future_birthday(self):
        data=prepared('1958-04-01');data['filing_status']='mfj'
        data['spouse'].update(birth_date='1960-11-01',death_date='2025-08-01')
        result=engine.calculate_return(data)
        self.assertEqual(result['lines']['27a'],649)
        self.assertEqual(result['person_age_rules']['spouse']['calendar_age'],64)
        self.assertFalse(result['person_age_rules']['spouse']['senior_age65'])

    def test_invalid_dates_rejected_before_calculation(self):
        for dob in ('2025-02-29','2001-02-30','2001-13-01','2001-01-1','01/01/2001',
                    '2001-01-01 ',True,None,'2026-01-01','1900-01-01'):
            with self.subTest(dob=dob):
                value=prepared();value['taxpayer']['birth_date']=dob
                with self.assertRaises(ValueError):engine.calculate_return(value)
        for dob,death in [('', '2025-01-01'),('2001-01-01','2024-12-31'),
                          ('2001-01-01','2026-01-01'),('2025-08-01','2025-07-01'),
                          ('2001-01-01','2025-02-29')]:
            value=prepared();value['taxpayer'].update(birth_date=dob,death_date=death)
            with self.assertRaises(ValueError):engine.calculate_return(value)

    def test_valid_Gregorian_leap_DOB_and_normalization_idempotence(self):
        for dob in ('2000-02-29','2004-02-29','1908-02-29'):
            value=prepared(dob);first=engine.normalized(value)
            self.assertEqual(engine.normalized(first),first)
            self.assertEqual(first['taxpayer']['birth_date'],dob)
        self.assertEqual(extended.person_date_rules({'age':35,'birth_date':'2000-02-29'})['calendar_age'],25)

    def test_legacy_age_only_drafts_keep_working(self):
        data=prepared();data['taxpayer'].pop('birth_date');data['taxpayer'].pop('death_date')
        for age,credit in [(24,0),(25,649),(64,649),(65,0)]:
            data['taxpayer']['age']=age
            self.assertEqual(engine.calculate_return(data)['lines']['27a'],credit)
        result=engine.calculate_return(data)
        self.assertEqual(result['person_age_rules']['taxpayer']['basis'],'explicit_age')
        self.assertTrue(any('Without a birth date' in row for row in result['warnings']))

    def test_unclaimed_EIC_discovery_uses_DOB_not_senior_age65(self):
        data=prepared('1961-01-01');data['eitc']['claim']=False
        result=engine.calculate_return(data)
        self.assertTrue(any('Possible EITC eligibility' in row for row in result['blocking_issues']))
        data['taxpayer']['birth_date']='1960-12-31'
        self.assertFalse(any('Possible EITC eligibility' in row for row in engine.calculate_return(data)['blocking_issues']))

    def test_actual_serialized_1040_refund_and_senior_checkbox(self):
        for dob,eic,senior in [('1961-01-01',649,True),('2001-01-01',649,False),('2001-01-02',0,False)]:
            with self.subTest(dob=dob):
                data=engine.normalized(prepared(dob));record={'data':data,'result':engine.calculate_return(data)}
                raw=forms.form1040_pdf(record);reader=PdfReader(io.BytesIO(raw));fields=reader.get_fields()
                p='topmostSubform[0].Page2[0].'
                self.assertEqual(str(fields[p+'f2_23[0]']['/V']),str(eic))
                self.assertEqual(str(fields[p+'f2_31[0]']['/V']),str(1000+eic))
                self.assertEqual(str(fields[p+'c2_5[0]']['/V']),'/1' if senior else '/Off')
                self.assertFalse(any('Final decedent' in row for row in record['result']['blocking_issues']))


if __name__=='__main__':unittest.main()
