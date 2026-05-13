from __future__ import annotations

import argparse
import json
import platform
import sys
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

from tools.calibre_library.inventory import classify_inventory_manifest
from tools.calibre_library.io import sha256_file, write_json, write_jsonl
from tools.calibre_library.paths import (
    calibre_artifacts_dir,
    calibre_work_dir,
    default_inventory_path,
    ensure_calibre_dirs,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify the source inventory into Calibre import groups."
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=default_inventory_path(),
        help="Path to chapter_inventory.json",
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
        "--check-source-exists",
        action="store_true",
        help="Check whether each source file exists on disk during normalization",
    )
    return parser.parse_args(argv)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _inventory_metadata(inventory_path: Path) -> dict[str, Any]:
    stat = inventory_path.stat()
    return {
        "path": str(inventory_path),
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "sha256": sha256_file(inventory_path),
    }


def _render_summary_md(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    class_counts = Counter(summary.get("file_class_counts", {}))
    group_type_counts = Counter(summary.get("group_type_counts", {}))
    review_required = manifest.get("review_required_groups", [])
    duplicates = manifest.get("duplicate_candidates", [])

    lines: list[str] = [
        "# Calibre Inventory Classification Summary",
        "",
        f"- generated_utc: {manifest['generated_utc']}",
        f"- inventory_path: {manifest['inventory']['path']}",
        f"- inventory_sha256: {manifest['inventory']['sha256']}",
        f"- total_rows: {summary['total_rows']}",
        f"- active_rows: {summary['active_rows']}",
        f"- artifact_rows: {summary['artifact_rows']}",
        f"- group_count: {summary['group_count']}",
        f"- review_required_groups: {summary['review_required_groups']}",
        f"- nested_duplicate_groups: {summary['nested_duplicate_groups']}",
        f"- duplicate_cluster_count: {summary['duplicate_cluster_count']}",
        "",
        "## File Classes",
    ]
    for name, count in sorted(class_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Group Types"])
    for name, count in sorted(group_type_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Review Required Groups"])
    for record in review_required[:20]:
        lines.append(
            f"- {record['group_id']} | {record['group_type']} | {record['parent_dir']} | "
            f"{record['primary_source_path']}"
        )
    if len(review_required) > 20:
        lines.append(f"- ... {len(review_required) - 20} more")

    lines.extend(["", "## Duplicate Clusters"])
    for record in duplicates[:20]:
        lines.append(
            f"- {record['duplicate_key']} | groups={record['group_count']} | "
            f"nested={record['nested_duplicate_count']}"
        )
    if len(duplicates) > 20:
        lines.append(f"- ... {len(duplicates) - 20} more")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    inventory_path = args.inventory
    if not inventory_path.exists():
        raise FileNotFoundError(f"Inventory JSON not found: {inventory_path}")

    work_dir, artifact_dir = ensure_calibre_dirs(args.work_dir, args.artifact_dir)
    manifest = classify_inventory_manifest(
        inventory_path,
        check_source_exists=args.check_source_exists,
    )

    rows = manifest["rows"]
    group_records = manifest["group_records"]
    duplicate_candidates = manifest["duplicate_candidates"]
    summary = manifest["summary"]

    run_manifest = {
        "generated_utc": _utc_now(),
        "repo_root": str(REPO_ROOT),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "command": list(sys.argv if argv is None else [sys.argv[0], *argv]),
        "inventory": _inventory_metadata(inventory_path),
        "summary": summary,
    }

    write_jsonl(work_dir / "inventory_normalized.jsonl", rows)
    write_jsonl(work_dir / "book_groups.jsonl", group_records)
    write_jsonl(work_dir / "duplicate_candidates.jsonl", duplicate_candidates)
    write_json(work_dir / "inventory_manifest.json", run_manifest)
    write_json(artifact_dir / "inventory_summary.json", run_manifest)
    artifact_payload = {
        **run_manifest,
        **manifest,
        "review_required_groups": [group for group in group_records if group.get("review_required")],
    }
    (artifact_dir / "inventory_summary.md").write_text(
        _render_summary_md(artifact_payload),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "inventory": str(inventory_path),
                "groups": summary["group_count"],
                "rows": summary["total_rows"],
                "review_required": summary["review_required_groups"],
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
