#!/usr/bin/env python3
"""Author a cleartext archive from the existing independently authored TaxML.

This is a caller-owned source profile, not output of the licensed original.
The experience and unknown documents are stored-only fictional content.
"""
from pathlib import Path
import base64
from io import BytesIO
import json
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'fixtures/taxml'
DEST = ROOT / 'fixtures/plaintext-container'
NS = 'http://schemas.intuit.com/LocalCfpContainer.xsd'
TAXML = '/tax/income/individual/taxreturn/taxml'
EXPERIENCE = '/tax/income/individual/taxreturn/experience/turbotax/xml'


def make_source(*, method=zipfile.ZIP_DEFLATED, selected_extra=b'', other_extra=b''):
    manifest = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<Manifest xmlns="{NS}">\n'
                ' <!-- Independently authored cleartext archive. Preserve these bytes. -->\n'
                ' <documents>\n'
                f'  <document><entityKey>return.xml</entityKey><entityType>{TAXML}</entityType></document>\n'
                f'  <document><entityKey>experience.xml</entityKey><entityType>{EXPERIENCE}</entityType></document>\n'
                '  <document><entityKey>stored-extra.bin</entityKey><entityType>urn:tax-reborn:owned-stored-only</entityType></document>\n'
                ' </documents>\n</Manifest>\n').encode()
    rows = [
        ('manifest.xml', manifest),
        ('return.xml', (FIX / 'synthetic-mixed-income.xml').read_bytes()),
        ('experience.xml', b'<?xml version="1.0"?><OwnedExperience status="stored-only"/>\n'),
        ('stored-extra.bin', b'Owned unrelated document\x00\xff\x00\x04'),
        ('unreferenced-notes.bin', b'Unreferenced owned bytes\x00\xff\x00\x01'),
    ]
    output = BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.comment = b'Owned archive comment retained exactly'
        for index, (name, data) in enumerate(rows):
            info = zipfile.ZipInfo(name, date_time=(2025, 12, 31, 12, 0, index * 2))
            info.compress_type = method
            info.comment = ('Owned member ' + str(index)).encode()
            info.extra = selected_extra if name == 'return.xml' else other_extra if name == 'unreferenced-notes.bin' else b''
            archive.writestr(info, data, compresslevel=9)
    return output.getvalue()


def request(source=None):
    carriers = []
    for name in ['synthetic-modern-windows-w2.xprf', 'synthetic-native-interest.xprf', 'synthetic-native-dividend.xprf']:
        raw = (FIX / name).read_bytes()
        carriers.append({'base64': base64.b64encode(raw).decode(), 'sha256': hashlib.sha256(raw).hexdigest()})
    return {'base64': base64.b64encode(make_source() if source is None else source).decode(),
            'container': 'cleartext_persistence_container',
            'profile': json.loads((FIX / 'synthetic-mixed-income-profile.json').read_text()),
            'carriers': carriers, 'profile_acknowledged': True}


def blocked_source():
    """Owned unknown metadata witness; never a claim about a vendor hash field."""
    original = make_source()
    output = BytesIO()
    with zipfile.ZipFile(BytesIO(original)) as archive, zipfile.ZipFile(output, 'w') as target:
        target.comment = archive.comment
        for info in archive.infolist():
            data = archive.read(info)
            if info.filename == 'manifest.xml':
                data = data.replace(b'</document>', b'<attributes><attribute><name>owned-payload-sha256</name><value>unmodeled</value></attribute></attributes></document>', 1)
            target.writestr(info, data)
    return output.getvalue()


if __name__ == '__main__':
    DEST.mkdir(parents=True, exist_ok=True)
    sample = make_source()
    (DEST / 'synthetic-cleartext-container.zip').write_bytes(sample)
    payload = json.dumps(request(sample), indent=2) + '\n'
    (DEST / 'request.json').write_text(payload)
    target = ROOT / 'web/samples/plaintext-container-request.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload)
    blocked = blocked_source()
    (DEST / 'synthetic-cleartext-container-blocked.zip').write_bytes(blocked)
    (ROOT / 'web/samples/plaintext-container-blocked-request.json').write_text(json.dumps(request(blocked), indent=2) + '\n')
    print(json.dumps({'bytes': len(sample), 'sha256': hashlib.sha256(sample).hexdigest(),
                      'synthetic_only': True, 'native_original_execution': 0}))
