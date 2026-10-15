"""Durable local exports through a user-controlled native save dialog."""
import base64
import binascii
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit

MAX_EXPORT_BYTES=15_000_000

class DesktopExport:
    def __init__(self,origin):
        self._origin=urlsplit(origin)
        self._window=None

    def save_file(self,filename,mime,encoded):
        if (not isinstance(filename,str) or not filename or len(filename)>240
                or not isinstance(mime,str) or len(mime)>160
                or not isinstance(encoded,str) or len(encoded)>20_000_000):
            raise ValueError('Invalid local export.')
        try:content=base64.b64decode(encoded,validate=True)
        except (ValueError,binascii.Error) as error:
            raise ValueError('Incomplete local export encoding.') from error
        if not content or len(content)>MAX_EXPORT_BYTES:
            raise ValueError('Local export size is unsupported.')
        safe_name=re.sub(r'[\\/\x00-\x1f<>:"|?*]','_',filename)
        import webview
        def select_destination():
            window=self._window
            current=urlsplit(window.get_current_url()) if window else None
            if (current is None or current.scheme!=self._origin.scheme
                    or current.netloc!=self._origin.netloc):
                raise ValueError('Local application origin required for exports.')
            return window.create_file_dialog(webview.SAVE_DIALOG,save_filename=safe_name)
        # Windows requires the native picker on its existing STA UI thread.
        # Cocoa's public dialog method already schedules onto its main thread.
        if sys.platform=='win32':
            from System import Func, Object
            owner=self._window.gui.BrowserView.instances[self._window.uid]
            chosen=(owner.Invoke(Func[Object](select_destination))
                    if owner.InvokeRequired else select_destination())
        else:
            chosen=select_destination()
        if not chosen:return {'cancelled':True,'saved':False}
        selected=chosen[0] if isinstance(chosen,(tuple,list)) else chosen
        if not isinstance(selected,str) or not selected:
            raise ValueError('Choose a local destination file.')
        target=Path(selected).expanduser().resolve()
        if not target.parent.is_dir() or target.is_dir():
            raise ValueError('Choose a file in an existing local folder.')
        temporary=None
        try:
            # Stage beside the destination so replace is atomic on its volume.
            # Close the file before replace on Windows. It is not owned by the
            # WebView download lifetime and never disappears at window close.
            with tempfile.NamedTemporaryFile(prefix='.tax-reborn-export-',
                    dir=target.parent,delete=False) as stream:
                temporary=Path(stream.name)
                stream.write(content);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,target);temporary=None
            if target.read_bytes()!=content:
                raise OSError('Saved local export failed complete readback.')
        finally:
            if temporary is not None:
                try:temporary.unlink()
                except FileNotFoundError:pass
        return {'saved':True,'cancelled':False,'bytes':len(content)}
