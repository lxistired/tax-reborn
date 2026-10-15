#!/usr/bin/env python3
"""Package reviewable source without builds, private evidence or user returns."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / 'VERSION').read_text().strip()
DIRECTORIES = {'android', 'ios', '.github', 'assets', 'docs', 'fixtures', 'forms', 'interop', 'qa', 'scripts', 'tests', 'vendor', 'web'}
TOP_FILES = {'AGENTS.md', 'LICENSE', 'NOTICE', 'README.md', 'VERSION',
             'desktop.py', 'desktop_export.py', 'server.py', 'source_documents.py', 'return_metadata.py', 'setup_preparation.py', 'investment_metadata.py','income_preparation.py', 'forms.py', 'tax_engine.py', 'tax_special_capital.py','tax_child_income.py', 'tax_extended.py',
             'tax_credits.py', 'tax_additional.py', 'tax_longtail.py', 'tax_filing.py','presentation_schema.py','privacy_review.py', 'official_forms.py', 'rules_2025.json',
             'requirements-desktop.txt', 'requirements.txt', '.gitignore', '.gitattributes'}
EXCLUDED_PARTS = {'__pycache__', '.git', 'node_modules', '.venv', 'dist', 'build', 'work'}
TEXT_SUFFIXES = {'.py', '.js', '.cjs', '.mjs', '.json', '.txt', '.md', '.html', '.css', '.xml', '.svg', '.yml', '.yaml', '.java', '.swift', '.plist', '.ps1', '.sh', '.properties', '.webmanifest'}

def main():
    out = ROOT / 'dist' / 'preview3'
    out.mkdir(parents=True, exist_ok=True)
    target = out / f'Tax-Reborn-{VERSION}-source.zip'
    records = []
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(ROOT.rglob('*')):
            relative = path.relative_to(ROOT)
            if EXCLUDED_PARTS.intersection(relative.parts):
                continue
            if relative.parts[0] not in DIRECTORIES and str(relative) not in TOP_FILES:
                continue
            if path.is_symlink():
                raise ValueError(f'Unexpected source symlink: {relative}')
            if not path.is_file() or path.suffix in {'.pyc', '.jks', '.keystore', '.sqlite', '.db'}:
                continue
            payload = path.read_bytes()
            # Git stores these source text files with LF. Existing Windows QA
            # working copies can have CRLF while the Git tree remains clean.
            # Preserve binary templates, images, wheels and WASM byte-for-byte.
            if path.suffix.lower() in TEXT_SUFFIXES:
                payload = payload.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')
            entry = zipfile.ZipInfo.from_file(path, f'Tax-Reborn-{VERSION}/{relative.as_posix()}')
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, payload)
            records.append({'file': relative.as_posix(), 'bytes': len(payload),
                            'sha256': hashlib.sha256(payload).hexdigest()})
    manifest = {'product': 'Tax Reborn', 'version': VERSION, 'file': target.name,
                'license': 'AGPL-3.0-only', 'includes_opentax_corresponding_source': True,
                'includes_vendor_intuit_binaries': False, 'includes_user_returns': False,
                'bytes': target.stat().st_size,
                'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'files': records}
    (out / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}, indent=2))

if __name__ == '__main__':
    main()
