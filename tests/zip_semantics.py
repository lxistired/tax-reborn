"""Cross-platform ZIP assertions that ignore deflater byte choices."""
import base64, copy, hashlib, json, zipfile
from io import BytesIO


def zip_semantic_snapshot(blob):
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        return {
            "comment": archive.comment,
            "members": [
                {
                    "filename": info.filename,
                    "date_time": info.date_time,
                    "compress_type": info.compress_type,
                    "comment": info.comment,
                    "extra": info.extra,
                    "external_attr": info.external_attr,
                    "create_system": info.create_system,
                    "flag_bits": info.flag_bits,
                    "file_size": info.file_size,
                    "CRC": info.CRC,
                    "payload": archive.read(info),
                }
                for info in archive.infolist()
            ],
        }


def request_semantics(value):
    """Compare request JSON while treating ZIP base64 as decoded ZIP semantics."""
    normalized = copy.deepcopy(value)
    encoded = normalized.pop("base64", None)
    if encoded is None:
        return normalized
    blob = base64.b64decode(encoded)
    try:
        normalized["_zip_semantics"] = zip_semantic_snapshot(blob)
    except zipfile.BadZipFile:
        normalized["_base64_bytes"] = blob
    return normalized


def assert_request_json_semantics(testcase, actual_path, expected_path):
    actual = json.loads(actual_path.read_text(encoding="utf-8"))
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    testcase.assertEqual(request_semantics(actual), request_semantics(expected))


def assert_zip_semantics_equal(testcase, actual_blob, expected_blob):
    testcase.assertEqual(zip_semantic_snapshot(actual_blob), zip_semantic_snapshot(expected_blob))


def assert_fixture_manifest_integrity(testcase, fixture_dir):
    manifest_path = fixture_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        blob = (fixture_dir / name).read_bytes()
        testcase.assertEqual(len(blob), expected["bytes"], name)
        testcase.assertEqual(hashlib.sha256(blob).hexdigest(), expected["sha256"], name)
