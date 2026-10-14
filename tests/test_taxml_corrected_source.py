"""Actual owned XPRF bytes, reviewed native TaxML, and exact XML edit readback.

All returns here are synthetic. Original program acceptance is unverified.
"""
import base64
import copy
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'web'))
import taxml_preparation as preparation
import taxml_wire as wire
import test_taxml_import as legacy
from taxml_xml_edit import patch_text_nodes
from test_taxml_import import registry_bytes, request, plaintext_archive
from test_taxml_native import document, entity_xml, form_xml, field_xml, HEADERS


def app_document():
    return document(entity_xml(form_xml(copy='1', filecopy='1')))


def native_request(data=None, carrier=None):
    carrier = registry_bytes() if carrier is None else carrier
    out = request(app_document() if data is None else data, carrier)
    out['profile'] = {'format': 'tax-reborn-taxml-native-windows-profile-v1', 'tax_year': 2025,
        'entity_name': 'USIndividualTaxReturn', 'formset_name': 'OwnedSet',
        'formset_headers': dict(HEADERS), 'template': out['profile']['templates'][0]}
    return out


def export(req, **changes):
    candidate = preparation.inspect_request(req)['candidates'][0]
    return preparation.export_request({'inspection': req, 'expected_candidate_sha256': candidate['receipt']['candidate_sha256'],
        'amounts': {k: str(changes.get(k, candidate['amounts'][k])) for k in preparation.BOX_KEYS.values()}, 'confirmed': True})


class CurrentWindowsWorkflow(unittest.TestCase):
    def test_owned_registry_bytes_are_required_and_nonzero_copy_is_reviewable(self):
        result = preparation.inspect_request(native_request())
        candidate = result['candidates'][0]
        self.assertTrue(candidate['can_review'])
        self.assertEqual(candidate['source_owner']['copyNum'], '1')
        self.assertEqual(candidate['amounts']['wages'], '1234.56')
        self.assertEqual(candidate['requires_manual_fields'], ['owner', 'social_security_tips', 'dependent_care_benefits'])
        self.assertIsNone(candidate['employer'])
        self.assertFalse(result['full_return_imported'])
        self.assertFalse(result['original_program_acceptance_verified'])

    def test_a_metadata_json_hash_is_not_a_registry(self):
        req = native_request(); data = b'[["WAGES",11,0]]'; identity = wire.digest(data)
        req['carriers'] = [{'base64': base64.b64encode(data).decode(), 'sha256': identity}]
        req['profile']['template']['carrier_sha256'] = identity
        with self.assertRaises(ValueError): preparation.inspect_request(req)

    def test_hash_and_selected_template_must_match_actual_xprf(self):
        for mutation in ('hash', 'template', 'resource', 'formset'):
            req = native_request()
            if mutation == 'hash': req['carriers'][0]['base64'] = base64.b64encode(registry_bytes() + b'x').decode()
            elif mutation == 'template': req['profile']['template']['carrier_sha256'] = '0' * 64
            elif mutation == 'resource': req['profile']['template']['resource_id'] = 42
            else: req['profile']['template']['formset_id'] = 'OwnedSet'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): preparation.inspect_request(req)

    def test_copy_zero_requires_actual_multicopy_factory_binding(self):
        req = request(); req['base64'] = base64.b64encode(base64.b64decode(req['base64']).replace(b'copyNum="1"', b'copyNum="0"')).decode()
        legacy = preparation.inspect_request(req)
        self.assertTrue(all(not c['can_review'] for c in legacy['candidates']))
        self.assertTrue(legacy['unresolved_facts'])
        modern = preparation.inspect_request(native_request(document()))
        self.assertFalse(modern['candidates'][0]['can_review'])
        self.assertTrue(any(x['code'] == 'unverified_multicopy_factory_binding' for x in modern['unresolved_facts']))
        with self.assertRaises(ValueError): export(native_request(document()), wages='2000')

    def test_wrong_field_kind_is_not_silently_treated_as_money(self):
        req = native_request(carrier=registry_bytes(field_kinds={'WAGES': 7}))
        value = preparation.inspect_request(req)
        self.assertFalse(value['candidates'][0]['can_review'])
        self.assertIn(1, value['candidates'][0]['missing_boxes'])

    def test_formset_headers_name_year_and_version_are_bound(self):
        for before, after in [(b'OWNED', b'OTHER'), (b'OwnedSet', b'OtherSet'), (b'taxYear="2025"', b'taxYear="2024"'), (b'9.15.0', b'9.15.1')]:
            value = preparation.inspect_request(native_request(app_document().replace(before, after)))
            self.assertTrue(value['unresolved_facts'])
            self.assertTrue(all(not c['can_review'] for c in value['candidates']))

    def test_unknown_sibling_duplicate_copy_and_true_flags_block_all(self):
        for data in [document(entity_xml(form_xml(copy='1', filecopy='1') + form_xml(copy='1', filecopy='1'))),
                app_document().replace(b'</FW2>', b'<UNKNOWN><x/></UNKNOWN></FW2>'),
                app_document().replace(b'<td:value >', b'<td:value computed="true">', 1),
                app_document().replace(b'</OwnedSet>', b'<OTHER tpsType="form"/></OwnedSet>')]:
            with self.subTest(data=data):
                result = preparation.inspect_request(native_request(data))
                self.assertTrue(result['unresolved_facts'])
                self.assertTrue(all(not c['can_review'] for c in result['candidates']))

    def test_unused_explicit_zero_is_blocked_but_used_zero_is_preserved(self):
        for used, expected in [('true', True), ('false', False)]:
            data = document(entity_xml(form_xml(copy='1', filecopy='1'))).replace(b'<td:value >1234.56', f'<td:value used="{used}">0'.encode(), 1)
            result = preparation.inspect_request(native_request(data))
            self.assertEqual(result['candidates'][0]['can_review'], expected)
            if expected:
                revised = base64.b64decode(export(native_request(data), wages='1234.57')['base64'])
                self.assertIn(b'<td:value used="true">1234.57</td:value>', revised)

    def test_six_corrected_values_reparse_and_original_is_retained(self):
        req = native_request(); before = copy.deepcopy(req)
        result = export(req, wages='1234.57', federal_withholding='0124.0')
        self.assertEqual(req, before)
        corrected = base64.b64decode(result['base64'])
        self.assertEqual(result['output_sha256'], wire.digest(corrected))
        req['base64'] = result['base64']
        candidate = preparation.inspect_request(req)['candidates'][0]
        self.assertEqual(candidate['amounts']['wages'], '1234.57')
        self.assertEqual(candidate['amounts']['federal_withholding'], '124.00')
        self.assertFalse(result['full_return_recalculated'])
        self.assertFalse(result['original_program_acceptance_verified'])

    def test_multiple_distinct_copies_edit_only_selected_owner(self):
        req = native_request(document(entity_xml(form_xml(copy='1', filecopy='1') + form_xml(copy='2', filecopy='2'))))
        result = preparation.inspect_request(req)
        self.assertEqual(len(result['candidates']), 2)
        corrected = base64.b64decode(export(req, wages='2000')['base64'])
        req['base64'] = base64.b64encode(corrected).decode()
        candidates = preparation.inspect_request(req)['candidates']
        self.assertEqual([c['amounts']['wages'] for c in candidates], ['2000.00', '1234.56'])

    def test_legacy_xml_export_does_not_change_namespace_comments_or_source_context(self):
        req = request(); data = base64.b64decode(req['base64'])
        data = b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>\n<!--outside--><?owned key?>' + data.replace(b'<SyntheticReturn ', b'<SyntheticReturn xmlns:opaque="urn:owned" ')
        req['base64'] = base64.b64encode(data).decode()
        result = export(req, wages='98231.18')
        corrected = base64.b64decode(result['base64'])
        self.assertEqual(corrected, data.replace(b'98231.17</td:value></WAGES>', b'98231.18</td:value></WAGES>'))

    def test_plaintext_archive_exports_xml_and_keeps_original_archive(self):
        req = native_request(plaintext_archive(app_document())); req['container'] = 'declared_plaintext_zip'
        before = req['base64']; result = export(req, wages='2000')
        self.assertEqual(req['base64'], before)
        self.assertEqual(result['export_container'], 'plaintext_xml')
        self.assertIn(b'<TaxReturns ', base64.b64decode(result['base64']))

    def test_invalid_and_stale_edits_are_refused(self):
        req = native_request(); candidate = preparation.inspect_request(req)['candidates'][0]
        base = {'inspection': req, 'expected_candidate_sha256': candidate['receipt']['candidate_sha256'], 'amounts': dict(candidate['amounts']), 'confirmed': True}
        for mutation in ('unconfirmed', 'stale', 'negative', 'precision', 'overflow', 'missing', 'extra', 'number'):
            value = copy.deepcopy(base)
            if mutation == 'unconfirmed': value['confirmed'] = False
            elif mutation == 'stale': value['expected_candidate_sha256'] = '0' * 64
            elif mutation == 'missing': del value['amounts']['wages']
            elif mutation == 'extra': value['amounts']['employer'] = 'Other'
            else: value['amounts']['wages'] = {'negative': '-1', 'precision': '1.001', 'overflow': '1000000001', 'number': 1}[mutation]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): preparation.export_request(value)


class ExactLeafEdit(unittest.TestCase):
    def test_utf8_offsets_quoted_greater_than_comments_and_pi_are_preserved(self):
        data = b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?><root xmlns:v="urn:value" note="a>b">' + '中文'.encode() + b'<!--keep--><?owned yes?><v:value used="true"><![CDATA[A&B]]></v:value><other opaque="v:Type"/></root><!--after-->'
        changed = patch_text_nodes(data, {'2': {'qname': '{urn:value}value', 'text': 'A&B', 'replacement': 'C<&>\rD'}})
        self.assertEqual(changed, data.replace(b'<![CDATA[A&B]]>', b'C&lt;&amp;&gt;&#13;D'))

    def test_ambiguous_missing_nonleaf_selfclosing_and_wrong_expected_value_refuse(self):
        for data, path, name, text in [(b'<r><v/></r>', '0', 'v', ''), (b'<r><v>A<x/>B</v></r>', '0', 'v', 'A'),
                (b'<r><v>A<!--comment--></v></r>', '0', 'v', 'A'), (b'<r><v>A</v></r>', '1', 'v', 'A'),
                (b'<r><v>A</v></r>', '0', 'wrong', 'A'), (b'<r><v>A</v></r>', '0', 'v', 'B')]:
            with self.subTest(data=data, path=path), self.assertRaises(ValueError):
                patch_text_nodes(data, {path: {'qname': name, 'text': text, 'replacement': 'C'}})

    def test_invalid_characters_and_dtd_are_refused(self):
        for text in ['\x00', '\x01', '\ud800']:
            with self.subTest(text=repr(text)), self.assertRaises(ValueError):
                patch_text_nodes(b'<r><v>A</v></r>', {'0': {'qname': 'v', 'text': 'A', 'replacement': text}})
        with self.assertRaises(ValueError):
            patch_text_nodes(b'<!DOCTYPE r><r><v>A</v></r>', {'0': {'qname': 'v', 'text': 'A', 'replacement': 'B'}})


class NativeReceiptPersistence(legacy.ReceiptPersistenceAcceptance):
    """Repeat durable HTTP/SQLite review and tamper checks for three-level paths."""
    def prepared(self):
        payload = super().prepared()
        req = native_request(document(entity_xml(form_xml(copy='1', filecopy='1'))).replace(b'>1234.56</td:value>', b'>98231.17</td:value>', 1))
        candidate = preparation.inspect_request(req)['candidates'][0]
        payload['data']['w2'][0].update(candidate['amounts'])
        metadata = legacy.return_metadata.normalize(payload['data'], None, legacy.tax_engine.ROW_DEFAULTS['w2'])
        item = metadata['w2_records'][0]
        item.update(reviewed=True, reviewed_at=datetime.now(timezone.utc).isoformat(),
            reviewed_fingerprint=item['row_fingerprint'], source_document={
                **payload['metadata']['w2_records'][0]['source_document'], 'taxml_receipt': candidate['receipt']})
        payload['metadata'] = metadata
        return payload


if __name__ == '__main__': unittest.main()
