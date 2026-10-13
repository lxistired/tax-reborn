"""PyInstaller runtime hook: report failures only for synthetic --smoke-test runs.

Normal application launches do not log exceptions or tax inputs through this
hook. Windowed builds otherwise hide an uncaught exception behind a native
dialog, which can make CI report a timeout instead of the actual failure.
"""
import json
import os
from pathlib import Path
import sys
import traceback

if '--smoke-test' in sys.argv and '--smoke-report' in sys.argv:
    _report_index = sys.argv.index('--smoke-report') + 1
    if _report_index < len(sys.argv):
        _report = Path(sys.argv[_report_index]).resolve()
        _report.parent.mkdir(parents=True, exist_ok=True)
        _log = _report.with_name(_report.stem + '-diagnostic.txt').open('a', encoding='utf-8')
        if sys.stdout is None:
            sys.stdout = _log
        if sys.stderr is None:
            sys.stderr = _log

        def _synthetic_smoke_exception(kind, error, stack):
            _trace = ''.join(traceback.format_exception(kind, error, stack))
            try:
                _log.write(_trace)
                _log.flush()
                _report.write_text(json.dumps({
                    'product': 'Tax Reborn', 'all_passed': False,
                    'frozen': bool(getattr(sys, 'frozen', False)),
                    'platform': sys.platform, 'synthetic_smoke_failure': True,
                    'exception_type': kind.__name__, 'error': str(error),
                    'traceback': _trace,
                }, indent=2) + '\n', encoding='utf-8')
            finally:
                # Do not leave an exception dialog waiting for human input.
                _log.close()
                os._exit(1)

        sys.excepthook = _synthetic_smoke_exception
