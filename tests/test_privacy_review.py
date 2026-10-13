import copy
import io
import unittest
from pypdf import PdfReader
import forms
import privacy_review
import tax_engine


class MaskedReviewTests(unittest.TestCase):
    def record(self):
        data = tax_engine.default_return()
        data['w2'] = [{'employer': 'Synthetic Widgets', 'wages': '60000', 'federal_withholding': '6500'}]
        data['identity'].update(first_name='Synthetic', last_name='Person', ssn='900121234',
                                address='1 Example Road', city='Example', state='CA', zip='00000')
        data['filing_details'].update(refund_delivery='direct_deposit', bank_routing='021000021',
                                      bank_account='99000000123456', bank_type='checking')
        return {'data': data, 'result': tax_engine.calculate_return(data)}

    def test_actual_pdf_masks_identifiers_and_preserves_tax_fields(self):
        record = self.record(); raw = forms.masked_review_pdf(record)
        fields = PdfReader(io.BytesIO(raw)).get_fields()
        original = {**forms.identity_values(record), **forms.filing_values(record)}
        for key in privacy_review.identifier_fields() & original.keys():
            self.assertEqual(str(fields[key]['/V']), '*' * len(str(original[key])))
        for key, value in forms.field_values(record['result']).items():
            self.assertEqual(str(fields[key]['/V']), str(value))
        proof = privacy_review.verify_no_identifiers(raw, privacy_review.tokens(original))
        self.assertTrue(proof['selected_identifiers_absent']); self.assertEqual(proof['pages'], 3)
        self.assertIn('Synthetic', fields['topmostSubform[0].Page1[0].f1_14[0]']['/V'])

    def test_spouse_and_dependent_identifiers_use_their_actual_fields(self):
        record = self.record(); data = record['data']; data['filing_status'] = 'mfj'
        data['identity'].update(spouse_first_name='Synthetic', spouse_last_name='Partner', spouse_ssn='900981234')
        data['dependents'] = [{'name': 'Synthetic child', 'age': 8, 'form_first_name': 'Synthetic',
                               'form_last_name': 'Child', 'form_ssn': '901451234'}]
        record['result'] = tax_engine.calculate_return(data)
        raw = forms.masked_review_pdf(record); fields = PdfReader(io.BytesIO(raw)).get_fields()
        self.assertEqual(fields['topmostSubform[0].Page1[0].f1_19[0]']['/V'], '*********')
        self.assertEqual(fields['topmostSubform[0].Page1[0].Table_Dependents[0].Row3[0].f1_39[0]']['/V'], '*********')
        privacy_review.verify_no_identifiers(raw, {'900981234', '901451234'})

    def test_saved_record_and_ordinary_export_are_unchanged(self):
        record = self.record(); before = copy.deepcopy(record)
        forms.masked_review_pdf(record); self.assertEqual(record, before)
        raw, _ = forms._official_1040(record)
        fields = PdfReader(io.BytesIO(raw)).get_fields()
        self.assertEqual(fields['topmostSubform[0].Page1[0].f1_16[0]']['/V'], '900121234')
        self.assertEqual(fields['topmostSubform[0].Page2[0].AccountNo[0].f2_33[0]']['/V'], '99000000123456')

    def test_identifier_in_unmasked_free_text_refuses_export(self):
        record = self.record(); record['data']['identity']['city'] = 'Example 900121234'
        with self.assertRaisesRegex(ValueError, 'export refused'):
            forms.masked_review_pdf(record)

    def test_invalid_source_identifier_does_not_fall_back_to_unmasked_export(self):
        record = self.record(); record['data']['identity']['ssn'] = 'malformed'
        with self.assertRaisesRegex(ValueError, '9 digits'):
            forms.masked_review_pdf(record)

    def test_missing_identifiers_can_still_export_a_labeled_review_copy(self):
        record = self.record(); record['data']['identity']['ssn'] = ''
        record['data']['filing_details']['refund_delivery'] = 'paper_check'
        raw = forms.masked_review_pdf(record); reader = PdfReader(io.BytesIO(raw))
        self.assertIn('MASKED IDENTIFIERS', reader.pages[0].extract_text())
        self.assertIn('not a filing packet', reader.pages[0].extract_text())


if __name__ == '__main__':
    unittest.main()
