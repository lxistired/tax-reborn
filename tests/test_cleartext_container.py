"""Complete App container source edits, preservation and refusal boundaries."""
import base64
import copy
from io import BytesIO
from pathlib import Path
import struct
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'web'))
sys.path.insert(0, str(ROOT / 'scripts'))
import taxml_preparation as prep
import taxml_container as container
from interop.container.raw_zip_reference import load_archive
from create_clear_container_fixture import make_source, request


def correct(req, candidate, **amounts):
    return prep.export_request({'inspection': req,
        'expected_candidate_sha256': candidate['receipt']['candidate_sha256'],
        'amounts': {**candidate['amounts'], **amounts} if candidate['record_type'] != 'w2' else
                   {key: amounts.get(key, candidate['amounts'][key]) for key in prep.BOX_KEYS.values()},
        'confirmed': True})


class CleartextContainerTests(unittest.TestCase):
    def test_selected_taxml_and_extra_documents_are_separate(self):
        req = request(); original = copy.deepcopy(req)
        result = prep.inspect_request(req)
        self.assertEqual(req, original)
        self.assertFalse(result['unresolved_facts'])
        self.assertEqual([c['record_type'] for c in result['candidates']], ['w2', 'interest', 'dividends'])
        self.assertTrue(all(c['can_review'] for c in result['candidates']))
        self.assertTrue(all(c['source_format'] == container.FORMAT for c in result['candidates']))
        report = result['container_report']
        self.assertEqual((report['members'], len(report['documents']), report['unreferenced_members']), (5, 3, 1))
        self.assertFalse(report['native_default_encrypted_file_supported'])
        self.assertFalse(report['other_document_semantics_validated'])
        self.assertEqual([d['stored_only'] for d in report['documents']], [False, True, True])
        self.assertFalse(result['full_return_imported'])

    def test_each_income_type_exports_complete_archive_with_other_raw_records_unchanged(self):
        req = request(); source = base64.b64decode(req['base64'])
        old = load_archive(source); before = prep.inspect_request(req)
        for selected in before['candidates']:
            key = 'wages' if selected['record_type'] == 'w2' else 'interest_income' if selected['record_type'] == 'interest' else 'ordinary'
            result = correct(req, selected, **{key: '9000.01'})
            self.assertEqual(result['export_container'], container.FORMAT)
            self.assertEqual(result['mime'], 'application/zip')
            output = base64.b64decode(result['base64']); new = load_archive(output)
            self.assertTrue(output.startswith(b'PK\x03\x04'))
            self.assertNotEqual(output, source)
            self.assertEqual(tuple(m.name for m in new.members), tuple(m.name for m in old.members))
            for a, b in zip(old.members, new.members):
                if a.name != b'return.xml': self.assertEqual(a.local, b.local)
            self.assertEqual(new.eocd[20:], old.eocd[20:])
            inspected = prep.inspect_request({**req, 'base64': result['base64']})
            for a, b in zip(before['candidates'], inspected['candidates']):
                if a['record_type'] == selected['record_type']: self.assertEqual(b['amounts'][key], '9000.01')
                else: self.assertEqual(a['amounts'], b['amounts'])
            self.assertTrue(result['container_report']['unselected_local_records_byte_identical'])
            self.assertFalse(result['full_return_recalculated'])
            self.assertEqual(base64.b64decode(req['base64']), source)

    def test_complete_archive_tampering_and_ambiguous_taxml_are_refused(self):
        source = make_source(method=zipfile.ZIP_STORED)
        marker = b'Unreferenced owned bytes'
        bad = bytearray(source); bad[source.index(marker)] ^= 1
        for data in [bytes(bad), source + b'extra', b'PK\x03\x04not-an-archive']:
            with self.assertRaises(ValueError): prep.inspect_request(request(data))
        archive = load_archive(source)
        changed = BytesIO()
        with zipfile.ZipFile(changed, 'w') as out:
            for member in archive.members:
                payload = member.payload
                if member.name == b'manifest.xml':
                    payload = payload.replace(b'</documents>', b'<document><entityKey>second.xml</entityKey><entityType>/tax/income/individual/taxreturn/taxml</entityType></document></documents>')
                out.writestr(member.name.decode(), payload)
            out.writestr('second.xml', next(m.payload for m in archive.members if m.name == b'return.xml'))
        with self.assertRaises(ValueError): prep.inspect_request(request(changed.getvalue()))

    def test_selected_unknown_extra_and_unknown_extra_relocation_are_refused(self):
        opaque = struct.pack('<HH', 0xCAFE, 3) + b'abc'
        for source in [make_source(method=zipfile.ZIP_STORED, selected_extra=opaque),
                       make_source(method=zipfile.ZIP_STORED, other_extra=opaque)]:
            req = request(source); inspected = prep.inspect_request(req)
            with self.assertRaises(ValueError): correct(req, inspected['candidates'][0], wages='9999999.99')

    def test_legacy_zip_extraction_contract_and_plain_xml_are_unchanged(self):
        from test_taxml_mixed import request as old_request
        req = old_request(); candidate = prep.inspect_request(req)['candidates'][0]
        output = correct(req, candidate, wages='9000.01')
        self.assertEqual(output['export_container'], 'plaintext_xml')
        self.assertEqual(output['mime'], 'application/xml')
        self.assertNotIn('source_format', candidate)

    def test_unmodeled_manifest_metadata_never_grants_review_or_payload_edit(self):
        source = make_source()
        with zipfile.ZipFile(BytesIO(source)) as archive:
            payloads = {info.filename: archive.read(info) for info in archive.infolist()}
        manifest = payloads['manifest.xml']
        variants = [
            manifest.replace(b'<Manifest xmlns=', b'<Manifest ownedHash="stale" xmlns='),
            manifest.replace(b'<document>', b'<document ownedHash="stale">', 1),
            manifest.replace(b'<entityKey>', b'<entityKey owned="unknown">', 1),
            manifest.replace(b'</document>', b'<attributes><attribute><name>owned-payload-sha256</name><value>stale</value></attribute></attributes></document>', 1),
            manifest.replace(b'</document>', b'<entityVer>1</entityVer></document>', 1),
            manifest.replace(b'</document>', b'<cfpEntityKey>unbound</cfpEntityKey></document>', 1),
            manifest.replace(b'</Manifest>', b'<relationships/></Manifest>'),
            manifest.replace(b'<documents>', b'<documents owned="unknown">'),
        ]
        for value in variants:
            buf = BytesIO()
            with zipfile.ZipFile(buf, 'w') as output:
                for name, data in payloads.items(): output.writestr(name, value if name == 'manifest.xml' else data)
            req = request(buf.getvalue()); inspected = prep.inspect_request(req)
            self.assertEqual(len(inspected['candidates']), 3)
            self.assertTrue(inspected['unresolved_facts'])
            self.assertFalse(inspected['container_report']['manifest_metadata_edit_authorized'])
            self.assertTrue(all(not c['can_review'] and not c['can_edit_source'] for c in inspected['candidates']))
            with self.assertRaises(ValueError): correct(req, inspected['candidates'][0], wages='9000.01')
            with self.assertRaises(ValueError): container.corrected_container(buf.getvalue(), 'return.xml', payloads['return.xml'])

    def test_manifest_comments_whitespace_and_processing_instructions_survive(self):
        source = make_source()
        with zipfile.ZipFile(BytesIO(source)) as archive:
            payloads = {info.filename: archive.read(info) for info in archive.infolist()}
        value = payloads['manifest.xml'].replace(b'<documents>', b'<?owned unchanged?><documents>')
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as output:
            for name, data in payloads.items(): output.writestr(name, value if name == 'manifest.xml' else data)
        req = request(buf.getvalue()); inspected = prep.inspect_request(req)
        self.assertFalse(inspected['unresolved_facts'])
        result = correct(req, inspected['candidates'][0], wages='9000.01')
        with zipfile.ZipFile(BytesIO(base64.b64decode(result['base64']))) as archive:
            self.assertEqual(archive.read('manifest.xml'), value)


if __name__ == '__main__': unittest.main()
