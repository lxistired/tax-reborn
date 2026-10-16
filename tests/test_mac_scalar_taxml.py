"""Whole-source ordinary dec1 edits; synthetic resources and explicit modes only."""
import base64
import copy
import json
from pathlib import Path
import re
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from zip_semantics import (assert_request_json_semantics, assert_zip_semantics_equal,
                            assert_fixture_manifest_integrity, request_semantics)
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'web'), str(ROOT / 'scripts')]
import taxml_mac as mac
import taxml_preparation as prep
from create_mac_scalar_fixture import build, request, make_xml, digest, resource_map
from create_mac_taxml_fixture import request as old_request
from interop.container.raw_zip_reference import load_archive


def edit(req, index=0, text='0.8', **overrides):
    field = prep.inspect_request(req)['scalar_fields'][index]
    return prep.export_request({'inspection': req,
        'expected_scalar_sha256': field['receipt']['field_sha256'],
        'value': text, 'confirmed': True, **overrides})


def with_resources(req, resources):
    at = 16 + 12 * len(resources); directory, records = [], []
    for (kind, rid), payload in resources.items():
        record = struct.pack('<IIH', len(payload) + 10, len(payload), 0) + payload
        directory.append(struct.pack('<HHII', kind, rid, at, len(record)))
        records.append(record); at += len(record)
    blob = b'XPRF\0\1\x10\x0c\x0a\0\0\0' + struct.pack('<I', len(resources)) + b''.join(directory + records)
    req['carriers'] = [{'base64': base64.b64encode(blob).decode(), 'sha256': digest(blob)}]
    req['profile']['registry_order'] = [digest(blob)]
    return req


class MacScalarTests(unittest.TestCase):
    def test_builder_reproducible_complete_and_no_vendor_resources(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            one, two = build(a), build(b)
            self.assertEqual(one, two)
            self.assertFalse(one['vendor_bytes_included'])
            self.assertEqual((one['entities'], one['form_copies'], one['scalar_fields']), (2, 7, 3))
            fixture_dir = ROOT / 'fixtures/mac-scalar-taxml'
            assert_fixture_manifest_integrity(self, fixture_dir)
            for name in one['files']:
                self.assertEqual((Path(a) / name).read_bytes(), (Path(b) / name).read_bytes())
                if name.endswith('.zip'):
                    assert_zip_semantics_equal(self, (Path(a) / name).read_bytes(), (fixture_dir / name).read_bytes())
                elif name.endswith('.json') and name != 'manifest.json':
                    assert_request_json_semantics(self, Path(a) / name, fixture_dir / name)
                else:
                    self.assertEqual((Path(a) / name).read_bytes(), (fixture_dir / name).read_bytes())

    def test_explicit_controller_and_null_both_bind_full_source(self):
        for mode in ('controller_filter', 'null_filter'):
            with self.subTest(mode=mode):
                req = request(filter_profile=mode)
                result = prep.inspect_request(req)
                self.assertEqual(result['source_filter_profile'], mode)
                self.assertEqual(len(result['candidates']), 7)
                self.assertEqual([f['text'] for f in result['scalar_fields']], ['0.7', '1.2', '-0.3'])
                self.assertTrue(all(f['can_edit_source'] and not f['can_review'] for f in result['scalar_fields']))
                self.assertTrue(all(f['current_ordinal'] == 9 and f['kind'] == 13 for f in result['scalar_fields']))
                self.assertFalse(result['unresolved_facts'])
                self.assertFalse(result['tax_values_imported'])
                self.assertEqual([f['coefficient'] for f in result['scalar_fields']], ['7', '12', '-3'])
                self.assertEqual(len({f['receipt']['field_sha256'] for f in result['scalar_fields']}), 3)
                self.assertEqual(len(mac._context(req)[-1].fields), 47)

    def test_decimal_does_not_enter_money_or_income_candidates(self):
        old = prep.inspect_request(old_request())
        new = prep.inspect_request(request())
        self.assertEqual([c['amounts'] for c in old['candidates']], [c['amounts'] for c in new['candidates']])
        self.assertEqual([c['missing_boxes'] for c in old['candidates']], [c['missing_boxes'] for c in new['candidates']])
        self.assertTrue(all('DECIMAL' not in c['sources'] for c in new['candidates']))

    def test_money_box_name_with_kind13_stays_missing_not_money_or_default_zero(self):
        for rid, label, record_type, amount in ((2, 'WAGES', 'w2', 'wages'),
                (3, 'L1', 'interest', 'interest_income'), (4, 'L1B', 'dividends', 'ordinary')):
            resources = resource_map(); payload = bytearray(resources[1900, rid]); payload[35] = 13
            resources[1900, rid] = bytes(payload)
            pattern = rb'(<'+label.encode()+rb' [^>]*tpsType=")cent("[^>]*><td:value>)[^<]+(</td:value>)'
            xml = re.sub(pattern, rb'\1dec1\g<2>0.7\3', make_xml())
            result = prep.inspect_request(with_resources(request(xml=xml), resources))
            selected = [c for c in result['candidates'] if c['record_type'] == record_type]
            self.assertTrue(all(not c['can_review'] and amount not in c['amounts'] for c in selected))
            self.assertTrue(any(f['field_id'] == label and f['kind'] == 13 for f in result['scalar_fields']))

    def test_nonordinary_compiled_attributes_and_format_block_entire_source(self):
        for offset, values in ((36, (1, 2, 255)), (37, (1, 0x40, 0x80))):
            for value in values:
                resources = resource_map(); payload = bytearray(resources[1900, 2])
                # The ninth complete entry is the DECIMAL current metadata.
                payload[offset + 8 * 39] = value; resources[1900, 2] = bytes(payload)
                with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                    prep.inspect_request(with_resources(request(), resources))

    def test_complete_container_edit_one_field_all_others_exact(self):
        req = request(); preserved = copy.deepcopy(req)
        source = base64.b64decode(req['base64']); old = load_archive(source)
        doc = mac._context(req)[-1]; selected = doc.fields[8]
        self.assertEqual((selected.text, selected.current_ordinal), ('0.7', 9))
        output = edit(req); self.assertEqual(req, preserved)
        blob = base64.b64decode(output['base64']); new = load_archive(blob)
        self.assertGreater(len(blob), 0)
        self.assertEqual([m.name for m in new.members], [m.name for m in old.members])
        self.assertEqual([m.payload for m in new.members if m.name != b'return.xml'],
                         [m.payload for m in old.members if m.name != b'return.xml'])
        self.assertEqual(output['number_kind'], 'decimal_coefficient')
        self.assertFalse(output['tax_values_imported']); self.assertFalse(output['full_return_recalculated'])
        expected = doc.source_bytes[:selected.text_start] + b'0.8' + doc.source_bytes[selected.text_end:]
        self.assertEqual(next(m.payload for m in new.members if m.name == b'return.xml'), expected)
        self.assertEqual([m.name for m in old.members], [m.name for m in new.members])
        self.assertEqual(sum(a.local == b.local for a, b in zip(old.members, new.members)), 4)
        reopened = mac._context({**req, 'base64': output['base64']})[-1]
        for before, after in zip(doc.fields, reopened.fields):
            self.assertEqual((before.key, before.current_ordinal, before.kind, before.attributes, before.value_attributes),
                (after.key, after.current_ordinal, after.kind, after.attributes, after.value_attributes))
            self.assertEqual(after.text, '0.8' if before.key == selected.key else before.text)

    def test_second_entity_and_copy_have_distinct_receipts_and_edits(self):
        req = request()
        for index, text in ((1, '0.0'), (2, '-0.8')):
            with self.subTest(index=index):
                output = edit(req, index, text)
                actual = prep.inspect_request({**req, 'base64': output['base64']})['scalar_fields']
                expected = ['0.7', '1.2', '-0.3']; expected[index] = text
                self.assertEqual([f['text'] for f in actual], expected)

    def test_plaintext_and_long_value_relocation_preserve_every_other_xml_byte(self):
        for plain in (False, True):
            req = request(plaintext=plain); doc = mac._context(req)[-1]
            selected = next(f for f in doc.fields if f.kind == 13)
            output = edit(req, text='9999999999999.9')
            self.assertEqual(output['mime'], 'application/xml' if plain else 'application/zip')
            readback = mac._context({**req, 'base64': output['base64']})[-1]
            expected = doc.source_bytes[:selected.text_start] + b'9999999999999.9' + doc.source_bytes[selected.text_end:]
            self.assertEqual(readback.source_bytes, expected)

    def test_mode_is_required_exact_and_not_inferred_from_xml(self):
        for mode in (None, False, True, 0, 1, '', 'sanitizer_filter', 'NULL', 'controller_filter '):
            req = request(); req['profile']['filter_profile'] = mode
            with self.subTest(mode=mode), self.assertRaises(ValueError): prep.inspect_request(req)
        req = request(); del req['profile']['filter_profile']
        with self.assertRaises(ValueError): prep.inspect_request(req)
        for mode in ('null_filter', 'controller_filter'):
            other = 'null_filter' if mode == 'controller_filter' else 'controller_filter'
            req = request(filter_profile=mode); req['profile']['filter_profile'] = other
            with self.subTest(mixed=mode), self.assertRaises(ValueError): prep.inspect_request(req)

    def test_v1_does_not_silently_acquire_dec1_or_debug_attribute_support(self):
        req = request(filter_profile='null_filter'); req['profile']['format'] = mac.PROFILE
        del req['profile']['filter_profile']
        with self.assertRaisesRegex(ValueError, 'explicit Mac scalar v2'): prep.inspect_request(req)
        req = old_request(); req['profile']['filter_profile'] = 'null_filter'
        with self.assertRaises(ValueError): prep.inspect_request(req)

    def test_decimal_lexical_and_overflow_refusals_no_rounding(self):
        for value in (None, False, 0.8, '0.80', '1', '.8', '1e2', 'NaN', '+0.8', '-0.0', '00.8', '10000000000000.0', '0.8 '):
            with self.subTest(value=value), self.assertRaises(ValueError): edit(request(), text=value)

    def test_full_id_current_ordinal_type_and_nonselected_unknown_are_guards(self):
        xml = make_xml()
        for source in (
            xml.replace(b'<DECIMAL field="9"', b'<DECIMAL field="8"', 1),
            xml.replace(b'<DECIMAL field="9" elem="0"', b'<DECIMAL field="9" elem="1"', 1),
            xml.replace(b'<DECIMAL field="9"', b'<OTHER field="9"', 1).replace(b'</DECIMAL>', b'</OTHER>', 1),
            xml.replace(b'tpsType="dec1"', b'tpsType="money"', 1),
            xml.replace(b'tpsSubType="default" cidForm="OwnedFW2" cidField="Owned_DECIMAL"', b'tpsSubType="other" cidForm="OwnedFW2" cidField="Owned_DECIMAL"', 1),
            xml.replace(b'>-0.3</td:value>', b'>-0.3</td:value><Unknown/>', 1),
            xml.replace(b'cidField="Owned_DECIMAL"', b'cidField="Owned_WAGES"', 1),
        ):
            with self.subTest(sha=digest(source)), self.assertRaises(ValueError): prep.inspect_request(request(xml=source))

    def test_unused_is_readonly_and_other_flags_not_accepted(self):
        xml = make_xml().replace(b'<td:value>0.7', b'<td:value used="false">0.7', 1)
        req = request(xml=xml); result = prep.inspect_request(req)
        self.assertEqual(result['scalar_fields'][0]['coefficient'], '7')
        self.assertFalse(result['scalar_fields'][0]['can_edit_source'])
        with self.assertRaises(ValueError): edit(req)
        for attrs in (b'used="true"', b'computed="true"', b'override="true"', b'other="1"'):
            with self.subTest(attrs=attrs), self.assertRaises(ValueError):
                prep.inspect_request(request(xml=make_xml().replace(b'<td:value>0.7', b'<td:value '+attrs+b'>0.7', 1)))

    def test_unknown_manifest_preserves_inspection_but_blocks_each_decimal_export(self):
        req = request(blocked=True); original = copy.deepcopy(req)
        result = prep.inspect_request(req)
        self.assertFalse(result['container_report']['manifest_metadata_edit_authorized'])
        self.assertTrue(result['unresolved_facts'])
        self.assertTrue(all(not f['can_edit_source'] for f in result['scalar_fields']))
        for index in range(3):
            with self.assertRaises(ValueError): edit(req, index)
        self.assertEqual(req, original)

    def test_stale_receipt_confirmation_unknown_keys_and_profile_changes_refused(self):
        req = request(); field = prep.inspect_request(req)['scalar_fields'][0]
        command = {'inspection': req, 'expected_scalar_sha256': field['receipt']['field_sha256'], 'value': '0.8', 'confirmed': True}
        for delta in ({'confirmed': False}, {'confirmed': 1}, {'expected_scalar_sha256': '0'*64}, {'other': 'ignored'}):
            with self.subTest(delta=delta), self.assertRaises(ValueError): prep.export_request({**command, **delta})
        new = request(filter_profile='null_filter')
        with self.assertRaises(ValueError): prep.export_request({**command, 'inspection': new})


if __name__ == '__main__': unittest.main()
