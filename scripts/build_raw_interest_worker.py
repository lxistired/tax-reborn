#!/usr/bin/env python3
"""Bundle the local interest reader from owned sources and public Pyodide.

Original calculation resources are never build inputs. Users select those
files locally at runtime. Use --check to verify a saved source checkout.
"""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
RUNTIME = WEB / 'raw-interest-runtime'


def outputs():
    manifest = json.loads((RUNTIME / 'raw-interest-runtime.json').read_text())
    assert manifest['format'] == 'tax-reborn-private-raw-interest-runtime-v1'
    paths = [row['path'] for row in manifest['files']]
    assert len(paths) == len(set(paths)) <= 256
    actual = {p.relative_to(RUNTIME).as_posix() for p in RUNTIME.rglob('*.py')}
    actual.update({'raw-interest-authority.json', 'CS24-runtime-authority.json',
                   'CS37-resource-authority.json'})
    assert set(paths) == actual, 'Runtime manifest must cover every owned module'
    for row in manifest['files']:
        path = Path(row['path'])
        assert not path.is_absolute() and '..' not in path.parts
        data = (RUNTIME / path).read_bytes()
        row['bytes'] = len(data)
        row['sha256'] = hashlib.sha256(data).hexdigest()
    prefix = (WEB / 'tax-worker.js').read_text().split('// Source:', 1)[0]
    worker = (prefix.rstrip() + '\n\n'
              + (WEB / 'vendor/pyodide/pyodide.js').read_text() + '\n'
              + (RUNTIME / 'raw-interest-worker-source.js').read_text())
    return {
        RUNTIME / 'raw-interest-runtime.json': json.dumps(manifest, indent=2) + '\n',
        RUNTIME / 'raw-interest-worker.js': worker,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for target, text in outputs().items():
        data = text.encode('utf-8')
        if args.check:
            assert target.read_bytes() == data, 'Rebuild ' + target.name
        else:
            target.write_bytes(data)
    print('Local interest worker and complete owned-module manifest verified'
          if args.check else 'Local interest worker and manifest rebuilt')
