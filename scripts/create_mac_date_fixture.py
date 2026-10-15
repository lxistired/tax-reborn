#!/usr/bin/env python3
"""Reproducible complete date sources with no vendor bytes or personal data."""
from pathlib import Path
import argparse, base64, hashlib, json, re, struct, sys
from io import BytesIO
import zipfile
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'web'), str(ROOT / 'scripts')]
import create_mac_taxml_fixture as old

PROFILE = 'tax-reborn-taxml-native-mac-profile-v3'
FIELDS = (('DATE', 4, 'date', '01/02/2000'),
          ('DAY', 5, 'day', '02-29'), ('MONTH', 6, 'month', '2000-02'))
DEST = ROOT / 'fixtures/mac-date-taxml'
def digest(data): return hashlib.sha256(data).hexdigest()

def resource_map():
    resources = old.resource_map(); payload = resources[1900, 2]
    records = b''.join(b'\xff' + name.encode().ljust(32, b' ') + struct.pack('<BBI', kind, 0, 0)
                       for name, kind, _, _ in FIELDS)
    resources[1900, 2] = struct.pack('<H', 11) + payload[2:] + records
    resources[2310, 2] = old.mapping_list('FW2', old.FIELDS['FW2'] + tuple(f[0] for f in FIELDS))
    return resources

def make_carrier():
    resources = resource_map(); at = 16 + 12 * len(resources); directory, records = [], []
    for (kind, rid), payload in resources.items():
        record = struct.pack('<IIH', len(payload) + 10, len(payload), 0) + payload
        directory.append(struct.pack('<HHII', kind, rid, at, len(record)))
        records.append(record); at += len(record)
    return b'XPRF\0\1\x10\x0c\x0a\0\0\0' + struct.pack('<I', len(resources)) + b''.join(directory + records)

def make_xml(filter_profile='controller_filter'):
    if filter_profile not in ('null_filter', 'controller_filter'):
        raise ValueError('Explicit supported source filter required')
    xml = old.make_xml()
    nodes = ''.join('    <'+name+' tpsType="'+label+'" tpsSubType="default" cidForm="OwnedFW2" cidField="Owned_'+name+'"><td:value>'+value+'</td:value></'+name+'>\n'
                    for name, _, label, value in FIELDS).encode()
    xml = xml.replace(b'   </FW2>', nodes + b'   </FW2>')
    if filter_profile == 'controller_filter':
        for form, fields in old.FIELDS.items():
            selected = fields + tuple(f[0] for f in FIELDS) if form == 'FW2' else fields
            for ordinal, field in enumerate(selected, 1):
                xml = xml.replace(('<'+field+' ').encode(), ('<'+field+' field="'+str(ordinal)+'" elem="0" ').encode())
    return xml

def request(*, filter_profile='controller_filter', plaintext=False, blocked=False, xml=None):
    xml = make_xml(filter_profile) if xml is None else xml
    # Reuse the exact independently authored public envelope rather than
    # regenerating platform-dependent ZipInfo creator metadata on Windows.
    template = json.loads((ROOT/'fixtures/mac-taxml/request.json').read_text())
    original = base64.b64decode(template['base64']); stream = BytesIO()
    with zipfile.ZipFile(BytesIO(original)) as source, zipfile.ZipFile(stream, 'w') as target:
        target.comment = source.comment
        for info in source.infolist():
            payload = source.read(info)
            if info.filename == 'return.xml': payload = xml
            elif info.filename == 'manifest.xml' and blocked:
                payload = payload.replace(b'</document>', b'<attributes><attribute><name>owned-unmodeled-hash</name><value>stale</value></attribute></attributes></document>', 1)
            target.writestr(info, payload)
    req = old.request(source=stream.getvalue(), plaintext=plaintext, xml=xml)
    carrier = make_carrier(); sha = digest(carrier)
    req['profile'].update(format=PROFILE, filter_profile=filter_profile, registry_order=[sha])
    req['carriers'] = [{'base64': base64.b64encode(carrier).decode(), 'sha256': sha}]
    return req

def build(destination=DEST):
    destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
    req = request(); blocked = request(blocked=True)
    blobs = {'owned-mac-date.xprf': make_carrier(), 'owned-mac-date.xml': make_xml(),
             'owned-mac-date.zip': base64.b64decode(req['base64']),
             'owned-mac-date-blocked.zip': base64.b64decode(blocked['base64'])}
    for name, data in blobs.items(): (destination / name).write_bytes(data)
    for name, value in [('request.json', req), ('null-request.json', request(filter_profile='null_filter')),
                        ('plaintext-request.json', request(plaintext=True)), ('blocked-request.json', blocked)]:
        (destination / name).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
    (destination / 'profile.json').write_text(json.dumps(req['profile'], indent=2, sort_keys=True)+'\n')
    manifest = {'format': 'tax-reborn-owned-mac-date-fixture-v1', 'vendor_bytes_included': False,
        'original_runtime_executions': 0, 'entities': 2, 'form_copies': 7, 'date_fields': 9,
        'native_factory_acceptance': False, 'native_date_load_executed': False,
        'files': {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())}
                  for p in sorted(destination.iterdir()) if p.is_file() and p.name not in ('manifest.json', 'README.md')}}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
    return manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--destination', type=Path, default=DEST)
    print(json.dumps(build(parser.parse_args().destination)))
