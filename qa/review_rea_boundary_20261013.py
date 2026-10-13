#!/usr/bin/env python3
"""Read-only count/provenance/public-source review for this recorded REA batch.

No application or vendor binary is executed. JSON is printed to stdout. A
source ZIP can be checked without extraction; DMG payload mounting and a general
secret scan are outside this script's scope.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_contains_any(path, markers):
    """Stream text-marker checks, including large producer-shaped JSON files."""
    wanted = [marker.encode("utf-8") for marker in markers]
    overlap = max(len(marker) for marker in wanted) - 1
    tail = b""
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            text = tail + chunk
            if any(marker in text for marker in wanted):
                return True
            tail = text[-overlap:]
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-dir", type=Path, required=True)
    parser.add_argument("--private-evidence-dir", type=Path, required=True)
    parser.add_argument("--original-bytes-root", type=Path)
    parser.add_argument("--source-zip", type=Path)
    args = parser.parse_args()
    public = args.public_dir.resolve()
    private = args.private_evidence_dir.resolve()
    for selected in (public, private, args.original_bytes_root):
        if selected is not None and selected.resolve() in (Path("/"), Path.home()):
            parser.error("Select bounded project directories, not / or the home directory.")
    checks = []

    def check(name, passed, detail=None):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    qa = read_json(public / "qa/rea-reconstruction-batch-20261013.json")
    canonical = read_json(private / "canonical-evidence-index.json")["rows"]
    grouped = Counter(row["binary"] for row in canonical)
    check("desktop61+4, media16 excluded",
          grouped == {"TurboTax 2025": 61, "MacDesktopAppShell": 4,
                      "zlt": 15, "viperex": 1}, dict(grouped))
    check("canonical original identity keys distinct",
          len({(r["original_sha256"], r["address"]) for r in canonical}) == len(canonical)
          and all(r["scope"] == "original artifact" for r in canonical))
    check("public desktop counts match canonical",
          qa["desktop_native_function_counts"]["original_main_unique_function_dossiers"] == 61
          and qa["desktop_native_function_counts"]["original_shell_unique_function_dossiers"] == 4
          and qa["desktop_native_function_counts"]["desktop_media_excluded"] == 16)
    mobile = private / "mobile-original"
    baseline = read_json(mobile / "android-method-evidence-index.json")
    added = read_json(mobile / "private/three-new-java-method-index.json")
    native = read_json(mobile / "private/original-native-function-index.json")
    scope_counts = Counter(r["scope"] for r in baseline)
    check("mobile30 bodies+2 declarations, three additions",
          scope_counts["decompiled_method_body"] == 30 and len(baseline) == 32
          and len(added) == 3 and qa["mobile_java_method_bodies"] == 33
          and qa["mobile_declarations_excluded"] == 2, dict(scope_counts))
    check("mobile12 original ELF identities and byte matches",
          len(native) == 12 and len({r["dedup_key"] for r in native}) == 12
          and all(r["entry16_match"] for r in native)
          and qa["mobile_native_original_elf_function_dossiers"] == 12)
    exports = [
        ("mobile_complete_export_sha256", mobile / "rea-android-complete-evidence-final-20261013.json", 56),
        ("mobile_native_supplement_export_sha256", mobile / "private/rea-native-original-complete-final.json", 36),
        ("mobile_java_gmv_supplement_export_sha256", mobile / "private/rea-java-gmv-three-complete.json", 9),
    ]
    for key, path, count in exports:
        check(key, qa.get(key) == digest(path)
              and len(read_json(path)["records"]) == count, {"expected_records": count})
    check("baseline export scope explicit", "Initial" in qa.get("mobile_complete_export_scope", ""))
    w2 = private / "engine/w2-upstream-followup"
    ledger = read_json(w2 / "w2-upstream-findings-ledger-private.json")
    probe = read_json(w2 / "selected-w2-synthetic-probe-private.json")
    check("W2 thirteen derived anchors add zero original dossiers",
          len(ledger["selected_derived_anchor_records"]) == 13
          and ledger["additional_full_original_function_count"] == 0
          and qa["desktop_native_function_counts"]["additional_full_original_main_dossiers_from_supplement"] == 0)
    check("seven synthetic partial probes, no original runtime",
          len(probe["fixtures"]) == 7 and all(f["pass"] for f in probe["fixtures"])
          and ledger["original_runtime_probe_count"] == 0
          and qa["vendor_runtime_comparisons"] == 0)
    w2qa = qa["w2_aggregation_probe"]
    check("marker branch preconditions explicit",
          w2qa.get("fixture_branch_preconditions_supplied") is True
          and w2qa.get("complete_hasvalue_fs2_marker_predicates_executed") is False)
    check("local subtotal not treated as final1040",
          w2qa["candidate"]["local_legacy_subtotal_usd"] == 2000
          and w2qa["candidate"]["current_independent_app_subtotal_usd"] == 2001
          and w2qa["original_final_1040_result_verified"] is False
          and w2qa["final_legacy_to_tke_binding_verified"] is False
          and w2qa["federal_rules_or_frozen_oracles_changed"] is False)
    check("tax core digest remains recorded", digest(public / "tax_engine.py")
          == qa["validation"]["federal_core_sha256"])

    # Exact-byte checks plus high-confidence raw-decompiler markers. A public
    # summary mentioning a symbol or original SHA does not trigger this check.
    forbidden_hashes = {r["original_sha256"] for r in canonical}
    forbidden_hashes.add(qa["mobile_apk_sha256"])
    member_rows = read_json(mobile / "zip-member-digest-inventory.json")["selected"]
    forbidden_hashes.update(r["sha256"] for r in member_rows)
    forbidden_hashes.update(r["derived_subject_sha256"] for r in ledger["selected_derived_anchor_records"])
    if args.original_bytes_root:
        files = [p for p in args.original_bytes_root.rglob("*") if p.is_file() and not p.is_symlink()]
        public_sizes = {p.stat().st_size for p in public.rglob("*") if p.is_file() and not p.is_symlink()}
        # This bounded target tree holds originals, unlike sibling app-build
        # and CI screenshot mirrors. No image is displayed or interpreted.
        forbidden_hashes.update(digest(p) for p in files if p.stat().st_size in public_sizes)
    markers = ["JADX " + "INFO:", "WARNING: Removing " + "unreachable block",
               "/* WARNING: Subroutine does " + "not return */"]
    text_extensions = {".java", ".c", ".cpp", ".txt", ".json", ".py", ".js", ".ts", ".md"}
    findings = []
    archives = []
    checked_files = 0
    for path in public.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        checked_files += 1
        relative = str(path.relative_to(public))
        if digest(path) in forbidden_hashes:
            findings.append({"path": relative, "reason": "exact original/derived vendor byte digest"})
        if path.suffix.lower() in text_extensions:
            if file_contains_any(path, markers):
                findings.append({"path": relative, "reason": "raw decompiler marker"})
        if path.suffix.lower() in {".apk", ".zip"} or (args.source_zip and path.resolve() == args.source_zip.resolve()):
            archives.append(path)
    if args.source_zip and args.source_zip.resolve() not in {p.resolve() for p in archives}:
        archives.append(args.source_zip)
    archive_members = 0
    for path in archives:
        if not zipfile.is_zipfile(path):
            findings.append({"path": str(path), "reason": "requested ZIP/APK is not ZIP"})
            continue
        with zipfile.ZipFile(path) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                archive_members += 1
                if entry.file_size > 200 * 1024 * 1024:
                    continue
                payload = archive.read(entry)
                if hashlib.sha256(payload).hexdigest() in forbidden_hashes:
                    findings.append({"path": str(path), "member": entry.filename,
                                     "reason": "exact original/derived vendor bytes in archive"})
                if Path(entry.filename).suffix.lower() in text_extensions:
                    text = payload.decode("utf-8", errors="replace")
                    if any(marker in text for marker in markers):
                        findings.append({"path": str(path), "member": entry.filename,
                                         "reason": "raw decompiler marker in archive"})
    check("no known original bytes/raw decompiler text in inspected tree and ZIP/APK",
          not findings, findings)
    reviewed = ["docs/REA_NATIVE_PROGRESS_20261013.md", "docs/REA_W2_AGGREGATION_20261013.md",
                "docs/REA_W2_NATIVE_20261013.md", "docs/REA_ANDROID_STATIC_20261013.md",
                "qa/rea-reconstruction-batch-20261013.json"]
    result = {"scope": "Recorded20261013 counts; exact-byte and text marker scan. No vendor execution.",
              "reviewed_document_sha256": {name: digest(public / name) for name in reviewed},
              "public_files_checked": checked_files, "archive_members_checked": archive_members,
              "checks": checks, "all_pass": all(c["passed"] for c in checks),
              "limitations": ["DMG contents not mounted; inspect built app source/resources separately.",
                              "Renamed or transformed photographs require an independent origin check.",
                              "This is not a general secret/credential scanner.",
                              "No claim of original final tax equivalence or OCR accuracy."]}
    print(json.dumps(result, indent=2))
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
