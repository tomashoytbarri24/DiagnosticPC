from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from core import update_manager as um
from core.version import VERSION, STAGE


class _Response:
    def __init__(self, data: bytes, headers=None):
        self._io = io.BytesIO(data)
        self.headers = headers or {}

    def read(self, size=-1):
        return self._io.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class InternalUpdaterV118Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_data = os.environ.get("COREPULSE_DATA_DIR")
        self.old_repo = os.environ.get("COREPULSE_UPDATE_REPOSITORY")
        os.environ["COREPULSE_DATA_DIR"] = str(Path(self.temp.name) / "data")
        os.environ["COREPULSE_UPDATE_REPOSITORY"] = "tomashoytbarri24/DiagnosticPC"

    def tearDown(self):
        if self.old_data is None:
            os.environ.pop("COREPULSE_DATA_DIR", None)
        else:
            os.environ["COREPULSE_DATA_DIR"] = self.old_data
        if self.old_repo is None:
            os.environ.pop("COREPULSE_UPDATE_REPOSITORY", None)
        else:
            os.environ["COREPULSE_UPDATE_REPOSITORY"] = self.old_repo
        self.temp.cleanup()

    def test_version_stage(self):
        self.assertTrue(VERSION.isdecimal())
        self.assertTrue(bool(STAGE))

    def test_version_parser(self):
        self.assertEqual(um.parse_version_key("V118"), (118,))
        self.assertEqual(um.parse_version_key("CorePulse V119"), (119,))
        self.assertEqual(um.parse_version_key("v1.2.3"), (1, 2, 3))

    def test_internal_includes_prerelease_stable_does_not(self):
        stable = um.ReleaseInfo("V118", "V118", "", False, None, None, ())
        preview = um.ReleaseInfo("V119", "V119 beta", "", True, None, None, ())
        self.assertEqual(um.choose_release([stable, preview], um.CHANNEL_INTERNAL).tag, "V119")
        self.assertEqual(um.choose_release([stable, preview], um.CHANNEL_STABLE).tag, "V118")

    def test_check_release_and_asset_selection(self):
        next_version = str(int(VERSION) + 1)
        zip_bytes = b"zip"
        digest = hashlib.sha256(zip_bytes).hexdigest()
        payload = [{
            "tag_name": f"V{next_version}", "name": f"CorePulse V{next_version}", "body": "Notas",
            "draft": False, "prerelease": True, "published_at": "2026-09-14T12:00:00Z",
            "html_url": "https://github.com/tomashoytbarri24/DiagnosticPC/releases/tag/V119",
            "assets": [
                {"name": f"CorePulse_V{next_version}.zip", "size": 3, "browser_download_url": "https://example/zip", "url": "https://api.example/zip", "digest": f"sha256:{digest}", "content_type": "application/zip"},
                {"name": f"CorePulse_Setup_V{next_version}.exe", "size": 10, "browser_download_url": "https://example/exe", "url": "https://api.example/exe", "digest": "sha256:" + "0" * 64, "content_type": "application/octet-stream"},
            ],
        }]
        data = json.dumps(payload).encode()
        result = um.check_for_update(um.CHANNEL_INTERNAL, opener=lambda *a, **k: _Response(data))
        self.assertTrue(result["available"])
        release = result["latest"]
        self.assertEqual(um.choose_asset(release, frozen=False).name, f"CorePulse_V{next_version}.zip")
        self.assertEqual(um.choose_asset(release, frozen=True).name, f"CorePulse_Setup_V{next_version}.exe")

    def test_verified_download_and_safe_source_stage(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("CorePulse_119/main.py", "print('ok')\n")
            archive.writestr("CorePulse_119/core/version.py", 'VERSION = "119"\n')
        payload = buf.getvalue()
        digest = hashlib.sha256(payload).hexdigest()
        asset = um.ReleaseAsset("CorePulse_119.zip", len(payload), "https://example/zip", "", f"sha256:{digest}", "application/zip")
        release = um.ReleaseInfo("V119", "V119", "", True, None, "https://example/release", (asset,))
        downloaded = um.download_asset(asset, release, opener=lambda *a, **k: _Response(payload, {"Content-Length": str(len(payload))}))
        self.assertTrue(downloaded["verified"])
        staged = um.stage_source_release(downloaded)
        self.assertTrue(Path(staged["entry"]).is_file())
        self.assertIn("V119", staged["directory"])

    def test_bad_digest_is_rejected(self):
        payload = b"not-the-published-file"
        asset = um.ReleaseAsset("CorePulse_119.zip", len(payload), "https://example/zip", "", "sha256:" + "0" * 64, "application/zip")
        release = um.ReleaseInfo("V119", "V119", "", True, None, None, (asset,))
        with self.assertRaises(um.UpdateError):
            um.download_asset(asset, release, opener=lambda *a, **k: _Response(payload, {"Content-Length": str(len(payload))}))

    def test_source_tree_integration_markers(self):
        root = Path(__file__).resolve().parents[1]
        main = (root / "main.py").read_text(encoding="utf-8")
        dashboard = (root / "gui" / "dashboard.py").read_text(encoding="utf-8")
        dialog = (root / "gui" / "update_dialog.py").read_text(encoding="utf-8")
        self.assertIn("def open_update_center", main)
        self.assertIn("Actualizaciones", dashboard)
        self.assertIn("Desarrollo", dialog)
        self.assertIn("Fuente portable", dialog)


if __name__ == "__main__":
    unittest.main()
