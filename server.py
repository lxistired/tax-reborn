#!/usr/bin/env python3
"""Tax Reborn: loopback-only local tax preparation and private SQLite saves."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import html
import json
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit
import uuid

import tax_engine
import return_metadata

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)).resolve()
VERSION = (BASE / 'VERSION').read_text(encoding='utf-8').strip()
WEB = BASE / 'web'
ID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
MAX_BODY = 2_000_000


def default_data_dir():
    if path := os.environ.get('TAX_REBORN_DATA_DIR'):
        return Path(path).expanduser().resolve()
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'Tax Reborn'
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'Tax Reborn'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'Tax Reborn'


def capabilities():
    import presentation_schema
    return {**presentation_schema.capabilities(), 'product': 'Tax Reborn', 'project_number': '000002', 'version': VERSION,
            'tax_year': 2025, 'jurisdiction': 'US federal', 'currency': 'USD',
            'electronic_filing': False, 'state_returns': '31 full-year resident calculation drafts; separate scope review required', 'official_product_parity': False,
            'storage': 'private local SQLite', 'requires_account': False}


def schema():
    return {'default_return': tax_engine.default_return(), 'demos': tax_engine.demo_returns(),
            'capabilities': capabilities()}


def worksheet(record):
    data, result = record['data'], record['result']
    issues = ''.join('<li>' + html.escape(str(x)) + '</li>' for x in result.get('blocking_issues', []))
    rows = ''.join('<tr><td>' + html.escape(str(k)) + '</td><td>' + ('Not computed' if k in result.get('not_computed_lines',[]) else '$' + format(v, ',.0f')) + '</td></tr>'
                   for k, v in result['lines'].items() if isinstance(v, (int, float)))
    trace = ''.join('<tr><td>' + html.escape(str(x.get('label', ''))) + '</td><td>' +
                    html.escape(str(x.get('amount', ''))) + '</td><td>' + html.escape(str(x.get('source', ''))) + '</td></tr>'
                    for x in result.get('trace', []))
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>2025 tax calculation worksheet</title>
<style>body{{font:14px system-ui;max-width:900px;margin:40px auto;color:#162426}}table{{border-collapse:collapse;width:100%}}td,th{{padding:7px;border-bottom:1px solid #ddd}}td:nth-child(2){{text-align:right}}.notice{{padding:14px;border:2px solid #a76a00}}@media print{{body{{margin:20px}}}}</style>
<h1>Tax Reborn · 2025 US federal worksheet</h1><p>{html.escape(str(data.get('name','Untitled')))} · {html.escape(str(data['filing_status']))} · {html.escape(record['updated_at'])}</p>
<p class="notice">CALCULATION DRAFT · Not submitted to the IRS. State drafts are calculated separately. Electronic filing is unavailable. Eligibility and unsupported situations must be reviewed.</p>
<ul>{issues}</ul><h2>Form 1040 calculation lines</h2><table><thead><tr><th>Line</th><th>Whole dollars (USD)</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Calculation trail</h2><table><thead><tr><th>Rule</th><th>Amount</th><th>Source</th></tr></thead><tbody>{trace}</tbody></table>
<p>Independently implemented by @lxistired. This is not an Intuit product. Return ID: {record['id']}</p></html>'''


class Store:
    def __init__(self, directory):
        self.directory = Path(directory).expanduser().resolve()
        if getattr(sys, 'frozen', False) and (self.directory == BASE or BASE in self.directory.parents):
            raise ValueError('Save data outside the installed application')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / 'returns.sqlite'
        with self.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS returns (id TEXT PRIMARY KEY, name TEXT NOT NULL, updated_at TEXT NOT NULL, data TEXT NOT NULL, result TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS state_inputs (return_id TEXT NOT NULL, jurisdiction TEXT NOT NULL, input TEXT NOT NULL, PRIMARY KEY(return_id,jurisdiction))')
            conn.execute('CREATE TABLE IF NOT EXISTS preparation_metadata (return_id TEXT PRIMARY KEY, metadata TEXT NOT NULL)')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def list(self):
        with self.connect() as conn:
            return [{'id': r['id'], 'name': r['name'], 'updated_at': r['updated_at'],
                     'summary': json.loads(r['result'])['summary']}
                    for r in conn.execute('SELECT id,name,updated_at,result FROM returns ORDER BY updated_at DESC')]

    def get(self, ident):
        if not ID.fullmatch(ident):
            raise ValueError('Invalid return identifier')
        with self.connect() as conn:
            row = conn.execute('SELECT * FROM returns WHERE id=?', (ident,)).fetchone()
            if row is not None:
                data = json.loads(row['data'])
                stored = conn.execute('SELECT metadata FROM preparation_metadata WHERE return_id=?', (ident,)).fetchone()
                metadata = return_metadata.normalize(data, json.loads(stored['metadata']) if stored else None,
                                                     tax_engine.ROW_DEFAULTS['w2'])
                encoded = json.dumps(metadata, allow_nan=False)
                if stored is None or stored['metadata'] != encoded:
                    conn.execute('INSERT INTO preparation_metadata VALUES (?,?) ON CONFLICT(return_id) DO UPDATE SET metadata=excluded.metadata', (ident, encoded))
        if row is None:
            raise FileNotFoundError('Return not found')
        return {'id': row['id'], 'updated_at': row['updated_at'], 'data': data,
                'result': json.loads(row['result']), 'states': self.states(ident), 'metadata': metadata}

    def save(self, payload):
        if not isinstance(payload, dict) or not isinstance(payload.get('data'), dict):
            raise ValueError('Expected a return object in data')
        ident = payload.get('id') or str(uuid.uuid4())
        if not isinstance(ident, str) or not ID.fullmatch(ident):
            raise ValueError('Return identifier must be a UUIDv4')
        data = payload['data']
        name = data.get('name', 'Untitled return')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
            raise ValueError('Return name must contain 1 to 200 characters')
        result = tax_engine.calculate_return(data)
        stamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            if 'expected_updated_at' in payload:
                expected = payload['expected_updated_at']
                if expected is not None and (not isinstance(expected, str) or len(expected) > 40):
                    raise ValueError('Invalid saved-return revision')
                conn.execute('BEGIN IMMEDIATE')
                saved = conn.execute('SELECT updated_at FROM returns WHERE id=?', (ident,)).fetchone()
                actual = saved['updated_at'] if saved else None
                if actual != expected:
                    raise ValueError('This saved return changed in another workspace. Reopen it before saving the import')
            previous = conn.execute('SELECT metadata FROM preparation_metadata WHERE return_id=?', (ident,)).fetchone()
            metadata = return_metadata.normalize(data, payload.get('metadata'), tax_engine.ROW_DEFAULTS['w2'],
                                                 json.loads(previous['metadata']) if previous else None)
            conn.execute('INSERT INTO returns VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,updated_at=excluded.updated_at,data=excluded.data,result=excluded.result',
                         (ident, name.strip(), stamp, json.dumps(data, allow_nan=False), json.dumps(result, allow_nan=False)))
            conn.execute('INSERT INTO preparation_metadata VALUES (?,?) ON CONFLICT(return_id) DO UPDATE SET metadata=excluded.metadata',
                         (ident, json.dumps(metadata, allow_nan=False)))
        return self.get(ident)

    def states(self, ident):
        with self.connect() as conn:
            return {r['jurisdiction']: json.loads(r['input']) for r in conn.execute('SELECT jurisdiction,input FROM state_inputs WHERE return_id=?', (ident,))}

    def save_state(self, ident, payload):
        self.get(ident)
        jurisdiction = payload.get('jurisdiction')
        allowed = 'il va ca ny pa nj oh nc ga md mo wi mn sc al or ok ct ks ar nm ne id wv me hi ri mt de nd vt'.split()
        values = payload.get('input')
        if jurisdiction not in allowed or not isinstance(values, dict) or values.get('jurisdiction') != jurisdiction or len(values) > 1200:
            raise ValueError('Expected a supported state and matching state input')
        for key, value in values.items():
            if not isinstance(key, str) or len(key) > 150 or not isinstance(value, (str, int, float, bool)) or isinstance(value, str) and len(value) > 1000:
                raise ValueError('State input must contain bounded simple values')
        encoded = json.dumps(values, allow_nan=False)
        if len(encoded) > 150000:
            raise ValueError('State draft too large')
        with self.connect() as conn:
            conn.execute('INSERT INTO state_inputs VALUES (?,?,?) ON CONFLICT(return_id,jurisdiction) DO UPDATE SET input=excluded.input', (ident,jurisdiction,encoded))
        return {'states': self.states(ident)}

    def delete(self, ident):
        self.get(ident)
        with self.connect() as conn:
            conn.execute('DELETE FROM state_inputs WHERE return_id=?', (ident,))
            conn.execute('DELETE FROM preparation_metadata WHERE return_id=?', (ident,))
            conn.execute('DELETE FROM returns WHERE id=?', (ident,))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # No tax values, document names or client addresses enter access logs.
        pass

    def send_data(self, status, body, content_type='application/json; charset=utf-8', filename=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        elif isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store' if self.path.startswith('/api/') else 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; worker-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'")
        if filename:
            self.send_header('Content-Disposition', 'attachment; filename="' + filename + '"')
        self.end_headers()
        self.wfile.write(body)

    def validate_origin(self, mutation=False):
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        host = self.headers.get('Host', '')
        if host not in allowed:
            raise ValueError('Host must match this local service')
        origin = self.headers.get('Origin')
        if origin and origin not in {'http://' + value for value in allowed}:
            raise ValueError('Foreign Origin is not allowed')
        if mutation and not (self.headers.get('Content-Type', '').split(';')[0] == 'application/json' and origin):
            raise ValueError('Same-origin JSON required for saves and deletion')

    def read_json(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise ValueError('Invalid request length')
        if not 0 < size <= MAX_BODY:
            raise ValueError('Return exceeds the permitted size')
        return json.loads(self.rfile.read(size), parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))

    def route(self, method):
        try:
            self.validate_origin(method in ('POST', 'DELETE'))
            path = unquote(urlsplit(self.path).path)
            if method == 'GET' and path == '/api/health':
                return self.send_data(200, capabilities())
            if method == 'GET' and path == '/api/schema':
                return self.send_data(200, schema())
            if method == 'POST' and path == '/api/calculate':
                return self.send_data(200, tax_engine.calculate_return(self.read_json()))
            if path == '/api/returns':
                if method == 'GET':
                    return self.send_data(200, {'returns': self.server.store.list()})
                if method == 'POST':
                    return self.send_data(200, self.server.store.save(self.read_json()))
            if path.startswith('/api/returns/'):
                parts = path.split('/')
                if len(parts) not in (4, 5):
                    raise FileNotFoundError('Unknown endpoint')
                record = self.server.store.get(parts[3])
                if len(parts) == 4 and method == 'GET':
                    return self.send_data(200, record)
                if len(parts) == 4 and method == 'DELETE':
                    self.server.store.delete(parts[3])
                    return self.send_data(200, {'ok': True})
                if len(parts) == 5 and parts[4] == 'states':
                    if method == 'GET': return self.send_data(200, {'states':record['states']})
                    if method == 'POST': return self.send_data(200, self.server.store.save_state(parts[3],self.read_json()))
                if len(parts) == 5 and method == 'GET':
                    if parts[4] == 'export.json':
                        return self.send_data(200, {'format':'tax-reborn-return-v1', **record}, filename='tax-reborn-2025-' + record['id'] + '.json')
                    if parts[4] == 'worksheet.html':
                        return self.send_data(200, worksheet(record), 'text/html; charset=utf-8', 'tax-reborn-2025-worksheet.html')
                    if parts[4] == 'form1040.pdf':
                        import forms
                        return self.send_data(200, forms.form1040_pdf(record), 'application/pdf', 'tax-reborn-2025-1040-DRAFT.pdf')
                    if parts[4] == 'paper-packet.pdf':
                        import forms
                        return self.send_data(200, forms.paper_packet_pdf(record), 'application/pdf', 'tax-reborn-2025-paper-packet-DRAFT.pdf')
                    if parts[4] == 'masked-review.pdf':
                        import forms
                        return self.send_data(200, forms.masked_review_pdf(record), 'application/pdf', 'tax-reborn-2025-MASKED-REVIEW.pdf')
                    if parts[4] == 'paper-checklist.json':
                        import forms
                        return self.send_data(200, forms.packet_status(record))
            if method == 'GET' and not path.startswith('/api/'):
                if path in ('/tax_engine.py', '/tax_special_capital.py','/tax_child_income.py', '/tax_extended.py', '/tax_credits.py', '/tax_additional.py', '/tax_longtail.py', '/tax_filing.py', '/presentation_schema.py', '/privacy_review.py', '/rules_2025.json', '/forms.py', '/official_forms.py'):
                    target = BASE / path[1:]
                elif path.startswith('/forms/'):
                    target=(BASE/path[1:]).resolve()
                    if (BASE/'forms').resolve() not in target.parents or target.suffix not in ('.json','.pdf'):
                        raise FileNotFoundError('Asset not found')
                else:
                    target = (WEB / (path.lstrip('/') or 'index.html')).resolve()
                    if WEB.resolve() not in target.parents:
                        raise FileNotFoundError('Asset not found')
                if not target.is_file():
                    raise FileNotFoundError('Asset not found')
                mime = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
                if target.suffix in ('.js', '.mjs'):
                    mime = 'text/javascript; charset=utf-8'
                return self.send_data(200, target.read_bytes(), mime)
            raise FileNotFoundError('Unknown endpoint')
        except FileNotFoundError as error:
            self.send_data(404, {'error': str(error)})
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            self.send_data(400, {'error': str(error)})
        except Exception:
            self.send_data(500, {'error': 'The local service could not complete this operation. Your saved return was not overwritten by a failed calculation.'})

    def do_GET(self):
        self.route('GET')

    def do_POST(self):
        self.route('POST')

    def do_DELETE(self):
        self.route('DELETE')


def create_server(port=8782, data_dir=None):
    http = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    http.daemon_threads = True
    http.store = Store(data_dir or default_data_dir())
    http.data_dir = http.store.directory
    return http


def main():
    parser = argparse.ArgumentParser(description='Tax Reborn — US federal tax year 2025')
    parser.add_argument('--port', type=int, default=8782)
    parser.add_argument('--data-dir', type=Path)
    args = parser.parse_args()
    http = create_server(args.port, args.data_dir)
    print(f'Tax Reborn {VERSION}: http://127.0.0.1:{http.server_port}/ (2025 US federal; no electronic filing)', flush=True)
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        http.server_close()


if __name__ == '__main__':
    main()
