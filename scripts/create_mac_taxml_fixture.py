#!/usr/bin/env python3
"""Construct public-safe Mac-shaped TaxML, metadata and cleartext ZIP examples.

Every XPRF byte, metadata ID, CID, XML value and source owner is independently
authored here. No vendor resource, saved return, program or binary is read.
The ZIP envelope reuses this repository's owned Preview29 guard fixture.
"""
from pathlib import Path
import argparse
import base64
from decimal import Decimal
import hashlib
from io import BytesIO
import json
import struct
import sys
import zipfile
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'web'), str(ROOT / 'scripts')]
from create_clear_container_fixture import make_source as owned_container

DEST = ROOT / 'fixtures/mac-taxml'
BASE = 'http://www.intuit.com/Ctg/Pta/TurboTax/'
FORMSET = 'OWNEDMAC2025'
FS_ELEMENT = 'OwnedUSIndividual2025'
FS_PREFIX = 'ownedmac'
CID_FORMSET = 'OwnedCIDFormSet2025'
PROFILE = 'tax-reborn-taxml-native-mac-profile-v1'
HEADERS = {'checksum': 'owned-checksum-2025-v1', 'dataVersion': '2025.1',
    'sharedForAllDataVersion': 'owned-all-1', 'sharedForFSDataVersion': 'owned-fs-1',
    'formsetAttribute': '7', 'showSmartWorksheets': 'false', 'implementationVersion': 'owned-1'}
FIELDS = {
    'FW2': ('WAGES', 'FEDTAX', 'SSWAGES', 'SSTAX', 'MEDWAGES', 'MEDTAX', 'SSTIPS', 'DCB'),
    'F1099I': ('L1', 'L3', 'EXINT', 'L4'),
    'F1099D': ('L1B', 'QDIV', 'L1C', 'L2C', 'L1CTX', 'L2'),
}
# (fileCopyNum U32, copyNum U16, values). A stored file-copy identity is not
# a native CopyNumber, and equal copyNums in separate entities do not merge.
ENTITIES = (
    ('11111111-1111-4111-8111-111111111111', (
        ('FW2', 70000, 1, ('1234.56', '123.00', '1234.56', '76.54', '1234.56', '17.90', '0.00', '0.00')),
        ('FW2', 70001, 2, ('50000.01', '4000.02', '50000.01', '3100.01', '50000.01', '725.01', '5.01', '10.01')),
        ('F1099I', 71000, 1, ('100.23', '40.27', '12.34', '20.45')),
        ('F1099D', 72000, 1, ('1200.31', '300.15', '1000.25', '150.05', '100.05', '200.49')),
    )),
    ('22222222-2222-4222-8222-222222222222', (
        ('FW2', 80000, 1, ('80000.10', '8000.01', '80000.10', '4960.01', '80000.10', '1160.01', '0.00', '0.00')),
        ('F1099I', 81000, 1, ('250.10', '30.20', '0.00', '25.00')),
        ('F1099D', 82000, 1, ('100.00', '20.00', '30.00', '0.00', '0.00', '4.00')),
    )),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def string_list(values):
    data = [v.encode('ascii') if isinstance(v, str) else v for v in values]
    if any(len(v) >= 255 for v in data):
        raise ValueError('This independent fixture uses short attribute strings.')
    return struct.pack('<H', len(data)) + b''.join(bytes([len(v)]) + v for v in data)


def mapping_list(form, fields):
    records = []
    for ordinal, field in enumerate(fields, 1):
        values = ('Owned' + form, '', 'Owned_' + field, 'owned-reader-extra')
        strings = b''.join(bytes([len(s.encode('ascii'))]) + s.encode('ascii') for s in values)
        records.append(struct.pack('<HB', ordinal, 3) + strings)
    position = 2 + 2 * len(records)
    offsets = []
    for record in records:
        offsets.append(position)
        position += len(record)
    if position > 65535:
        raise ValueError('Owned mapping exceeds the selected U16 offset profile.')
    return struct.pack('<H', len(records)) + struct.pack('<' + 'H' * len(records), *offsets) + b''.join(records)


def resource_map():
    formset_strings = [FORMSET, '2025', 'owned', '', '', '', '', '5', 'owned']
    resources = {(18500, 1): string_list(formset_strings),
                 (1525, 1): string_list((FS_PREFIX, 'OwnedUSIndividual', '2025')),
                 (7000, 1): string_list(tuple('OwnedList' + str(i) for i in range(20)) + (CID_FORMSET,))}
    for rid, (form, fields) in enumerate(FIELDS.items(), 2):
        parts = [form, FORMSET, '1', '2025'] + [''] * 15
        parts[16] = '5'
        resources[18000, rid] = string_list(parts)
        resources[1900, rid] = struct.pack('<H', len(fields)) + b''.join(
            b'\xff' + field.encode('ascii').ljust(32, b' ') + struct.pack('<BBI', 11, 0, 0)
            for field in fields)
        resources[1901, rid] = struct.pack('<H', 0)
        resources[2310, rid] = mapping_list(form, fields)
    return resources


def make_carrier():
    resources = resource_map()
    count = len(resources)
    header = b'XPRF\0\1\x10\x0c\x0a\0\0\0' + struct.pack('<I', count)
    at = 16 + 12 * count
    directory, records = [], []
    for (kind, rid), payload in resources.items():
        record = struct.pack('<IIH', len(payload) + 10, len(payload), 0) + payload
        directory.append(struct.pack('<HHII', kind, rid, at, len(record)))
        records.append(record)
        at += len(record)
    return header + b''.join(directory) + b''.join(records)


def attributes(values):
    return ' '.join(key + '=' + quoteattr(str(value)) for key, value in values.items())


def make_xml(*, missing=None, unused=None, duplicate=None):
    """Variants address (entity index, form-copy index, field ID)."""
    output = ['<?xml version="1.0" encoding="UTF-8"?>\n',
        '<TaxReturns xmlns="' + BASE + 'TaxReturns" xmlns:td="' + BASE + 'TaxDataType">\n',
        ' <!-- INDEPENDENT SAMPLE: no original saved return or native execution. -->\n']
    for ei, (entity_uuid, copies) in enumerate(ENTITIES):
        output.append(' <USIndividualTaxReturn xmlns="' + BASE + 'USIndividualTaxReturn" ' +
            attributes({'taxYear': '2025', 'uuid': entity_uuid, 'tpsEngineVersion': '9.15.0'}) + '>\n')
        fs_uuid = '00000000-0000-4000-8000-' + format(ei + 1, '012x')
        output.append('  <' + FS_ELEMENT + ' xmlns="' + BASE + FS_ELEMENT + '" ' + attributes({
            **HEADERS, 'uuid': fs_uuid, 'tpsType': 'formset', 'tpsPrefix': FS_PREFIX, 'cidFormSet': CID_FORMSET}) + '>\n')
        for ci, (form, file_copy, copy_number, values) in enumerate(copies):
            output.append('   <' + form + ' ' + attributes({'tpsType': 'form', 'copyNum': copy_number,
                'fileCopyNum': file_copy, 'porIndex': ci + 1, 'formCopyAttributes': 3,
                'uuid': '00000000-0000-4000-8000-' + format(file_copy, '012x')}) + '>\n')
            for field, value in zip(FIELDS[form], values):
                key = (ei, ci, field)
                if key == missing:
                    continue
                Decimal(value)  # Authored exact decimal source text.
                token = '    <' + field + ' ' + attributes({'tpsType': 'cent', 'tpsSubType': 'default',
                    'cidForm': 'Owned' + form, 'cidField': 'Owned_' + field}) + '><td:value' + (
                    ' used="false"' if key == unused else '') + '>' + value + '</td:value></' + field + '>\n'
                output.append(token)
                if key == duplicate:
                    output.append(token)
            output.append('   </' + form + '>\n')
        output.append('  </' + FS_ELEMENT + '>\n </USIndividualTaxReturn>\n')
    output.append('</TaxReturns>\n')
    return ''.join(output).encode('utf-8')


def make_source(xml=None, *, blocked=False):
    """Use only the existing owned five-member cleartext guard envelope."""
    source = owned_container()
    output = BytesIO()
    with zipfile.ZipFile(BytesIO(source)) as old, zipfile.ZipFile(output, 'w') as new:
        new.comment = old.comment
        for info in old.infolist():
            payload = old.read(info)
            if info.filename == 'return.xml':
                payload = make_xml() if xml is None else xml
            elif info.filename == 'manifest.xml' and blocked:
                payload = payload.replace(b'</document>', b'<attributes><attribute><name>owned-unmodeled-hash</name><value>stale</value></attribute></attributes></document>', 1)
            new.writestr(info, payload)
    return output.getvalue()


def request(source=None, *, plaintext=False, xml=None, blocked=False):
    carrier = make_carrier()
    payload = (make_xml() if xml is None else xml) if plaintext else (make_source(xml, blocked=blocked) if source is None else source)
    return {'base64': base64.b64encode(payload).decode(),
        'container': 'plaintext_xml' if plaintext else 'cleartext_persistence_container',
        'profile': {'format': PROFILE, 'tax_year': 2025, 'registry_order': [digest(carrier)],
                    'entity_name': 'USIndividualTaxReturn', 'formsets': [
                        {'formset_id': FORMSET, 'expected_headers': dict(HEADERS), 'forms': list(FIELDS)}]},
        'carriers': [{'base64': base64.b64encode(carrier).decode(), 'sha256': digest(carrier)}],
        'profile_acknowledged': True}


def build(destination=DEST):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    files = {'owned-mac-income.xprf': make_carrier(), 'owned-mac-income.xml': make_xml(),
             'owned-mac-income.zip': make_source(), 'owned-mac-blocked.zip': make_source(blocked=True)}
    for name, data in files.items():
        (destination / name).write_bytes(data)
    requests = {'request.json': request(), 'plaintext-request.json': request(plaintext=True),
                'blocked-request.json': request(blocked=True)}
    for name, value in requests.items():
        (destination / name).write_bytes((json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    manifest = {'format': 'tax-reborn-wholly-owned-mac-taxml-fixture-v1',
        'provenance': 'All resource, XML and owner values independently generated; existing owned ZIP guard envelope reused.',
        'vendor_bytes_included': False, 'original_saved_return': False, 'original_runtime_executions': 0,
        'entities': 2, 'form_copies': 7, 'carrier_resources': len(resource_map()),
        'fileCopyNum_U32_70000_is_not_copyNum_U16_1': True,
        'expected_headers': dict(HEADERS),
        'files': {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())}
                  for p in sorted(destination.iterdir()) if p.is_file() and p.name != 'manifest.json'}}
    (destination / 'manifest.json').write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, default=DEST)
    args = parser.parse_args()
    print(json.dumps(build(args.destination)))
