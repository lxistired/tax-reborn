"""Mixed income XML ownership, exact sibling preservation and global refusal.

All inputs are independently authored; no original saved return is claimed.
"""
import base64
import copy
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'web'))
import taxml_preparation as prep
import taxml_wire as wire

FIX = ROOT / 'fixtures/taxml'

def request(payload=None):
    profile = json.loads((FIX / 'synthetic-mixed-income-profile.json').read_text())
    carriers = [(FIX / name).read_bytes() for name in ['synthetic-modern-windows-w2.xprf', 'synthetic-native-interest.xprf', 'synthetic-native-dividend.xprf']]
    return dict(base64=base64.b64encode(payload or (FIX / 'synthetic-mixed-income.xml').read_bytes()).decode(), container='plaintext_xml', profile=profile,
                carriers=[dict(base64=base64.b64encode(b).decode(), sha256=wire.digest(b)) for b in carriers], profile_acknowledged=True)

class MixedIncomeTests(unittest.TestCase):
    def test_same_copy_number_on_different_forms_has_distinct_owners_and_paths(self):
        r = prep.inspect_request(request())
        self.assertFalse(r['unresolved_facts'])
        self.assertEqual([c['record_type'] for c in r['candidates']], ['w2', 'interest', 'dividends'])
        self.assertEqual([c['receipt']['form_path'] for c in r['candidates']], ['0/0/0', '0/0/1', '0/0/2'])
        self.assertTrue(all(c['can_review'] for c in r['candidates']))
        for c, t in zip(r['candidates'], request()['profile']['templates']):
            self.assertEqual(c['receipt']['template_carrier_sha256'], t['carrier_sha256'])
            self.assertEqual(c['receipt']['template_resource_id'], t['resource_id'])
            self.assertEqual(c['source_owner']['copyNum'], '1')
        self.assertEqual(len({c['receipt']['candidate_sha256'] for c in r['candidates']}), 3)
        self.assertFalse(r['full_return_imported'])

    def test_correcting_selected_form_preserves_both_other_form_bytes(self):
        req = request(); before = base64.b64decode(req['base64'])
        for c in prep.inspect_request(req)['candidates']:
            key = next(iter(c['amounts'])); values = {**c['amounts'], key: '2000.01'}
            if c['record_type'] == 'dividends': values['ordinary'] = '2000.01'
            out = prep.export_request(dict(inspection=req, expected_candidate_sha256=c['receipt']['candidate_sha256'], amounts=values, confirmed=True))
            after = base64.b64decode(out['base64'])
            r = prep.inspect_request({**req, 'base64': out['base64']})
            selected = next(x for x in r['candidates'] if x['record_type'] == c['record_type'])
            self.assertEqual(selected['amounts'][key], '2000.01')
            for other in prep.inspect_request(req)['candidates']:
                if other['record_type'] == c['record_type']: continue
                name = other['source_owner']['form_name'].encode()
                start = before.index(b'<' + name + b' '); end = before.index(b'</' + name + b'>') + len(name) + 3
                self.assertIn(before[start:end], after)
                reread = next(x for x in r['candidates'] if x['record_type'] == other['record_type'])
                self.assertEqual(reread['amounts'], other['amounts'])
            self.assertEqual(base64.b64decode(req['base64']), before)
            self.assertFalse(out['full_return_recalculated'])

    def test_unsupported_sibling_and_nondefault_flags_block_every_candidate(self):
        before = base64.b64decode(request()['base64'])
        for bad in [before.replace(b'</OwnedSet>', b'<OTHER tpsType="form"/></OwnedSet>'),
                    before.replace(b'<td:value >100.23', b'<td:value override="true">100.23'),
                    before.replace(b'<F1099I ', b'<F1099I xmlns="urn:wrong" ')]:
            r = prep.inspect_request(request(bad))
            self.assertTrue(r['unresolved_facts'])
            self.assertTrue(all(not c['can_review'] for c in r['candidates']))

    def test_duplicate_same_form_identity_remains_ambiguous(self):
        before = base64.b64decode(request()['base64']); start = before.index(b'<F1099I '); end = before.index(b'</F1099I>') + len(b'</F1099I>')
        r = prep.inspect_request(request(before.replace(b'</OwnedSet>', before[start:end] + b'</OwnedSet>')))
        self.assertTrue(any(f['code'] == 'duplicate_form_copy_identity' for f in r['unresolved_facts']))
        self.assertTrue(all(not c['can_review'] for c in r['candidates']))

    def test_profile_order_does_not_reassign_carriers_or_candidate_paths(self):
        req = request(); before = prep.inspect_request(req)['candidates']
        req['profile']['templates'].reverse(); req['carriers'].reverse()
        after = prep.inspect_request(req)['candidates']
        for a, b in zip(before, after):
            self.assertEqual(a['amounts'], b['amounts'])
            self.assertEqual(a['sources'], b['sources'])
            self.assertEqual(a['receipt']['candidate_sha256'], b['receipt']['candidate_sha256'])
            self.assertEqual(a['receipt']['template_carrier_sha256'], b['receipt']['template_carrier_sha256'])

    def test_ambiguous_missing_or_cross_formset_profiles_refuse(self):
        for change in ['duplicate', 'missing', 'wrong_carrier', 'cross_formset']:
            req = request()
            if change == 'duplicate': req['profile']['templates'].append(copy.deepcopy(req['profile']['templates'][0]))
            if change == 'missing': req['profile']['templates'].pop()
            if change == 'wrong_carrier': req['profile']['templates'][1]['carrier_sha256'] = req['profile']['templates'][0]['carrier_sha256']
            if change == 'cross_formset': req['profile']['templates'][1]['formset_id'] = 'OtherSet'
            with self.subTest(change=change), self.assertRaises(ValueError): prep.inspect_request(req)

    def test_plaintext_zip_keeps_selected_member_and_all_form_owners(self):
        req = request(); payload = base64.b64decode(req['base64']); buf = BytesIO()
        manifest = (f'<Manifest xmlns="{wire.MANIFEST_NS}"><documents><document>'
                    f'<entityKey>return.xml</entityKey><entityType>{wire.TAXML_TYPE}</entityType>'
                    '</document></documents></Manifest>').encode()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('manifest.xml', manifest)
            z.writestr('return.xml', payload)
        req.update(base64=base64.b64encode(buf.getvalue()).decode(), container='declared_plaintext_zip')
        r = prep.inspect_request(req)
        self.assertEqual(len(r['candidates']), 3)
        self.assertTrue(all(c['can_review'] and c['receipt']['archive_member'] == 'return.xml' for c in r['candidates']))

if __name__ == '__main__': unittest.main()
