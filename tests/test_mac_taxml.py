"""Owned Mac metadata, complete multi-owner XML and actual App ZIP API tests."""
import base64
import copy
from io import BytesIO
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'web'), str(ROOT / 'scripts')]
import taxml_preparation as prep
import taxml_mac as mac
import taxml_wire as wire
from interop.container.raw_zip_reference import load_archive
from interop.form_core import effective_registry_fields_reference as core
from interop.form_core import native_taxml_names_reference as names
from create_mac_taxml_fixture import (
    build, request, make_xml, make_source, make_carrier, resource_map,
    FORMSET, FIELDS, HEADERS, ENTITIES, CID_FORMSET, FS_ELEMENT, digest,
)


def edit(req, candidate, updates):
    wanted = (prep.INTEREST_FIELDS if candidate['record_type'] == 'interest' else
              prep.DIVIDEND_FIELDS if candidate['record_type'] == 'dividends' else
              tuple((box, '', name) for box, name in prep.BOX_KEYS.items()))
    values = {name: updates[name] if name in updates else candidate['amounts'][name] for _, _, name in wanted}
    return prep.export_request({'inspection': req,
        'expected_candidate_sha256': candidate['receipt']['candidate_sha256'],
        'amounts': values, 'confirmed': True})


def archive_payload(blob, member):
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        return archive.read(member)


class MacTaxMLTests(unittest.TestCase):
    def test_builder_is_independent_reproducible_and_checked_in_requests_match(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            one, two = build(a), build(b)
            self.assertEqual(one, two)
            self.assertFalse(one['vendor_bytes_included'])
            self.assertEqual((one['entities'], one['form_copies'], one['carrier_resources']), (2, 7, 15))
            for name in one['files']:
                self.assertEqual((Path(a) / name).read_bytes(), (Path(b) / name).read_bytes())
                self.assertEqual((Path(a) / name).read_bytes(), (ROOT / 'fixtures/mac-taxml' / name).read_bytes())
        stored = json.loads((ROOT / 'fixtures/mac-taxml/request.json').read_text())
        self.assertEqual(stored, request())
        self.assertEqual(stored['profile']['formsets'][0]['expected_headers'], HEADERS)

    def test_complete_real_xprf_directory_same_registry_names_and_CID(self):
        blob = make_carrier()
        resources = wire.read_xprf_resources(blob, digest(blob))
        self.assertEqual(resources, resource_map())
        count = struct.unpack_from('<I', blob, 12)[0]
        rows = [struct.unpack_from('<HHII', blob, 16 + 12 * i) for i in range(count)]
        self.assertEqual(len({(t, r) for t, r, _, _ in rows}), 15)
        self.assertTrue(all(o >= 16 + 12 * count and o + n <= len(blob) for _, _, o, n in rows))
        spans = sorted((o, o + n) for _, _, o, n in rows)
        self.assertTrue(all(a[1] == b[0] for a, b in zip(spans, spans[1:])))
        registry = core.register_records((core.Carrier(bytes.fromhex(digest(blob)), resources),))
        self.assertEqual(len(registry.formsets), 1)
        fs = registry.formsets[0]
        fsnames = names.formset_names(registry, fs)
        self.assertEqual((fs.identifier.rstrip(), fsnames.element_name, fsnames.cid_formset),
                         (FORMSET.encode(), FS_ELEMENT, CID_FORMSET))
        self.assertIs(fsnames.parts_source.owner, fs)
        for form in fs.forms:
            token = form.identifier.rstrip().decode()
            template, _ = core.field_template(registry, form)
            self.assertEqual([f.identifier.rstrip().decode() for f in template.fields], list(FIELDS[token]))
            for ordinal, field in enumerate(template.fields, 1):
                selected = names.field_names(registry, form, field.identifier)
                self.assertEqual((selected.current_ordinal, selected.kind, selected.compiled_format), (ordinal, 11, 0))
                self.assertEqual((selected.cid_form, selected.cid_table, selected.cid_field),
                    ('Owned' + token, '', 'Owned_' + selected.element_name))
                self.assertTrue(selected.mapping_found)
                self.assertIs(selected.mapping_source.owner, form)

    def test_actual_App_complete_inspect_entities_copies_boxes_and_plaintext(self):
        req = request(); before = copy.deepcopy(req)
        result = prep.inspect_request(req)
        self.assertEqual(req, before)
        self.assertFalse(result['unresolved_facts'])
        self.assertEqual([c['record_type'] for c in result['candidates']],
                         ['w2', 'w2', 'interest', 'dividends', 'w2', 'interest', 'dividends'])
        self.assertTrue(all(c['can_review'] and not c['missing_boxes'] for c in result['candidates']))
        first, second = result['candidates'][:2]
        self.assertEqual((first['source_owner']['fileCopyNum'], first['source_owner']['copyNum']), ('70000', '1'))
        self.assertEqual(second['source_owner']['copyNum'], '2')
        self.assertEqual(first['amounts']['social_security_wages'], '1234.56')
        self.assertEqual(first['sources']['social_security_wages']['field_id'], 'SSWAGES')
        self.assertEqual(first['sources']['social_security_withholding']['field_id'], 'SSTAX')
        self.assertEqual(first['requires_manual_fields'], ['owner', 'employer'])
        self.assertEqual(result['candidates'][4]['source_owner']['copyNum'], '1')
        self.assertNotEqual(first['source_owner']['entity_uuid'], result['candidates'][4]['source_owner']['entity_uuid'])
        self.assertEqual(len({c['receipt']['form_path'] for c in result['candidates']}), 7)
        self.assertEqual((result['container_report']['members'], result['container_report']['unreferenced_members']), (5, 1))
        plain = prep.inspect_request(request(plaintext=True))
        self.assertEqual([c['amounts'] for c in result['candidates']], [c['amounts'] for c in plain['candidates']])
        self.assertFalse(result['full_return_imported'])
        self.assertFalse(result['original_program_acceptance_verified'])

    def check_complete_edit(self, candidate_index, updates):
        req = request(); original_request = copy.deepcopy(req)
        source = base64.b64decode(req['base64']); old = load_archive(source)
        inspected = prep.inspect_request(req); selected = inspected['candidates'][candidate_index]
        old_document = mac._context(req)[-1]
        exported = edit(req, selected, updates)
        self.assertEqual(req, original_request)
        self.assertEqual(exported['export_container'], 'cleartext_persistence_container')
        self.assertEqual(exported['mime'], 'application/zip')
        self.assertEqual(exported['source_sha256'], digest(source))
        self.assertFalse(exported['full_return_recalculated'])
        output = base64.b64decode(exported['base64']); new = load_archive(output)
        self.assertEqual(len(new.members), 5)
        self.assertEqual([m.name for m in new.members], [m.name for m in old.members])
        for a, b in zip(old.members, new.members):
            if a.name != b'return.xml':
                self.assertEqual(a.local, b.local)
                self.assertEqual(a.payload, b.payload)
        self.assertEqual(old.eocd[20:], new.eocd[20:])
        self.assertTrue(exported['container_report']['unselected_local_records_byte_identical'])
        reopened_request = {**req, 'base64': exported['base64']}
        readback = prep.inspect_request(reopened_request)
        self.assertFalse(readback['unresolved_facts'])
        for a, b in zip(inspected['candidates'], readback['candidates']):
            self.assertEqual(a['source_owner'], b['source_owner'])
            self.assertEqual(a['receipt']['form_path'], b['receipt']['form_path'])
            expected = {**a['amounts'], **updates} if a is selected else a['amounts']
            self.assertEqual(b['amounts'], expected)
        wanted = {tuple([entry[0], bytes.fromhex(entry[1]), bytes.fromhex(entry[2]), entry[3], bytes.fromhex(entry[4])]): updates[name]
                  for name in updates for entry in [selected['sources'][name]['key']]}
        expected_xml = old_document.source_bytes
        for f in sorted((f for f in old_document.fields if f.key in wanted), key=lambda f: f.text_start, reverse=True):
            expected_xml = expected_xml[:f.text_start] + wanted[f.key].encode('ascii') + expected_xml[f.text_end:]
        self.assertEqual(archive_payload(output, 'return.xml'), expected_xml)
        after_document = mac._context(reopened_request)[-1]
        self.assertEqual([f.key for f in old_document.fields], [f.key for f in after_document.fields])
        for a, b in zip(old_document.fields, after_document.fields):
            self.assertEqual((a.attributes, a.value_attributes), (b.attributes, b.value_attributes))
            if a.key not in wanted: self.assertEqual(a.text, b.text)
        return readback

    def test_multi_field_W2_edit_whole_ZIP_and_all_other_owner_bytes(self):
        self.check_complete_edit(0, {'wages': '2345.67', 'federal_withholding': '101.02',
            'social_security_wages': '2345.67', 'social_security_withholding': '145.43',
            'medicare_wages': '2345.67', 'medicare_withholding': '34.01'})

    def test_multi_field_interest_and_dividend_edits_preserve_other_copies(self):
        self.check_complete_edit(2, {'interest_income': '9000.01', 'treasury_interest': '41.29',
            'tax_exempt_interest': '13.25', 'federal_withholding': '99.01'})
        self.check_complete_edit(3, {'ordinary': '2000.01', 'qualified': '1000.01',
            'capital_gain_distributions': '1000.01', 'unrecaptured_1250_gain': '100.01',
            'collectibles_gain': '50.01', 'federal_withholding': '99.01'})

    def test_second_entity_edit_does_not_change_same_copyNum_in_first_entity(self):
        self.check_complete_edit(4, {'wages': '80000.11', 'federal_withholding': '8000.03'})

    def test_unmodeled_manifest_is_readonly_and_complete_source_survives(self):
        req = request(blocked=True); original = copy.deepcopy(req)
        result = prep.inspect_request(req)
        self.assertEqual(len(result['candidates']), 7)
        self.assertTrue(result['unresolved_facts'])
        self.assertFalse(result['container_report']['manifest_metadata_edit_authorized'])
        self.assertTrue(all(not c['can_review'] and not c['can_edit_source'] for c in result['candidates']))
        with self.assertRaises(ValueError): edit(req, result['candidates'][0], {'wages': '12.34'})
        self.assertEqual(req, original)

    def test_missing_and_Used0_are_not_zero_and_cannot_edit(self):
        for variant in ('missing', 'unused'):
            req = request(xml=make_xml(**{variant: (0, 0, 'WAGES')}))
            inspected = prep.inspect_request(req); first = inspected['candidates'][0]
            self.assertIn(1, first['missing_boxes'])
            self.assertFalse(first['can_review'])
            self.assertNotIn('wages', first['amounts'])
            with self.assertRaises(ValueError): edit(req, first, {'wages': '12.34'})
        result = prep.inspect_request(request())
        zero = result['candidates'][5]
        self.assertEqual(zero['amounts']['tax_exempt_interest'], '0.00')
        self.assertTrue(zero['can_review'])

    def test_duplicate_field_copy_and_entity_refuse_without_normalization(self):
        variants = [make_xml(duplicate=(0, 0, 'WAGES')),
            make_xml().replace(b'fileCopyNum="70001"', b'fileCopyNum="70000"'),
            make_xml().replace(ENTITIES[1][0].encode(), ENTITIES[0][0].encode())]
        for data in variants:
            with self.subTest(sha=digest(data)), self.assertRaises(ValueError): prep.inspect_request(request(xml=data))

    def test_profile_headers_registry_CID_and_exact_hash_are_independent_guards(self):
        req = request()
        variants = []
        bad = copy.deepcopy(req); bad['profile']['formsets'][0]['expected_headers']['checksum'] = 'other'; variants.append(bad)
        bad = copy.deepcopy(req); del bad['profile']['formsets'][0]['expected_headers']['checksum']; variants.append(bad)
        bad = copy.deepcopy(req); bad['carriers'][0]['base64'] += 'AA=='; variants.append(bad)
        variants.append(request(xml=make_xml().replace(b'cidField="Owned_WAGES"', b'cidField="Other"', 1)))
        variants.append(request(xml=make_xml().replace(b'copyNum="1"', b'copyNum="0"', 1)))
        for bad in variants:
            with self.subTest(profile=bad['profile']), self.assertRaises(ValueError): prep.inspect_request(bad)

    def test_stale_candidate_and_unknown_correction_fields_refuse(self):
        req = request(); candidate = prep.inspect_request(req)['candidates'][0]
        values = {name: candidate['amounts'][name] for name in prep.BOX_KEYS.values()}
        for changes in ({'expected_candidate_sha256': '0' * 64}, {'amounts': {**values, 'dependent_care_benefits': '1.00'}}, {'confirmed': False}):
            command = {'inspection': req, 'expected_candidate_sha256': candidate['receipt']['candidate_sha256'],
                       'amounts': values, 'confirmed': True, **changes}
            with self.assertRaises(ValueError): prep.export_request(command)


if __name__ == '__main__': unittest.main()
