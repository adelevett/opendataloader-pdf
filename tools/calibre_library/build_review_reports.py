from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from collections import Counter, defaultdict
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


RESOLVED_STATUSES = {"path_resolved", "text_resolved", "hybrid_resolved"}
FAILURE_ATTEMPT_STATUSES = {"error", "timeout"}

REASON_PRIORITY = {
    "extraction_error": 0,
    "extraction_timeout": 0,
    "isbn_conflict": 1,
    "isbn_duplicate_candidate": 2,
    "title_duplicate_candidate": 3,
    "nested_duplicate_candidate": 3,
    "isbn_unresolved": 4,
    "structural_review_required": 5,
}

REVIEW_ACTIONS = {
    "extraction_error": "inspect failed PDF or extractor runtime before relying on this group",
    "extraction_timeout": "retry with longer timeout or isolate the failing source path",
    "isbn_conflict": "choose the correct canonical ISBN or split the group into separate books",
    "isbn_duplicate_candidate": "deduplicate same-ISBN groups before import",
    "title_duplicate_candidate": "deduplicate same-title groups before import",
    "nested_duplicate_candidate": "collapse only if nested files are true duplicates",
    "isbn_unresolved": "escalate scan or keep as no-ISBN manual record",
    "structural_review_required": "confirm grouping, primary file, and component policy",
}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 4 Calibre curation and review reports from the ISBN audit."
    )
    parser.add_argument(
        "--isbn-audit-jsonl",
        type=Path,
        default=calibre_work_dir() / "isbn_audit_groups.jsonl",
        help="Group-level ISBN audit JSONL produced by audit_isbn.py",
    )
    parser.add_argument(
        "--book-groups-jsonl",
        type=Path,
        default=calibre_work_dir() / "book_groups.jsonl",
        help="Grouped inventory JSONL produced by classify_inventory.py",
    )
    parser.add_argument(
        "--title-duplicate-jsonl",
        type=Path,
        default=calibre_work_dir() / "duplicate_candidates.jsonl",
        help="Title-key duplicate candidate JSONL produced by classify_inventory.py",
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
    return parser.parse_args(argv)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_optional_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return load_jsonl(path)


def _failed_attempts(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        attempt
        for attempt in record.get("scan_attempts", [])
        if str(attempt.get("status") or "") in FAILURE_ATTEMPT_STATUSES
    ]


def _title_guess(group: dict[str, Any] | None, audit: dict[str, Any]) -> str:
    if group:
        return str(group.get("parent_title_key") or group.get("parent_dir") or "")
    return str(audit.get("parent_dir") or "")


def _cluster_key(prefix: str, value: str) -> str:
    return f"{prefix}:{value}"


def _build_title_duplicate_index(
    duplicate_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    clusters: list[dict[str, Any]] = []
    by_group: dict[str, list[str]] = defaultdict(list)
    for record in duplicate_records:
        duplicate_key = str(record.get("duplicate_key") or "").strip()
        if not duplicate_key:
            continue
        cluster_id = _cluster_key("title", duplicate_key)
        group_ids = [str(group_id) for group_id in record.get("group_ids", []) if group_id]
        cluster = {
            "cluster_id": cluster_id,
            "cluster_type": "title_key",
            "duplicate_key": duplicate_key,
            "group_count": int(record.get("group_count") or len(group_ids)),
            "group_ids": group_ids,
            "parent_dirs": record.get("parent_dirs", []),
            "primary_paths": record.get("primary_paths", []),
            "nested_duplicate_count": int(record.get("nested_duplicate_count") or 0),
            "review_reason": "title_duplicate_candidate",
        }
        clusters.append(cluster)
        for group_id in group_ids:
            by_group[group_id].append(cluster_id)
    return clusters, by_group


def _build_isbn_duplicate_index(
    audit_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    by_isbn: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in audit_records:
        canonical = str(record.get("best_canonical_isbn") or record.get("best_isbn") or "").strip()
        if canonical:
            by_isbn[canonical].append(record)

    clusters: list[dict[str, Any]] = []
    by_group: dict[str, list[str]] = defaultdict(list)
    for isbn, records in sorted(by_isbn.items()):
        if len(records) < 2:
            continue
        cluster_id = _cluster_key("isbn", isbn)
        group_ids = [str(record.get("group_id") or "") for record in records]
        cluster = {
            "cluster_id": cluster_id,
            "cluster_type": "isbn",
            "duplicate_key": isbn,
            "group_count": len(records),
            "group_ids": group_ids,
            "statuses": [record.get("status") for record in records],
            "parent_dirs": [record.get("parent_dir") for record in records],
            "primary_paths": [record.get("primary_source_path") for record in records],
            "conflict_count": sum(1 for record in records if record.get("status") == "conflict"),
            "resolved_count": sum(1 for record in records if record.get("status") in RESOLVED_STATUSES),
            "review_reason": "isbn_duplicate_candidate",
        }
        clusters.append(cluster)
        for group_id in group_ids:
            if group_id:
                by_group[group_id].append(cluster_id)
    return clusters, by_group


def _review_reasons(
    audit: dict[str, Any],
    group: dict[str, Any] | None,
    isbn_duplicate_clusters: list[str],
    title_duplicate_clusters: list[str],
) -> list[str]:
    reasons: set[str] = set()
    status = str(audit.get("status") or "")

    for attempt in _failed_attempts(audit):
        attempt_status = str(attempt.get("status") or "")
        if attempt_status == "timeout":
            reasons.add("extraction_timeout")
        else:
            reasons.add("extraction_error")

    if status == "conflict":
        reasons.add("isbn_conflict")
    elif status == "unresolved":
        reasons.add("isbn_unresolved")

    if isbn_duplicate_clusters:
        reasons.add("isbn_duplicate_candidate")
    if title_duplicate_clusters:
        reasons.add("title_duplicate_candidate")

    if group:
        if group.get("nested_duplicate_candidate"):
            reasons.add("nested_duplicate_candidate")
        if group.get("review_required"):
            reasons.add("structural_review_required")

    return sorted(reasons, key=lambda item: (REASON_PRIORITY.get(item, 99), item))


def _priority_for_reasons(reasons: list[str]) -> int:
    if not reasons:
        return 99
    return min(REASON_PRIORITY.get(reason, 99) for reason in reasons)


def _review_id(group_id: str, reasons: list[str]) -> str:
    primary_reason = reasons[0] if reasons else "review"
    return f"{primary_reason}:{group_id}"


def _build_review_row(
    audit: dict[str, Any],
    group: dict[str, Any] | None,
    reasons: list[str],
    isbn_duplicate_clusters: list[str],
    title_duplicate_clusters: list[str],
) -> dict[str, Any]:
    group_id = str(audit.get("group_id") or "")
    failed_attempts = _failed_attempts(audit)
    return {
        "review_id": _review_id(group_id, reasons),
        "priority": _priority_for_reasons(reasons),
        "review_reasons": reasons,
        "recommended_actions": [REVIEW_ACTIONS[reason] for reason in reasons if reason in REVIEW_ACTIONS],
        "group_id": group_id,
        "status": audit.get("status"),
        "title_guess": _title_guess(group, audit),
        "parent_dir": audit.get("parent_dir"),
        "group_type": audit.get("group_type"),
        "confidence": group.get("confidence") if group else None,
        "best_isbn": audit.get("best_isbn"),
        "best_canonical_isbn": audit.get("best_canonical_isbn"),
        "best_confidence": audit.get("best_confidence"),
        "best_source_kind": audit.get("best_source_kind"),
        "best_source_label": audit.get("best_source_label"),
        "candidate_count": audit.get("candidate_count"),
        "candidate_isbns": audit.get("candidate_isbns", []),
        "primary_source_path": audit.get("primary_source_path"),
        "active_file_count": group.get("active_file_count") if group else None,
        "active_file_classes": group.get("active_file_classes", []) if group else [],
        "active_source_paths": group.get("active_source_paths", []) if group else [],
        "scan_targets": audit.get("scan_targets", []),
        "scan_target_classes": audit.get("scan_target_classes", []),
        "failed_attempt_count": len(failed_attempts),
        "failed_attempts": failed_attempts,
        "isbn_duplicate_clusters": isbn_duplicate_clusters,
        "title_duplicate_clusters": title_duplicate_clusters,
    }


def _build_curated_row(audit: dict[str, Any], group: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "group_id": audit.get("group_id"),
        "curation_status": "auto_curated",
        "title_guess": _title_guess(group, audit),
        "parent_dir": audit.get("parent_dir"),
        "group_type": audit.get("group_type"),
        "isbn": audit.get("best_isbn"),
        "canonical_isbn": audit.get("best_canonical_isbn"),
        "isbn_confidence": audit.get("best_confidence"),
        "isbn_source_kind": audit.get("best_source_kind"),
        "isbn_source_label": audit.get("best_source_label"),
        "primary_source_path": audit.get("primary_source_path"),
        "active_source_paths": group.get("active_source_paths", []) if group else [],
        "component_policy": "primary_plus_components",
        "duplicate_policy": "unique_candidate",
        "metadata_fetch_status": "not_attempted",
        "needs_metadata_fetch": True,
        "needs_manual_review": False,
    }


def _build_metadata_fetch_queue(
    audit_records: list[dict[str, Any]],
    review_reasons_by_group: dict[str, list[str]],
) -> list[dict[str, Any]]:
    by_isbn: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in audit_records:
        if row.get("status") not in RESOLVED_STATUSES:
            continue
        isbn = str(row.get("best_canonical_isbn") or row.get("best_isbn") or "").strip()
        if isbn:
            by_isbn[isbn].append(row)

    queue: list[dict[str, Any]] = []
    for isbn, rows in sorted(by_isbn.items()):
        blocked_rows = [
            row
            for row in rows
            if review_reasons_by_group.get(str(row.get("group_id") or ""))
        ]
        queue.append(
            {
                "canonical_isbn": isbn,
                "fetch_status": "not_attempted",
                "provider_order": ["calibre", "openlibrary", "googlebooks"],
                "group_count": len(rows),
                "group_ids": [str(row.get("group_id") or "") for row in rows],
                "parent_dirs": [row.get("parent_dir") for row in rows],
                "review_blocked_group_count": len(blocked_rows),
                "review_reasons_by_group": {
                    str(row.get("group_id") or ""): review_reasons_by_group.get(
                        str(row.get("group_id") or ""),
                        [],
                    )
                    for row in blocked_rows
                },
            }
        )
    return queue


def _csv_value(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _write_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "priority",
        "review_reasons",
        "group_id",
        "status",
        "best_isbn",
        "title_guess",
        "parent_dir",
        "group_type",
        "primary_source_path",
        "failed_attempt_count",
        "isbn_duplicate_clusters",
        "title_duplicate_clusters",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _csv_value(row.get(name)) for name in fieldnames})


def _render_summary_md(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    lines = [
        "# Calibre Phase 4 Review Summary",
        "",
        f"- generated_utc: {manifest['generated_utc']}",
        f"- isbn_audit_jsonl: {manifest['isbn_audit_jsonl']}",
        f"- book_groups_jsonl: {manifest['book_groups_jsonl']}",
        f"- title_duplicate_jsonl: {manifest['title_duplicate_jsonl']}",
        "",
        "## Counts",
        f"- audit_groups: {summary['audit_groups']}",
        f"- auto_curated_books: {summary['auto_curated_books']}",
        f"- review_queue_items: {summary['review_queue_items']}",
        f"- duplicate_candidate_clusters: {summary['duplicate_candidate_clusters']}",
        f"- metadata_fetch_queue_items: {summary['metadata_fetch_queue_items']}",
        "",
        "## Review Reasons",
    ]
    for name, count in sorted(summary["review_reason_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Audit Statuses"])
    for name, count in sorted(summary["audit_status_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Duplicate Cluster Types"])
    for name, count in sorted(summary["duplicate_cluster_type_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    review_rows = manifest.get("review_queue_sample", [])
    if review_rows:
        lines.extend(["", "## Top Review Items"])
        for row in review_rows:
            reasons = ", ".join(row.get("review_reasons", []))
            lines.append(
                f"- P{row['priority']} | {row['group_id']} | {row['status']} | "
                f"{row.get('best_isbn') or ''} | {reasons} | {row['parent_dir']}"
            )

    curated_rows = manifest.get("curated_books_sample", [])
    if curated_rows:
        lines.extend(["", "## Auto-Curated Sample"])
        for row in curated_rows:
            lines.append(
                f"- {row['group_id']} | {row['canonical_isbn']} | "
                f"{row['isbn_source_kind']} | {row['parent_dir']}"
            )

    return "\n".join(lines) + "\n"


def _sort_review_row(row: dict[str, Any]) -> tuple[int, str, str]:
    return (
        int(row.get("priority") or 99),
        str(row.get("status") or ""),
        str(row.get("parent_dir") or ""),
    )


def _sort_curated_row(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("title_guess") or ""), str(row.get("group_id") or ""))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.isbn_audit_jsonl.exists():
        raise FileNotFoundError(f"ISBN audit JSONL not found: {args.isbn_audit_jsonl}")
    if not args.book_groups_jsonl.exists():
        raise FileNotFoundError(f"Book groups JSONL not found: {args.book_groups_jsonl}")

    work_dir, artifact_dir = ensure_calibre_dirs(args.work_dir, args.artifact_dir)
    audit_records = load_jsonl(args.isbn_audit_jsonl)
    group_records = load_jsonl(args.book_groups_jsonl)
    title_duplicate_records = _load_optional_jsonl(args.title_duplicate_jsonl)

    groups_by_id = {str(record.get("group_id") or ""): record for record in group_records}
    title_clusters, title_duplicate_by_group = _build_title_duplicate_index(title_duplicate_records)
    isbn_clusters, isbn_duplicate_by_group = _build_isbn_duplicate_index(audit_records)
    duplicate_clusters = sorted(
        [*isbn_clusters, *title_clusters],
        key=lambda row: (str(row.get("cluster_type") or ""), str(row.get("duplicate_key") or "")),
    )

    review_queue: list[dict[str, Any]] = []
    curated_books: list[dict[str, Any]] = []
    review_reasons_by_group: dict[str, list[str]] = {}

    for audit in audit_records:
        group_id = str(audit.get("group_id") or "")
        group = groups_by_id.get(group_id)
        isbn_duplicate_clusters = isbn_duplicate_by_group.get(group_id, [])
        title_duplicate_clusters = title_duplicate_by_group.get(group_id, [])
        reasons = _review_reasons(audit, group, isbn_duplicate_clusters, title_duplicate_clusters)
        if reasons:
            review_reasons_by_group[group_id] = reasons

        if reasons:
            review_queue.append(
                _build_review_row(
                    audit,
                    group,
                    reasons,
                    isbn_duplicate_clusters,
                    title_duplicate_clusters,
                )
            )
        elif audit.get("status") in RESOLVED_STATUSES and audit.get("best_canonical_isbn"):
            curated_books.append(_build_curated_row(audit, group))
        else:
            fallback_reasons = ["structural_review_required"]
            review_reasons_by_group[group_id] = fallback_reasons
            review_queue.append(
                _build_review_row(audit, group, fallback_reasons, [], [])
            )

    review_queue.sort(key=_sort_review_row)
    curated_books.sort(key=_sort_curated_row)
    metadata_fetch_queue = _build_metadata_fetch_queue(audit_records, review_reasons_by_group)

    reason_counts: Counter[str] = Counter()
    for row in review_queue:
        reason_counts.update(row.get("review_reasons", []))

    audit_status_counts = Counter(str(record.get("status") or "unknown") for record in audit_records)
    duplicate_cluster_type_counts = Counter(
        str(record.get("cluster_type") or "unknown") for record in duplicate_clusters
    )

    manifest = {
        "generated_utc": _utc_now(),
        "repo_root": str(REPO_ROOT),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "command": list(sys.argv if argv is None else [sys.argv[0], *argv]),
        "isbn_audit_jsonl": str(args.isbn_audit_jsonl),
        "book_groups_jsonl": str(args.book_groups_jsonl),
        "title_duplicate_jsonl": str(args.title_duplicate_jsonl),
        "summary": {
            "audit_groups": len(audit_records),
            "book_groups": len(group_records),
            "auto_curated_books": len(curated_books),
            "review_queue_items": len(review_queue),
            "duplicate_candidate_clusters": len(duplicate_clusters),
            "metadata_fetch_queue_items": len(metadata_fetch_queue),
            "review_reason_counts": dict(reason_counts),
            "audit_status_counts": dict(audit_status_counts),
            "duplicate_cluster_type_counts": dict(duplicate_cluster_type_counts),
        },
        "review_queue_sample": review_queue[:25],
        "curated_books_sample": curated_books[:25],
        "duplicate_candidate_sample": duplicate_clusters[:25],
    }

    write_jsonl(work_dir / "review_queue.jsonl", review_queue)
    write_jsonl(work_dir / "curated_books.jsonl", curated_books)
    write_jsonl(work_dir / "curation_duplicate_candidates.jsonl", duplicate_clusters)
    write_jsonl(work_dir / "metadata_fetch_queue.jsonl", metadata_fetch_queue)
    write_json(work_dir / "curation_manifest.json", manifest)
    write_json(artifact_dir / "curation_summary.json", manifest)
    (artifact_dir / "curation_summary.md").write_text(
        _render_summary_md(manifest),
        encoding="utf-8",
    )
    _write_review_csv(artifact_dir / "manual_review_queue.csv", review_queue)

    print(
        json.dumps(
            {
                "auto_curated": len(curated_books),
                "review_queue": len(review_queue),
                "duplicate_clusters": len(duplicate_clusters),
                "metadata_fetch_queue": len(metadata_fetch_queue),
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
