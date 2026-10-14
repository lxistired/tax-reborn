"""Native-service origin persistence and conflict behavior for local documents."""
from pathlib import Path
import tempfile
import unittest
import desktop


class DesktopDocumentOrigin(unittest.TestCase):
    def test_same_workspace_reopens_at_same_origin(self):
        with tempfile.TemporaryDirectory() as path:
            first = desktop.LocalService(Path(path)).start()
            origin = first.url
            first.stop()
            reopened = desktop.LocalService(Path(path)).start()
            try:
                self.assertEqual(reopened.url, origin)
            finally:
                reopened.stop()

    def test_active_workspace_conflict_does_not_hide_documents_with_new_origin(self):
        with tempfile.TemporaryDirectory() as path:
            first = desktop.LocalService(Path(path)).start()
            try:
                with self.assertRaisesRegex(RuntimeError, 'different origin was not selected'):
                    desktop.LocalService(Path(path))
            finally:
                first.stop()
