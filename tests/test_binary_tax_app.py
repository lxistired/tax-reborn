"""App binary inspect/edit/export with entirely independent sample documents.

This suite exercises actual binary bytes and the public App request functions.
It does not assert acceptance by an original program or a complete tax return.
"""
import base64
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'web'), str(ROOT / 'scripts')]

import binary_tax
import create_binary_fixture as fixtures
import tax_engine
import taxml_preparation as prep
from interop.form_core.native_document_reference import load_document_bytes, walk_forms

FIX = ROOT / 'fixtures/binary-tax'


def request(name='income'):
    return json.loads((FIX / f'{name}-request.json').read_text(encoding='utf-8'))


def inspected(name='income'):
    req = request(name)
    return req, binary_tax.inspect_request(req)


def decoded(req):
    # An explicit test registry selects current table IDs independently of the
    # App allocator. Every input is reparsed without a store-side object.
    _, context, _, _ = fixtures.registry_inputs()
    context = replace(context, current_table_ids={
        (fixtures.FORMSET.encode(), n): n + 10 for n in range(1, 5)})
    return load_document_bytes(base64.b64decode(req['base64']), fixtures.buffers(),
                               template_context=context)


def candidate_by_path(result, path):
    return next(c for c in result['candidates']
                if c['source_owner']['binary_path'] == path)


def required_amounts(candidate):
    fields = (prep.BOX_KEYS.values() if candidate['record_type'] == 'w2' else
              (name for _, _, name in prep.INTEREST_FIELDS)
              if candidate['record_type'] == 'interest' else
              (name for _, _, name in prep.DIVIDEND_FIELDS))
    return {name: candidate['amounts'][name] for name in fields}


class BinaryTaxAppAcceptance(unittest.TestCase):
    def assert_retained_except(self, before, after, *, path, ordinal, raw):
        """Compare every decoded form/header/slot/node/link, one raw64 excepted."""
        self.assertEqual(before.entity_header, after.entity_header)
        self.assertEqual([fs.header for fs in before.formsets],
                         [fs.header for fs in after.formsets])
        left, right = dict(walk_forms(before)), dict(walk_forms(after))
        self.assertEqual(list(left), list(right))
        for key, old in left.items():
            new = right[key]
            self.assertEqual(old.header, new.header)
            self.assertEqual(old.table_id, new.table_id)
            self.assertEqual(old.string_table, new.string_table)
            self.assertEqual(old.tables, new.tables)
            self.assertEqual(old.links, new.links)
            self.assertEqual(len(old.children), len(new.children))
            self.assertEqual(old.hash_state.heads, new.hash_state.heads)
            self.assertEqual(old.hash_state.wide, new.hash_state.wide)
            self.assertEqual(len(old.hash_state.buffers), len(new.hash_state.buffers))
            for old_buffer, new_buffer in zip(old.hash_state.buffers, new.hash_state.buffers):
                self.assertEqual(old_buffer.capacity, new_buffer.capacity)
                expected = tuple(replace(node, raw=raw)
                    if key == path and node.field_index == ordinal and node.element_index == 0
                    else node for node in old_buffer.nodes)
                self.assertEqual(expected, new_buffer.nodes)
            # Actual serialized headers and link descriptions carry extra bits.
            self.assertEqual(old.metadata.get('source_header_wire'),
                             new.metadata.get('source_header_wire'))
            self.assertEqual([link.metadata.get('source_wire') for link in old.links],
                             [link.metadata.get('source_wire') for link in new.links])

    def test_requests_bind_actual_files_and_reproduce_without_vendor_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory)
            fixtures.build_fixtures(generated)
            for path in generated.iterdir():
                with self.subTest(name=path.name):
                    self.assertEqual(path.read_bytes(), (FIX / path.name).read_bytes())
        manifest = json.loads((FIX / 'manifest.json').read_text())
        self.assertFalse(manifest['vendor_resources_included'])
        self.assertFalse(manifest['original_saved_return'])
        for name, entry in manifest['entries'].items():
            req = request(name)
            binary = (FIX / entry['binary']).read_bytes()
            self.assertEqual(base64.b64decode(req['base64']), binary)
            self.assertEqual(fixtures.digest(binary), entry['binary_sha256'])
            self.assertEqual(fixtures.digest((FIX / entry['request']).read_bytes()),
                             entry['request_sha256'])

    def test_income_exact_money_and_explicit_review_requirements(self):
        req, result = inspected()
        self.assertEqual(prep.inspect_request(req), result)
        self.assertFalse(result['unresolved_facts'])
        self.assertEqual([c['record_type'] for c in result['candidates']],
                         ['w2', 'interest', 'dividends'])
        self.assertTrue(all(c['can_review'] for c in result['candidates']))
        self.assertEqual(result['candidates'][0]['amounts'], {
            'wages': '1234.56', 'federal_withholding': '123.00',
            'social_security_wages': '1234.56', 'social_security_withholding': '76.54',
            'medicare_wages': '1234.56', 'medicare_withholding': '17.90',
            'social_security_tips': '0.00', 'dependent_care_benefits': '0.00'})
        self.assertEqual(result['candidates'][1]['amounts'], {
            'interest_income': '100.23', 'treasury_interest': '40.27',
            'tax_exempt_interest': '12.34', 'federal_withholding': '20.45'})
        self.assertEqual(result['candidates'][2]['amounts'], {
            'ordinary': '1200.31', 'qualified': '300.15',
            'capital_gain_distributions': '1000.25', 'unrecaptured_1250_gain': '150.05',
            'collectibles_gain': '100.05', 'federal_withholding': '200.49'})
        self.assertEqual(result['candidates'][0]['requires_manual_fields'], ['owner'])
        self.assertIn('supported_interest_scope', result['candidates'][1]['requires_manual_fields'])
        self.assertIn('qualified_dividend_eligibility', result['candidates'][2]['requires_manual_fields'])
        self.assertFalse(result['tax_values_imported'])
        self.assertFalse(result['full_return_imported'])
        self.assertFalse(result['original_program_acceptance_verified'])

    def test_inspected_amounts_reach_actual_app_tax_calculation_refund_344(self):
        # Explicitly supply the facts that inspection asks the reviewer to add.
        # Browser/IndexedDB acceptance is exercised separately by the runtime UI.
        for name in ('income', 'nested'):
            _, result = inspected(name)
            data = tax_engine.default_return()
            data['interest'].append(dict(tax_engine.ROW_DEFAULTS['interest'],
                payer='Existing synthetic bank', taxable='30.00'))
            for candidate in result['candidates']:
                kind, values = candidate['record_type'], candidate['amounts']
                if kind == 'w2':
                    row = dict(tax_engine.ROW_DEFAULTS['w2'], **values,
                               employer='Synthetic employer', owner='taxpayer')
                elif kind == 'interest':
                    row = dict(tax_engine.ROW_DEFAULTS['interest'], payer='Synthetic payer',
                        taxable=str(Decimal(values['interest_income']) + Decimal(values['treasury_interest'])),
                        tax_exempt=values['tax_exempt_interest'],
                        federal_withholding=values['federal_withholding'])
                else:
                    row = dict(tax_engine.ROW_DEFAULTS['dividends'], **values,
                               payer='Synthetic payer', special_distribution_confirmed=True)
                data[kind].append(row)
            calculated = tax_engine.calculate_return(data)
            with self.subTest(name=name):
                self.assertEqual(calculated['lines']['1a'], 1235)
                self.assertEqual(calculated['lines']['2b'], 171)
                self.assertEqual(calculated['lines']['3b'], 1200)
                self.assertEqual(calculated['lines']['7a'], 1000)
                self.assertEqual(calculated['summary']['refund'], 344)
                self.assertFalse(calculated['can_prepare'])
                self.assertFalse(data['eligibility']['all_income_reported'])

    def test_nested_headers_child_and_both_link_directions_resolve(self):
        req, result = inspected('nested')
        forms = result['binary_archive']['forms']
        self.assertEqual([form['path'] for form in forms],
                         [[0, 0], [0, 0, 0], [0, 1], [0, 2]])
        self.assertEqual((forms[0]['tables'], forms[0]['children']), (1, 1))
        self.assertEqual(sum(len(form['links']) for form in forms), 4)
        self.assertTrue(all(link['resolved'] for form in forms for link in form['links']))
        doc = decoded(req)
        parent = doc.formsets[0].forms[0]
        self.assertEqual((parent.tables[0].identifier, parent.tables[0].word28,
                          parent.tables[0].word2a), (b'OWNED_ROWS', 5, 9))
        self.assertEqual(parent.children[0].header.parent.identifier, b'FW2')
        self.assertEqual(parent.children[0].header.parent_field_id, b'WAGES')
        self.assertEqual(parent.links[0].form_id, b'F1099D')  # forward target
        self.assertEqual(parent.children[0].links[0].form_id, b'FW2')  # backward target

    def test_edit_one_nested_amount_retains_every_other_parsed_fact(self):
        req, result = inspected('nested')
        child = candidate_by_path(result, [0, 0, 0])
        field = child['sources']['interest_income']
        before = decoded(req)
        source = base64.b64decode(req['base64'])
        output = binary_tax.edit_request(dict(inspection=req,
            expected_source_sha256=result['source_sha256'], confirmed=True,
            changes=[dict(path=field['binary_path'], ordinal=field['ordinal'],
                          element=0, value='7.89')]))
        corrected = {**req, 'base64': output['base64']}
        self.assert_retained_except(before, decoded(corrected), path=(0, 0, 0),
                                    ordinal=field['ordinal'], raw=789)
        reread = binary_tax.inspect_request(corrected)
        self.assertEqual(candidate_by_path(reread, [0, 0, 0])['amounts']['interest_income'], '7.89')
        self.assertEqual(candidate_by_path(reread, [0, 1])['amounts']['interest_income'], '100.23')
        self.assertEqual(base64.b64decode(req['base64']), source)
        self.assertEqual(output['changed_fields'], 1)
        self.assertTrue(output['binary_roundtrip_verified'])
        self.assertTrue(output['all_other_parsed_facts_preserved'])
        self.assertFalse(output['full_return_recalculated'])
        self.assertFalse(output['original_program_acceptance_verified'])

    def test_selected_income_export_reloads_and_preserves_siblings(self):
        req, initial = inspected()
        for candidate in initial['candidates']:
            amounts = required_amounts(candidate)
            key = next(iter(amounts))
            amounts[key] = format(Decimal(amounts[key]) + Decimal('0.01'), '.2f')
            with self.subTest(kind=candidate['record_type']):
                output = binary_tax.export_request(dict(inspection=req,
                    expected_candidate_sha256=candidate['receipt']['candidate_sha256'],
                    amounts=amounts, confirmed=True))
                corrected = {**req, 'base64': output['base64']}
                reread = binary_tax.inspect_request(corrected)
                path = candidate['source_owner']['binary_path']
                actual = candidate_by_path(reread, path)
                self.assertEqual(required_amounts(actual), amounts)
                self.assertEqual(fixtures.digest(base64.b64decode(output['base64'])), output['output_sha256'])
                self.assert_retained_except(decoded(req), decoded(corrected), path=tuple(path),
                    ordinal=candidate['sources'][key]['ordinal'],
                    raw=int(Decimal(amounts[key]) * 100))
                for sibling in initial['candidates']:
                    if sibling['source_owner']['binary_path'] != path:
                        self.assertEqual(candidate_by_path(reread, sibling['source_owner']['binary_path'])['amounts'],
                                         sibling['amounts'])

    def test_unused_nonzero_payload_is_distinct_from_present_zero(self):
        req, result = inspected('unused-zero')
        wages = result['candidates'][0]
        self.assertFalse(wages['can_review'])
        self.assertIn(1, wages['missing_boxes'])
        facts = {fact['field_id']: fact for fact in result['binary_archive']['forms'][0]['fields']}
        self.assertEqual((facts['WAGES']['status'], facts['WAGES']['text'], facts['WAGES']['raw64']),
                         ('unused', None, '123456'))
        self.assertEqual((facts['FEDTAX']['status'], facts['FEDTAX']['text']), ('value', '0.00'))
        self.assertFalse(facts['WAGES']['editable'])
        self.assertTrue(facts['FEDTAX']['editable'])
        with self.assertRaises(ValueError):
            binary_tax.edit_request(dict(inspection=req,
                expected_source_sha256=result['source_sha256'], confirmed=True,
                changes=[dict(path=[0, 0], ordinal=facts['WAGES']['ordinal'], element=0, value='0')]))

    def test_registry_hash_profile_version_and_acknowledgment_refuse_tampering(self):
        for mutation in ('hash', 'carrier', 'binding', 'version', 'acknowledgment'):
            req = request()
            if mutation == 'hash':
                req['carriers'][0]['sha256'] = '0' * 64
            elif mutation == 'carrier':
                raw = bytearray(base64.b64decode(req['carriers'][0]['base64']))
                raw[-1] ^= 1
                req['carriers'][0]['base64'] = base64.b64encode(raw).decode()
            elif mutation == 'binding':
                req['profile']['templates'][0]['resource_id'] += 1
            elif mutation == 'version':
                req['profile']['template_versions'][fixtures.FORMSET] += 1
            else:
                req['profile_acknowledged'] = False
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                binary_tax.inspect_request(req)

    def test_stale_hashes_and_unconfirmed_corrections_are_refused(self):
        req, result = inspected()
        candidate = result['candidates'][0]
        source = candidate['sources']['wages']
        edit = dict(inspection=req, expected_source_sha256=result['source_sha256'],
                    changes=[dict(path=[0, 0], ordinal=source['ordinal'], element=0, value='100')], confirmed=True)
        export = dict(inspection=req,
            expected_candidate_sha256=candidate['receipt']['candidate_sha256'],
            amounts=required_amounts(candidate), confirmed=True)
        for function, payload, hash_key in [(binary_tax.edit_request, edit, 'expected_source_sha256'),
                                            (binary_tax.export_request, export, 'expected_candidate_sha256')]:
            for key, value in [(hash_key, '0' * 64), ('confirmed', False)]:
                with self.subTest(function=function.__name__, key=key), self.assertRaises(ValueError):
                    function({**payload, key: value})

    def test_invalid_field_precision_duplicate_and_binary_structure_are_refused(self):
        req, result = inspected()
        source = result['candidates'][0]['sources']['wages']
        change = dict(path=[0, 0], ordinal=source['ordinal'], element=0, value='1.00')
        for changes in [[{**change, 'value': '1.001'}], [{**change, 'ordinal': 65535}],
                        [change, change], [{**change, 'element': 1}]]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                binary_tax.edit_request(dict(inspection=req,
                    expected_source_sha256=result['source_sha256'], changes=changes, confirmed=True))
        payload = base64.b64decode(req['base64'])
        for raw in [payload[:-1], b'\0' + payload[1:], payload + b'UNPARSED']:
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                binary_tax.inspect_request({**req, 'base64': base64.b64encode(raw).decode()})

    def test_profile_order_does_not_change_field_or_owner_binding(self):
        req, initial = inspected('nested')
        req['profile']['templates'].reverse()
        req['carriers'].reverse()
        reread = binary_tax.inspect_request(req)
        for before, after in zip(initial['candidates'], reread['candidates']):
            self.assertEqual(before['amounts'], after['amounts'])
            self.assertEqual(before['sources'], after['sources'])
            self.assertEqual(before['source_owner'], after['source_owner'])
            for key in ('source_sha256', 'candidate_sha256', 'form_path',
                        'template_carrier_sha256', 'template_resource_id'):
                self.assertEqual(before['receipt'][key], after['receipt'][key])
        # Reordering the explicit profile changes its own canonical hash only.
        self.assertNotEqual(initial['wire_profile_sha256'], reread['wire_profile_sha256'])
        self.assertEqual(reread['binary_archive'], initial['binary_archive'])


if __name__ == '__main__':
    unittest.main()
