#!/usr/bin/env python3
"""Package reviewable source without builds, private evidence or user returns."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / 'VERSION').read_text().strip()
DIRECTORIES = {'android', 'ios', '.github', 'assets', 'docs', 'fixtures', 'forms', 'qa', 'scripts', 'tests', 'vendor', 'web'}
TOP_FILES = {'AGENTS.md', 'LICENSE', 'NOTICE', 'README.md', 'VERSION',
             'desktop.py', 'server.py', 'return_metadata.py', 'investment_metadata.py', 'forms.py', 'tax_engine.py', 'tax_extended.py',
             'tax_credits.py', 'tax_additional.py', 'tax_longtail.py', 'tax_filing.py','presentation_schema.py','privacy_review.py', 'official_forms.py', 'rules_2025.json',
             'requirements-desktop.txt', 'requirements.txt', '.gitignore', '.gitattributes'}
EXCLUDED_PARTS = {'__pycache__', '.git', 'node_modules', '.venv', 'dist', 'build', 'work'}

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
            archive.write(path, f'Tax-Reborn-{VERSION}/{relative.as_posix()}')
            records.append({'file': relative.as_posix(), 'bytes': path.stat().st_size,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {'product': 'Tax Reborn', 'version': VERSION, 'file': target.name,
                'license': 'AGPL-3.0-only', 'includes_opentax_corresponding_source': True,
                'includes_vendor_intuit_binaries': False, 'includes_user_returns': False,
                'bytes': target.stat().st_size,
                'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'files': records}
    (out / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}, indent=2))

if __name__ == '__main__':
    main()
