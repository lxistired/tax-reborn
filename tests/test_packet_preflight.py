"""Real serialized-page failures must block a paper-preparation export.

The page/copy expectations use public IRS templates and synthetic tax cases.
No renderer Success flag or advertised page count is accepted as a page oracle.
"""
from copy import deepcopy
import io
import json
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NumberObject, TextStringObject
import forms
import official_forms
import tax_engine
from tests.test_official_forms import business_sample
from tests.test_paper_packet import example


def rewritten(raw,change):
    writer=PdfWriter();writer.clone_document_from_reader(PdfReader(io.BytesIO(raw)))
    change(writer)
    target=io.BytesIO();writer.write(target)
    return target.getvalue()


class PacketPreflightAcceptance(unittest.TestCase):
    def test_required_blank_page_cannot_disappear_behind_a_successful_field_readback(self):
        form=official_forms.render_official_form('f1040sc',{'31':90000})
        # Page2 has no filled expected values in this case. Existing field/value
        # verification alone accepts the truncated PDF; packet preflight must not.
        dropped=rewritten(form['pdf_bytes'],lambda writer:writer.remove_page(1))
        official_forms.verify_official_pdf(dropped,form['values'])
        with self.assertRaisesRegex(ValueError,'page count differs'):
            official_forms.verify_packet_pages(dropped,official_forms.packet_manifest([form['packet_instance']]))

    def test_actual_renderer_page_loss_blocks_the_application_support_packet(self):
        original=official_forms.render_official_form
        def bad_renderer(**spec):
            form=original(**spec)
            if form['id']=='f1040sc':
                form['pdf_bytes']=rewritten(form['pdf_bytes'],lambda writer:writer.remove_page(1))
                # Leave the old successful verification/count untouched.
            return form
        with patch.object(official_forms,'render_official_form',side_effect=bad_renderer):
            with self.assertRaisesRegex(ValueError,'page count differs'):
                forms.paper_packet_pdf(business_sample())

    def test_unknown_form_owner_cannot_fall_back_to_taxpayer(self):
        record=business_sample();record['result']['schedules']['schedule_c'][0]['owner']='dependent'
        with self.assertRaisesRegex(ValueError,'Unsupported packet owner'):
            official_forms.build_official_packet(record)

    def test_duplicate_composite_copy_identity_is_rejected(self):
        instance=official_forms.packet_instance('f1040sc','taxpayer',1,2)
        with self.assertRaisesRegex(ValueError,'Duplicate packet copy identity'):
            official_forms.packet_manifest([instance,deepcopy(instance)])

    def test_unsupported_page_gaps_and_repeated_pages_are_rejected(self):
        instance=official_forms.packet_instance('f1040sc','taxpayer',1,2)
        for pages in ([1,3],[1,1],[2,1]):
            with self.subTest(pages=pages):
                with self.assertRaisesRegex(ValueError,'unsupported gap or duplicate'):
                    official_forms.packet_manifest([{**instance,'required_pages':pages}])

    def test_boolean_or_nonpositive_copy_and_page_counts_are_rejected(self):
        for copy_index,page_count in ((True,2),(0,2),(-1,2),(1,True),(1,0)):
            with self.subTest(copy=copy_index,pages=page_count):
                self.assertRaises(ValueError,official_forms.packet_instance,'f1040sc','taxpayer',copy_index,page_count)

    def test_two_business_copies_survive_merge_with_distinct_page_identity(self):
        record=business_sample()
        record['data']['businesses'].append({**record['data']['businesses'][0],'name':'Second Example','revenue':'20000','expenses':'1000'})
        record['result']=tax_engine.calculate_return(record['data'])
        packet=official_forms.build_official_packet(record)
        planned=[item for item in packet['packet_manifest']['instances'] if item['form_id']=='f1040sc']
        self.assertEqual([(item['owner'],item['copy_index'],item['required_pages']) for item in planned],
                         [('taxpayer',1,[1,2]),('taxpayer',2,[1,2])])
        pages=PdfReader(io.BytesIO(packet['pdf_bytes'])).pages
        actual=[(page['/TaxRebornCopy'],page['/TaxRebornTemplatePage']) for page in pages if page['/TaxRebornForm']=='f1040sc']
        self.assertEqual(actual,[(1,1),(1,2),(2,1),(2,2)])
        self.assertTrue(packet['verification']['packet_preflight']['page_identities_verified'])

    def test_taxpayer_and_spouse_copies_do_not_share_identity(self):
        record=business_sample();data=record['data'];data['filing_status']='mfj'
        data['identity'].update(spouse_first_name='Example',spouse_last_name='Spouse',spouse_ssn='123456788')
        data['businesses'].append({**data['businesses'][0],'owner':'spouse','name':'Spouse Example','revenue':'20000','expenses':'1000'})
        record['result']=tax_engine.calculate_return(data)
        packet=official_forms.build_official_packet(record)
        planned=[item for item in packet['packet_manifest']['instances'] if item['form_id']=='f1040sc']
        self.assertEqual([(item['owner'],item['copy_index']) for item in planned],[('taxpayer',1),('spouse',1)])

    def test_renderer_cannot_substitute_another_owner(self):
        original=official_forms.render_official_form
        def bad_renderer(**spec):
            form=original(**spec);form['owner']='spouse';return form
        with patch.object(official_forms,'render_official_form',side_effect=bad_renderer):
            with self.assertRaisesRegex(ValueError,'required form/owner/copy/year'):
                official_forms.build_official_packet(business_sample())

    def test_spouse_pages_cannot_be_replaced_by_taxpayer_copy_with_same_count(self):
        record=business_sample();data=record['data'];data['filing_status']='mfj'
        data['identity'].update(spouse_first_name='Example',spouse_last_name='Spouse',spouse_ssn='123456788')
        data['businesses'].append({**data['businesses'][0],'owner':'spouse','name':'Spouse Example','revenue':'20000','expenses':'1000'})
        record['result']=tax_engine.calculate_return(data)
        original=official_forms.render_official_form
        def bad_renderer(**spec):
            form=original(**spec)
            if form['id']=='f1040sc' and form['owner']=='spouse':
                def replace_owner(writer):
                    for page in writer.pages:page[NameObject('/TaxRebornOwner')]=TextStringObject('taxpayer')
                form['pdf_bytes']=rewritten(form['pdf_bytes'],replace_owner)
            return form
        with patch.object(official_forms,'render_official_form',side_effect=bad_renderer):
            with self.assertRaisesRegex(ValueError,'identity differs'):
                forms.paper_packet_pdf(record)

    def test_success_flag_cannot_replace_an_actual_draft(self):
        original=official_forms.render_official_form
        def bad_renderer(**spec):
            form=original(**spec);form['status']='Success';return form
        with patch.object(official_forms,'render_official_form',side_effect=bad_renderer):
            with self.assertRaisesRegex(ValueError,'did not produce a draft'):
                official_forms.build_official_packet(business_sample())

    def test_page_duplicate_does_not_pass_when_total_count_matches(self):
        form=official_forms.render_official_form('f1040sc',{'31':90000})
        def duplicate_identity(writer):
            writer.pages[1][NameObject('/TaxRebornTemplatePage')]=NumberObject(1)
        raw=rewritten(form['pdf_bytes'],duplicate_identity)
        with self.assertRaisesRegex(ValueError,'identity differs at output page 2'):
            official_forms.verify_packet_pages(raw,official_forms.packet_manifest([form['packet_instance']]))

    def test_string_copy_identity_is_rejected_even_if_its_printed_value_matches(self):
        form=official_forms.render_official_form('f1040sc',{'31':90000})
        raw=rewritten(form['pdf_bytes'],lambda writer:writer.pages[0].__setitem__(NameObject('/TaxRebornCopy'),TextStringObject('1')))
        self.assertRaises(ValueError,official_forms.verify_packet_pages,raw,official_forms.packet_manifest([form['packet_instance']]))

    def test_page_order_is_verified_after_serialization(self):
        form=official_forms.render_official_form('f1040sc',{'31':90000})
        def reorder(writer):
            # Swap the serialized page-tree references. Inserting a page that
            # already belongs to the writer can reuse its original position.
            kids=writer._pages.get_object()['/Kids'];kids[0],kids[1]=kids[1],kids[0]
        raw=rewritten(form['pdf_bytes'],reorder)
        with self.assertRaisesRegex(ValueError,'identity differs at output page 1'):
            official_forms.verify_packet_pages(raw,official_forms.packet_manifest([form['packet_instance']]))

    def test_packet_status_rechecks_actual_bytes_instead_of_cached_success(self):
        record=business_sample();packet=official_forms.build_official_packet(record)
        packet['pdf_bytes']=b''
        with self.assertRaisesRegex(ValueError,'Required packet output is empty'):
            forms.packet_status(record,packet)

    def test_final_paper_packet_contains_serialized_cover_main_and_support_manifest(self):
        record=business_sample();before=deepcopy(record)
        raw=forms.paper_packet_pdf(record);reader=PdfReader(io.BytesIO(raw))
        manifest=json.loads(reader.metadata['/TaxRebornPacketManifest'])
        self.assertEqual(manifest['instances'][0]['form_id'],'preparation_checklist')
        self.assertEqual(manifest['instances'][1]['form_id'],'f1040')
        self.assertEqual(manifest['instances'][1]['required_pages'],[1,2])
        proof=official_forms.verify_packet_pages(raw,manifest)
        self.assertEqual(proof['actual_pages'],len(reader.pages));self.assertFalse(manifest['filing_packet_ready'])
        self.assertEqual(record,before)

    def test_final_export_page_loss_is_rejected_even_with_all_filled_fields_present(self):
        class MissingChecklistWriter(PdfWriter):
            def write(self,stream):
                if self.metadata and self.metadata.get('/Title')=='Tax Reborn 2025 official paper-preparation draft':
                    self.remove_page(0)
                return super().write(stream)
        with patch.object(forms,'PdfWriter',MissingChecklistWriter):
            with self.assertRaisesRegex(ValueError,'page count differs'):
                forms.paper_packet_pdf(example())

    def test_empty_support_plan_is_valid_and_does_not_claim_filing_readiness(self):
        record=example();packet=official_forms.build_official_packet(record)
        self.assertEqual(packet['packet_manifest']['expected_pdf_pages'],0)
        status=forms.packet_status(record,packet)
        self.assertEqual(status['supporting_packet_preflight']['actual_pages'],0)
        self.assertFalse(status['filing_packet_ready']);self.assertFalse(status['transmitted'])

    def test_manifest_cannot_claim_filing_readiness_or_an_invented_count(self):
        for changes in ({'filing_packet_ready':True},{'expected_pdf_pages':True},{'tax_year':2024}):
            manifest={**official_forms.packet_manifest([]),**changes}
            self.assertRaises(ValueError,official_forms.verify_packet_pages,b'',manifest)


if __name__=='__main__':unittest.main()
