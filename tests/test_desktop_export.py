"""User-selected exports remain real files after the native shell closes."""
import base64
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from desktop_export import DesktopExport

class FakeWindow:
    def __init__(self,path,url='http://127.0.0.1:27145/'):
        self.path=path;self.url=url;self.dialog_calls=[]
    def get_current_url(self):return self.url
    def create_file_dialog(self,kind,**kwargs):
        self.dialog_calls.append((kind,kwargs));return self.path

class DurableDesktopExport(unittest.TestCase):
    def run_export(self,window,content=b'independent binary export\0\xff'):
        export=DesktopExport('http://127.0.0.1:27145/');export._window=window
        with patch.dict(sys.modules,{'webview':SimpleNamespace(SAVE_DIALOG='save')}):
            return export.save_file('synthetic.taxbin','application/octet-stream',base64.b64encode(content).decode())

    def test_real_bytes_survive_bridge_and_separate_process_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'selected.taxbin';content=b'\x00\xffowned source\r\n'*100
            window=FakeWindow((str(path),));result=self.run_export(window,content)
            self.assertTrue(result['saved']);self.assertEqual(result['bytes'],len(content))
            del window
            r=subprocess.run([sys.executable,'-c','from pathlib import Path;import sys;sys.stdout.buffer.write(Path(sys.argv[1]).read_bytes())',str(path)],capture_output=True,check=True)
            self.assertEqual(r.stdout,content)
            self.assertEqual([p.name for p in path.parent.iterdir()],['selected.taxbin'])

    def test_cancel_never_changes_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'existing.pdf';path.write_bytes(b'old source')
            result=self.run_export(FakeWindow(None));self.assertTrue(result['cancelled'])
            self.assertEqual(path.read_bytes(),b'old source')

    def test_explicitly_selected_existing_file_is_replaced_and_read_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'selected.taxbin';path.write_bytes(b'previous export')
            self.run_export(FakeWindow(str(path)),b'new complete source')
            self.assertEqual(path.read_bytes(),b'new complete source')

    def test_foreign_origin_rejected_before_save_picker(self):
        for url in ('https://example.invalid/','http://127.0.0.1:27146/','http://localhost:27145/'):
            w=FakeWindow(None,url)
            with self.subTest(url=url),self.assertRaisesRegex(ValueError,'origin'):self.run_export(w)
            self.assertFalse(w.dialog_calls)

    def test_invalid_encoding_or_size_never_opens_picker(self):
        w=FakeWindow(None);export=DesktopExport('http://127.0.0.1:27145/');export._window=w
        for value in ('%%%','',base64.b64encode(b'x'*15_000_001).decode()):
            with self.assertRaises(ValueError):export.save_file('file.pdf','application/pdf',value)
        self.assertFalse(w.dialog_calls)

    def test_write_failure_preserves_prior_file_and_cleans_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'selected.taxbin';path.write_bytes(b'prior export')
            with patch('desktop_export.os.replace',side_effect=PermissionError('selected file open')):
                with self.assertRaises(PermissionError):self.run_export(FakeWindow((str(path),)))
            self.assertEqual(path.read_bytes(),b'prior export')
            self.assertEqual([p.name for p in path.parent.iterdir()],['selected.taxbin'])

if __name__=='__main__':unittest.main()
