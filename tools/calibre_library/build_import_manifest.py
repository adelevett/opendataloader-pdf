from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _bootstrap_repo_imports() -> Path:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[2]
    package_src = repo_root / "python" / "opendataloader-pdf" / "src"
    for candidate in (repo_root, package_src):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
    return repo_root


REPO_ROOT = _bootstrap_repo_imports()

from tools.calibre_library.io import load_jsonl, write_json, write_jsonl
from tools.calibre_library.paths import calibre_artifacts_dir, calibre_work_dir, ensure_calibre_dirs


PRIMARY_PDF_CLASSES = {
    "isbn_named",
    "full_pdf_candidate",
}

COMPONENT_LIKE_NAME_RE = re.compile(
    r"(?i)(^|[\s_.-])("
    r"front|fm|toc|contents|index|idx|ndx|gidx|cind|glossary|glo|answer|answers|ans|solution|"
    r"appendix|app\d*|chapter|ch\d*|ch[\s_.-]*\d+|part|unit|section|lesson|"
    r"bibliography|references?|credits?|cre|cover|preface|foreword|artistlist|infosources|insert"
    r")($|[\s_.-])"
)

STANDALONE_PDF_NAME_RE = re.compile(
    r"(?i)(^|[\s_.-])(textbook|full|complete|combined|entire|whole|single|ebook)($|[\s_.-])"
)

FIXED_ZIP_DATETIME = (1980, 1, 1, 0, 0, 0)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic Calibre import manifests and optional component ZIPs."
    )
    parser.add_argument(
        "--curated-jsonl",
        type=Path,
        default=calibre_work_dir() / "curated_books.jsonl",
        help="Auto-curated book records produced by build_review_reports.py",
    )
    parser.add_argument(
        "--book-groups-jsonl",
        type=Path,
        default=calibre_work_dir() / "book_groups.jsonl",
        help="Grouped inventory JSONL produced by classify_inventory.py",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=calibre_work_dir(),
        help="Ignored repo-local workspace for JSONL manifests",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=calibre_artifacts_dir(),
        help="Ignored repo-local workspace for human-readable artifacts",
    )
    parser.add_argument(
        "--build-zips",
        action="store_true",
        help="Create component ZIP files while building the import manifest",
    )
    parser.add_argument(
        "--force-zips",
        action="store_true",
        help="Rebuild component ZIPs even when an archive already exists",
    )
    parser.add_argument(
        "--zip-compression",
        choices=["stored", "deflated"],
        default="stored",
        help="ZIP compression method; stored is faster and deterministic for already-compressed PDFs",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum curated records to process; 0 means all",
    )
    return parser.parse_args(argv)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _metadata_status(work_dir: Path, isbn: str) -> dict[str, Any]:
    status_path = work_dir / "metadata_cache" / "isbn" / isbn / "fetch_status.json"
    if not status_path.exists():
        return {
            "status": "not_attempted",
            "opf_path": None,
            "status_path": str(status_path),
        }
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "status": "provider_error",
            "opf_path": None,
            "status_path": str(status_path),
            "error": "fetch_status.json is not valid JSON",
        }
    return {
        "status": status.get("status") or "unknown",
        "opf_path": status.get("opf_path"),
        "status_path": str(status_path),
        "opf_summary": status.get("opf_summary") or {},
    }


def _source_entries(group: dict[str, Any]) -> list[dict[str, Any]]:
    paths = [str(path) for path in group.get("active_source_paths", [])]
    classes = [str(value) for value in group.get("active_file_classes", [])]
    names = [str(value) for value in group.get("active_file_names", [])]

    entries: list[dict[str, Any]] = []
    for index, source_path in enumerate(paths):
        path = Path(source_path)
        exists = path.exists()
        stat = path.stat() if exists else None
        file_name = names[index] if index < len(names) else path.name
        file_class = classes[index] if index < len(classes) else ""
        entries.append(
            {
                "index": index,
                "source_path": source_path,
                "file_name": file_name,
                "file_class": file_class,
                "extension": path.suffix.lower(),
                "exists": exists,
                "size_bytes": stat.st_size if stat else None,
                "mtime_utc": datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=timezone.utc,
                ).isoformat()
                if stat
                else None,
            }
        )
    return entries


def _is_component_like(entry: dict[str, Any], *, active_count: int) -> bool:
    if active_count <= 1:
        return False
    file_class = str(entry.get("file_class") or "")
    if file_class not in PRIMARY_PDF_CLASSES:
        return True
    file_name = str(entry.get("file_name") or "")
    stem = Path(file_name).stem
    return bool(COMPONENT_LIKE_NAME_RE.search(stem))


def _choose_primary_entry(group: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    existing = [entry for entry in entries if entry.get("exists")]
    if not existing:
        return None
    if len(existing) == 1:
        return existing[0]

    single_file_like = str(group.get("group_type") or "") == "single_file_book"
    if single_file_like:
        pdfs = [entry for entry in existing if entry.get("extension") == ".pdf"]
        if pdfs:
            return sorted(
                pdfs,
                key=lambda entry: (
                    0 if entry["source_path"] == str(group.get("primary_source_path") or "") else 1,
                    -int(entry.get("size_bytes") or 0),
                    str(entry.get("source_path") or ""),
                ),
            )[0]
        return sorted(existing, key=lambda entry: str(entry.get("source_path") or ""))[0]

    primary_path = str(group.get("primary_source_path") or "")
    preferred = [
        entry
        for entry in existing
        if entry.get("extension") == ".pdf"
        and entry.get("file_class") in PRIMARY_PDF_CLASSES
        and not _is_component_like(entry, active_count=len(existing))
        and STANDALONE_PDF_NAME_RE.search(str(entry.get("file_name") or ""))
    ]
    if preferred:
        return sorted(
            preferred,
            key=lambda entry: (
                0 if entry["source_path"] == primary_path else 1,
                -int(entry.get("size_bytes") or 0),
                str(entry.get("source_path") or ""),
            ),
        )[0]

    return None


def _safe_zip_leaf(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return cleaned or "book"


def _component_zip_path(zip_dir: Path, group_id: str, isbn: str, title_guess: str) -> Path:
    name = f"{group_id}_{isbn}_{_safe_zip_leaf(title_guess)[:80]}.zip"
    return zip_dir / name


def _arcname_for_entry(entry: dict[str, Any], used: set[str]) -> str:
    file_name = Path(str(entry.get("file_name") or entry.get("source_path") or "component")).name
    arcname = f"files/{file_name}"
    if arcname not in used:
        used.add(arcname)
        return arcname
    index = int(entry.get("index") or 0)
    stem = Path(file_name).stem
    suffix = Path(file_name).suffix
    arcname = f"files/{index:04d}_{stem}{suffix}"
    used.add(arcname)
    return arcname


def _zip_method(name: str) -> int:
    return zipfile.ZIP_DEFLATED if name == "deflated" else zipfile.ZIP_STORED


def _add_bytes_to_zip(zip_handle: zipfile.ZipFile, arcname: str, payload: bytes, method: int) -> None:
    info = zipfile.ZipInfo(arcname, FIXED_ZIP_DATETIME)
    info.compress_type = method
    info.external_attr = 0o644 << 16
    zip_handle.writestr(info, payload)


def _add_file_to_zip(zip_handle: zipfile.ZipFile, source_path: Path, arcname: str, method: int) -> None:
    info = zipfile.ZipInfo(arcname, FIXED_ZIP_DATETIME)
    info.compress_type = method
    info.external_attr = 0o644 << 16
    with source_path.open("rb") as source, zip_handle.open(info, "w") as target:
        shutil.copyfileobj(source, target, length=1024 * 1024)


def _write_component_zip(
    *,
    zip_path: Path,
    source_manifest: dict[str, Any],
    source_manifest_bytes: bytes,
    component_entries: list[dict[str, Any]],
    compression: str,
    force: bool,
) -> None:
    if zip_path.exists() and not force:
        return
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    method = _zip_method(compression)
    used: set[str] = set()
    temp_path = zip_path.with_suffix(".zip.tmp")
    if temp_path.exists():
        temp_path.unlink()
    with zipfile.ZipFile(temp_path, "w") as zip_handle:
        _add_bytes_to_zip(zip_handle, "source_manifest.json", source_manifest_bytes, method)
        used.add("source_manifest.json")
        for entry in component_entries:
            if not entry.get("exists"):
                continue
            source_path = Path(str(entry["source_path"]))
            arcname = _arcname_for_entry(entry, used)
            _add_file_to_zip(zip_handle, source_path, arcname, method)
    if zip_path.exists():
        zip_path.unlink()
    temp_path.replace(zip_path)


def _source_manifest_path(manifest_dir: Path, group_id: str) -> Path:
    return manifest_dir / f"{group_id}.source_manifest.json"


def _build_import_record(
    *,
    curated: dict[str, Any],
    group: dict[str, Any],
    work_dir: Path,
    build_zips: bool,
    force_zips: bool,
    zip_compression: str,
) -> dict[str, Any]:
    group_id = str(curated.get("group_id") or "")
    isbn = str(curated.get("canonical_isbn") or curated.get("isbn") or "").strip()
    title_guess = str(curated.get("title_guess") or group.get("parent_title_key") or group.get("parent_dir") or "")
    entries = _source_entries(group)
    existing_entries = [entry for entry in entries if entry.get("exists")]
    missing_entries = [entry for entry in entries if not entry.get("exists")]
    primary_entry = _choose_primary_entry(group, entries)
    primary_path = str(primary_entry["source_path"]) if primary_entry else None
    component_entries = [
        entry
        for entry in entries
        if entry.get("exists") and (not primary_path or entry.get("source_path") != primary_path)
    ]

    metadata = _metadata_status(work_dir, isbn)
    manifest_dir = work_dir / "source_manifests"
    zip_dir = work_dir / "component_zips"
    source_manifest_path = _source_manifest_path(manifest_dir, group_id)
    component_zip_path = (
        _component_zip_path(zip_dir, group_id, isbn or "no_isbn", title_guess)
        if component_entries or not primary_path
        else None
    )

    zip_component_entries = component_entries if primary_path else existing_entries
    source_manifest = {
        "generated_utc": _utc_now(),
        "group_id": group_id,
        "parent_dir": curated.get("parent_dir"),
        "title_guess": title_guess,
        "canonical_isbn": isbn,
        "metadata_status": metadata.get("status"),
        "primary_source_path": primary_path,
        "component_zip_path": str(component_zip_path) if component_zip_path else None,
        "sources": entries,
        "component_sources": zip_component_entries,
        "missing_sources": missing_entries,
    }
    source_manifest_bytes = _json_bytes(source_manifest)
    source_manifest_hash = _sha256_bytes(source_manifest_bytes)
    source_manifest["source_manifest_hash"] = source_manifest_hash
    manifest_dir.mkdir(parents=True, exist_ok=True)
    source_manifest_path.write_bytes(_json_bytes(source_manifest))

    zip_exists = False
    zip_size_bytes = None
    if component_zip_path and build_zips and zip_component_entries:
        _write_component_zip(
            zip_path=component_zip_path,
            source_manifest=source_manifest,
            source_manifest_bytes=_json_bytes(source_manifest),
            component_entries=zip_component_entries,
            compression=zip_compression,
            force=force_zips,
        )
    if component_zip_path and component_zip_path.exists():
        zip_exists = True
        zip_size_bytes = component_zip_path.stat().st_size

    review_flags: list[str] = []
    if missing_entries:
        review_flags.append("missing_source_files")
    if metadata.get("status") != "success":
        review_flags.append(f"metadata_{metadata.get('status')}")

    primary_format_path = primary_path
    primary_format_kind = None
    if primary_entry:
        extension = str(primary_entry.get("extension") or "").lstrip(".")
        primary_format_kind = extension or "file"
    extra_data_files: list[str] = []
    if primary_path and component_zip_path:
        if zip_exists or not build_zips:
            extra_data_files.append(str(component_zip_path))
        if build_zips and not zip_exists:
            review_flags.append("component_zip_not_created")
    elif not primary_path and component_zip_path:
        if zip_exists or not build_zips:
            primary_format_path = str(component_zip_path)
            primary_format_kind = "component_zip"
        if build_zips and not zip_exists:
            review_flags.append("component_zip_not_created")

    if primary_format_path:
        if primary_format_kind == "component_zip":
            import_action = "add_component_zip_as_primary"
        elif primary_format_kind == "pdf":
            import_action = "add_primary_pdf"
        else:
            import_action = "add_primary_file"
    else:
        import_action = "manual_review_required"
        review_flags.append("no_importable_primary_or_zip")

    return {
        "group_id": group_id,
        "title_guess": title_guess,
        "author_guess": None,
        "best_isbn": curated.get("isbn"),
        "canonical_isbn": isbn,
        "metadata_status": metadata.get("status"),
        "metadata_opf_path": metadata.get("opf_path") if metadata.get("status") == "success" else None,
        "metadata_status_path": metadata.get("status_path"),
        "primary_format_path": primary_format_path,
        "primary_format_kind": primary_format_kind,
        "extra_data_files": extra_data_files,
        "source_manifest_path": str(source_manifest_path),
        "source_manifest_hash": source_manifest_hash,
        "component_zip_path": str(component_zip_path) if component_zip_path else None,
        "component_zip_exists": zip_exists,
        "component_zip_size_bytes": zip_size_bytes,
        "component_source_count": len(zip_component_entries),
        "active_source_count": len(entries),
        "missing_source_count": len(missing_entries),
        "custom_columns": {
            "#source_paths": [entry["source_path"] for entry in entries],
            "#inventory_group_id": group_id,
            "#best_isbn_source": curated.get("isbn_source_kind"),
            "#import_confidence": curated.get("isbn_confidence"),
            "#review_flags": review_flags,
            "#duplicate_policy": curated.get("duplicate_policy"),
            "#source_manifest_hash": source_manifest_hash,
        },
        "import_action": import_action,
        "confidence": curated.get("isbn_confidence"),
        "review_flags": review_flags,
        "calibre_plan": {
            "add": primary_format_path,
            "set_metadata": metadata.get("opf_path") if metadata.get("status") == "success" else None,
            "add_extra_data": extra_data_files,
        },
    }


def _render_summary_md(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    lines = [
        "# Calibre Import Manifest Summary",
        "",
        f"- generated_utc: {manifest['generated_utc']}",
        f"- curated_jsonl: {manifest['curated_jsonl']}",
        f"- book_groups_jsonl: {manifest['book_groups_jsonl']}",
        f"- build_zips: {manifest['build_zips']}",
        f"- zip_compression: {manifest['zip_compression']}",
        "",
        "## Counts",
        f"- curated_records: {summary['curated_records']}",
        f"- import_manifest_records: {summary['import_manifest_records']}",
        f"- importable_records: {summary['importable_records']}",
        f"- manual_review_required: {summary['manual_review_required']}",
        f"- records_with_primary_pdf: {summary['records_with_primary_pdf']}",
        f"- records_with_primary_zip: {summary['records_with_primary_zip']}",
        f"- records_with_extra_data_zip: {summary['records_with_extra_data_zip']}",
        f"- component_zips_existing: {summary['component_zips_existing']}",
        f"- missing_source_records: {summary['missing_source_records']}",
        "",
        "## Import Actions",
    ]
    for name, count in sorted(summary["import_action_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Metadata Statuses"])
    for name, count in sorted(summary["metadata_status_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Review Flags"])
    for name, count in sorted(summary["review_flag_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    samples = manifest.get("sample_records", [])
    if samples:
        lines.extend(["", "## Sample Records"])
        for row in samples:
            lines.append(
                f"- {row['group_id']} | {row['import_action']} | "
                f"{row.get('canonical_isbn') or ''} | {row.get('primary_format_kind') or ''} | "
                f"extras={len(row.get('extra_data_files', []))} | {row['title_guess']}"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.curated_jsonl.exists():
        raise FileNotFoundError(f"Curated books JSONL not found: {args.curated_jsonl}")
    if not args.book_groups_jsonl.exists():
        raise FileNotFoundError(f"Book groups JSONL not found: {args.book_groups_jsonl}")

    work_dir, artifact_dir = ensure_calibre_dirs(args.work_dir, args.artifact_dir)
    curated_rows = load_jsonl(args.curated_jsonl)
    if args.limit:
        curated_rows = curated_rows[: args.limit]
    groups = load_jsonl(args.book_groups_jsonl)
    groups_by_id = {str(group.get("group_id") or ""): group for group in groups}

    import_records: list[dict[str, Any]] = []
    for curated in curated_rows:
        group_id = str(curated.get("group_id") or "")
        group = groups_by_id.get(group_id)
        if not group:
            continue
        import_records.append(
            _build_import_record(
                curated=curated,
                group=group,
                work_dir=work_dir,
                build_zips=args.build_zips,
                force_zips=args.force_zips,
                zip_compression=args.zip_compression,
            )
        )

    import_action_counts = Counter(str(row.get("import_action") or "unknown") for row in import_records)
    metadata_status_counts = Counter(str(row.get("metadata_status") or "unknown") for row in import_records)
    review_flag_counts: Counter[str] = Counter()
    for row in import_records:
        review_flag_counts.update(row.get("review_flags", []))

    manifest = {
        "generated_utc": _utc_now(),
        "repo_root": str(REPO_ROOT),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "command": list(sys.argv if argv is None else [sys.argv[0], *argv]),
        "curated_jsonl": str(args.curated_jsonl),
        "book_groups_jsonl": str(args.book_groups_jsonl),
        "build_zips": args.build_zips,
        "zip_compression": args.zip_compression,
        "summary": {
            "curated_records": len(curated_rows),
            "import_manifest_records": len(import_records),
            "importable_records": sum(1 for row in import_records if row.get("primary_format_path")),
            "manual_review_required": sum(
                1 for row in import_records if row.get("import_action") == "manual_review_required"
            ),
            "records_with_primary_pdf": sum(
                1 for row in import_records if row.get("primary_format_kind") == "pdf"
            ),
            "records_with_primary_zip": sum(
                1 for row in import_records if row.get("primary_format_kind") == "component_zip"
            ),
            "records_with_extra_data_zip": sum(1 for row in import_records if row.get("extra_data_files")),
            "component_zips_existing": sum(1 for row in import_records if row.get("component_zip_exists")),
            "missing_source_records": sum(1 for row in import_records if row.get("missing_source_count")),
            "import_action_counts": dict(import_action_counts),
            "metadata_status_counts": dict(metadata_status_counts),
            "review_flag_counts": dict(review_flag_counts),
        },
        "sample_records": import_records[:25],
    }

    write_jsonl(work_dir / "import_manifest.jsonl", import_records)
    write_json(work_dir / "import_manifest_summary.json", manifest)
    write_json(artifact_dir / "import_manifest_summary.json", manifest)
    (artifact_dir / "import_manifest_summary.md").write_text(
        _render_summary_md(manifest),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "records": len(import_records),
                "importable": manifest["summary"]["importable_records"],
                "primary_pdf": manifest["summary"]["records_with_primary_pdf"],
                "primary_zip": manifest["summary"]["records_with_primary_zip"],
                "extra_data_zip": manifest["summary"]["records_with_extra_data_zip"],
                "component_zips_existing": manifest["summary"]["component_zips_existing"],
                "work_dir": str(work_dir),
                "artifact_dir": str(artifact_dir),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
