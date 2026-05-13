from __future__ import annotations

import argparse
import hashlib
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

from tools.calibre_library.audit_isbn import _scan_group
from tools.calibre_library.io import load_jsonl, write_json, write_jsonl
from tools.calibre_library.paths import calibre_artifacts_dir, calibre_work_dir, ensure_calibre_dirs


HIGH_PRIORITY_SCAN_CLASSES = {
    "front_matter_pdf",
    "toc_pdf",
    "index_pdf",
    "preface_intro_pdf",
}
SECONDARY_PRIORITY_SCAN_CLASSES = {
    "full_pdf_candidate",
}
TERTIARY_PRIORITY_SCAN_CLASSES = {
    "appendix_pdf",
    "chapter_split_pdf",
    "page_range_pdf",
    "part_unit_section_pdf",
}

DEFAULT_SAMPLE_SIZE = 100
DEFAULT_PER_GROUP_TYPE = 5


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gather ISBN source-location data from a stratified sample of book groups."
    )
    parser.add_argument(
        "--groups-jsonl",
        type=Path,
        default=calibre_work_dir() / "book_groups.jsonl",
        help="Grouped inventory manifest produced by classify_inventory.py",
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
        "--pages",
        default="1-10",
        help="Page range to inspect in each target PDF when text extraction is needed",
    )
    parser.add_argument(
        "--max-scan-targets",
        type=int,
        default=3,
        help="Maximum number of target files to inspect per group when text extraction is needed",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help="Maximum number of groups to sample in total for calibration",
    )
    parser.add_argument(
        "--per-group-type",
        type=int,
        default=DEFAULT_PER_GROUP_TYPE,
        help="Maximum groups to sample from each group_type before backfilling by priority",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic sampling seed",
    )
    parser.add_argument(
        "--allow-hybrid-fallback",
        action="store_true",
        help="Allow OCR fallback on low-text scan targets",
    )
    parser.add_argument(
        "--allow-chapter-fallback",
        action="store_true",
        help="Allow fallback scanning of chapter-like split and page-range PDFs",
    )
    parser.add_argument(
        "--hybrid-url",
        default="http://127.0.0.1:5002",
        help="Hybrid backend URL used for fallback OCR",
    )
    parser.add_argument(
        "--hybrid-backend",
        default="docling-fast",
        help="Hybrid backend selector passed through to the converter",
    )
    parser.add_argument(
        "--hybrid-mode",
        default="auto",
        help="Hybrid mode used when fallback OCR is exercised",
    )
    parser.add_argument(
        "--hybrid-ocr-strategy",
        default="auto",
        help="Hybrid OCR strategy used when fallback OCR is exercised",
    )
    parser.add_argument(
        "--use-struct-tree",
        action="store_true",
        help="Pass use_struct_tree to the converter during extraction",
    )
    parser.add_argument(
        "--native-char-threshold",
        type=int,
        default=120,
        help="Native extraction char count below which hybrid fallback is triggered",
    )
    return parser.parse_args(argv)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_key(seed: int, value: str) -> str:
    digest = hashlib.sha1(f"{seed}:{value}".encode("utf-8", errors="ignore")).hexdigest()
    return digest


def _selection_priority(group: dict[str, Any]) -> tuple[int, str]:
    scan_target_classes = [str(item) for item in group.get("scan_target_classes") or []]
    group_type = str(group.get("group_type") or "unknown")

    if any(scan_class in HIGH_PRIORITY_SCAN_CLASSES for scan_class in scan_target_classes):
        return 0, "front_matter_like"
    if any(scan_class in SECONDARY_PRIORITY_SCAN_CLASSES for scan_class in scan_target_classes):
        return 1, "full_pdf_candidate"
    if scan_target_classes:
        if any(scan_class in TERTIARY_PRIORITY_SCAN_CLASSES for scan_class in scan_target_classes):
            return 2, "split_or_collection"
        return 2, "other_scan_targets"
    if group_type == "artifact_group":
        return 3, "artifact_group"
    return 3, "unclassified"


def _method_tag(args: argparse.Namespace) -> str:
    hybrid_state = "hybrid" if args.allow_hybrid_fallback else "native"
    chapter_state = "chapter-fallback=on" if args.allow_chapter_fallback else "chapter-fallback=off"
    struct_tree_state = "struct-tree" if args.use_struct_tree else "no-struct-tree"
    return (
        "catalog-stratified|"
        "front-matter-first|"
        f"pages={args.pages}|"
        f"max-targets={args.max_scan_targets}|"
        f"sample-size={args.sample_size}|"
        f"per-group-type={args.per_group_type}|"
        f"{hybrid_state}|"
        f"{chapter_state}|"
        f"{struct_tree_state}|"
        f"native-threshold={args.native_char_threshold}"
    )


def _choose_sample(groups: list[dict[str, Any]], sample_size: int, per_group_type: int, seed: int) -> list[dict[str, Any]]:
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        by_type[str(group.get("group_type") or "unknown")].append(group)

    sample: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def add_group(group: dict[str, Any]) -> None:
        group_id = str(group.get("group_id") or "")
        if not group_id or group_id in seen_ids:
            return
        seen_ids.add(group_id)
        sample.append(group)

    for group_type in sorted(by_type):
        ranked = sorted(
            by_type[group_type],
            key=lambda item: (
                _selection_priority(item)[0],
                _stable_key(seed, str(item.get("group_id") or "")),
            ),
        )
        for group in ranked[:per_group_type]:
            add_group(group)
            if len(sample) >= sample_size:
                return sample[:sample_size]

    if len(sample) < sample_size:
        remaining = [group for group in groups if str(group.get("group_id") or "") not in seen_ids]
        remaining.sort(
            key=lambda item: (
                _selection_priority(item)[0],
                _stable_key(seed, str(item.get("group_id") or "")),
            )
        )
        for group in remaining:
            add_group(group)
            if len(sample) >= sample_size:
                break

    return sample[:sample_size]


def _render_summary_md(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    method = manifest["method"]
    resolved_rows = [row for row in manifest.get("sample_rows", []) if row.get("best_isbn")]
    unresolved_rows = [row for row in manifest.get("sample_rows", []) if not row.get("best_isbn")]
    conflict_rows = [row for row in manifest.get("sample_rows", []) if row.get("status") == "conflict"]
    lines: list[str] = [
        "# ISBN Source Sample",
        "",
        f"- generated_utc: {manifest['generated_utc']}",
        f"- groups_jsonl: {manifest['groups_jsonl']}",
        f"- sample_size: {manifest['sample_size']}",
        f"- per_group_type: {manifest['per_group_type']}",
        f"- pages: {manifest['pages']}",
        f"- allow_hybrid_fallback: {manifest['allow_hybrid_fallback']}",
        f"- sampling_policy: {manifest['sampling_policy']}",
        "",
        "## Method",
        f"- method_tag: {manifest['method_tag']}",
        f"- sample_size: {method['sample_size']}",
        f"- per_group_type: {method['per_group_type']}",
        f"- pages: {method['pages']}",
        f"- max_scan_targets: {method['max_scan_targets']}",
        f"- allow_hybrid_fallback: {method['allow_hybrid_fallback']}",
        f"- allow_chapter_fallback: {method['allow_chapter_fallback']}",
        f"- hybrid_backend: {method['hybrid_backend']}",
        f"- hybrid_mode: {method['hybrid_mode']}",
        f"- hybrid_ocr_strategy: {method['hybrid_ocr_strategy']}",
        f"- use_struct_tree: {method['use_struct_tree']}",
        f"- native_char_threshold: {method['native_char_threshold']}",
        f"- selection_policy: {method['selection_policy']}",
        "",
        "## Counts",
        f"- groups_total: {summary['groups_total']}",
        f"- groups_sampled: {summary['groups_sampled']}",
        f"- groups_with_isbn: {summary['groups_with_isbn']}",
        f"- groups_with_path_isbn: {summary['groups_with_path_isbn']}",
        f"- groups_with_text_isbn: {summary['groups_with_text_isbn']}",
        f"- groups_with_hybrid_isbn: {summary['groups_with_hybrid_isbn']}",
        f"- groups_unresolved: {summary['groups_unresolved']}",
        f"- groups_with_conflict: {summary['groups_with_conflict']}",
        "",
        "## Best Source Kind",
    ]
    for name, count in sorted(summary.get("best_source_kind_counts", {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Best Source Labels"])
    for name, count in sorted(summary.get("best_source_label_counts", {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Page Numbers"])
    for name, count in sorted(summary.get("best_page_number_counts", {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Selection Priority"])
    for name, count in sorted(summary.get("selection_priority_counts", {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Findings"])
    lines.append(f"- resolved: {len(resolved_rows)}")
    lines.append(f"- unresolved: {len(unresolved_rows)}")
    lines.append(f"- conflict: {len(conflict_rows)}")

    if resolved_rows:
        lines.append("")
        lines.append("### Resolved")
        for row in resolved_rows[:20]:
            lines.append(
                f"- {row['group_id']} | {row['best_isbn']} | {row['best_source_kind']} | "
                f"{row['best_source_label']} | page {row['best_page_number']} | "
                f"method={row['method_tag']}"
            )

    if conflict_rows:
        lines.append("")
        lines.append("### Conflicts")
        for row in conflict_rows[:20]:
            lines.append(
                f"- {row['group_id']} | {row['group_type']} | {row['best_isbn']} | "
                f"{row['best_source_kind']} | method={row['method_tag']}"
            )

    if unresolved_rows:
        lines.append("")
        lines.append("### Unresolved")
        for row in unresolved_rows[:20]:
            lines.append(f"- {row['group_id']} | {row['group_type']} | method={row['method_tag']}")

    lines.extend(["", "## Sample Rows"])
    for row in manifest.get("sample_rows", [])[:20]:
        lines.append(
            f"- {row['group_id']} | {row['group_type']} | {row['title_guess']} | "
            f"{row['status']} | {row['best_isbn']} | {row['best_source_kind']} | "
            f"{row['best_source_label']} | page {row['best_page_number']} | {row['selection_priority_label']} | "
            f"{row['method_tag']}"
        )

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.groups_jsonl.exists():
        raise FileNotFoundError(f"Group manifest not found: {args.groups_jsonl}")

    work_dir, artifact_dir = ensure_calibre_dirs(args.work_dir, args.artifact_dir)
    groups = load_jsonl(args.groups_jsonl)
    sample_groups = _choose_sample(groups, args.sample_size, args.per_group_type, args.seed)

    sample_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    best_source_kind_counts: Counter[str] = Counter()
    best_source_label_counts: Counter[str] = Counter()
    best_page_number_counts: Counter[str] = Counter()
    selection_priority_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    errors = 0
    method_tag = _method_tag(args)

    for group in sample_groups:
        audit_record, consolidated = _scan_group(
            group,
            pages=args.pages,
            max_scan_targets=args.max_scan_targets,
            path_confidence_threshold=0.9,
            verify_path_candidates=False,
            allow_hybrid_fallback=args.allow_hybrid_fallback,
            allow_chapter_fallback=args.allow_chapter_fallback,
            hybrid_url=args.hybrid_url,
            hybrid_backend=args.hybrid_backend,
            hybrid_mode=args.hybrid_mode,
            hybrid_ocr_strategy=args.hybrid_ocr_strategy,
            use_struct_tree=args.use_struct_tree,
            native_char_threshold=args.native_char_threshold,
        )

        title_guess = str(group.get("parent_title_key") or group.get("parent_dir") or "")
        selection_priority_bucket, selection_priority_label = _selection_priority(group)
        row = {
            "group_id": audit_record["group_id"],
            "title_guess": title_guess,
            "parent_dir": audit_record["parent_dir"],
            "group_type": audit_record["group_type"],
            "primary_source_path": audit_record["primary_source_path"],
            "status": audit_record["status"],
            "best_isbn": audit_record["best_isbn"],
            "best_canonical_isbn": audit_record["best_canonical_isbn"],
            "best_source_kind": audit_record["best_source_kind"],
            "best_source_label": audit_record["best_source_label"],
            "best_page_number": audit_record["best_page_number"],
            "candidate_count": audit_record["candidate_count"],
            "path_candidate_count": audit_record["path_candidate_count"],
            "needs_manual_review": audit_record["needs_manual_review"],
            "needs_metadata_fetch": audit_record["needs_metadata_fetch"],
            "scan_attempts": audit_record["scan_attempts"],
            "path_candidate_isbns": audit_record["path_candidate_isbns"],
            "path_candidate_best_confidence": audit_record["path_candidate_best_confidence"],
            "selection_priority_bucket": selection_priority_bucket,
            "selection_priority_label": selection_priority_label,
            "method_tag": method_tag,
        }
        sample_rows.append(row)
        candidate_rows.extend(
            {
                "group_id": audit_record["group_id"],
                "title_guess": title_guess,
                "group_type": audit_record["group_type"],
                **candidate,
            }
            for candidate in consolidated
        )
        status_counts[audit_record["status"]] += 1
        if audit_record["best_source_kind"]:
            best_source_kind_counts[str(audit_record["best_source_kind"])] += 1
        if audit_record["best_source_label"]:
            best_source_label_counts[str(audit_record["best_source_label"])] += 1
        if audit_record["best_page_number"] is not None:
            best_page_number_counts[str(audit_record["best_page_number"])] += 1
        selection_priority_counts[selection_priority_label] += 1
        if any(attempt.get("status") == "error" for attempt in audit_record.get("scan_attempts", [])):
            errors += 1

    groups_total = len(groups)
    groups_sampled = len(sample_rows)
    groups_with_isbn = sum(1 for row in sample_rows if row["best_isbn"])
    groups_with_path_isbn = sum(1 for row in sample_rows if row["best_source_kind"] == "path")
    groups_with_text_isbn = sum(1 for row in sample_rows if row["best_source_kind"] == "native_text")
    groups_with_hybrid_isbn = sum(1 for row in sample_rows if row["best_source_kind"] == "hybrid_text")
    groups_with_conflict = sum(1 for row in sample_rows if row["status"] == "conflict")
    groups_unresolved = sum(1 for row in sample_rows if row["status"] == "unresolved")

    manifest = {
        "generated_utc": _utc_now(),
        "repo_root": str(REPO_ROOT),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "groups_jsonl": str(args.groups_jsonl),
        "sample_size": args.sample_size,
        "per_group_type": args.per_group_type,
        "pages": args.pages,
        "allow_hybrid_fallback": args.allow_hybrid_fallback,
        "allow_chapter_fallback": args.allow_chapter_fallback,
        "method_tag": method_tag,
        "sampling_policy": (
            "front_matter_like > full_pdf_candidate > split_or_collection > artifact_group/unclassified; "
            "chapter-like fallback disabled by default; per-group-type deterministic hash tie-break"
        ),
        "method": {
            "sample_size": args.sample_size,
            "per_group_type": args.per_group_type,
            "pages": args.pages,
            "max_scan_targets": args.max_scan_targets,
            "allow_hybrid_fallback": args.allow_hybrid_fallback,
            "allow_chapter_fallback": args.allow_chapter_fallback,
            "hybrid_url": args.hybrid_url,
            "hybrid_backend": args.hybrid_backend,
            "hybrid_mode": args.hybrid_mode,
            "hybrid_ocr_strategy": args.hybrid_ocr_strategy,
            "use_struct_tree": args.use_struct_tree,
            "native_char_threshold": args.native_char_threshold,
            "seed": args.seed,
            "selection_policy": "front_matter_like > full_pdf_candidate > split_or_collection > artifact_group/unclassified; chapter-like fallback disabled by default; per-group-type deterministic hash tie-break",
        },
        "summary": {
            "groups_total": groups_total,
            "groups_sampled": groups_sampled,
            "groups_with_isbn": groups_with_isbn,
            "groups_with_path_isbn": groups_with_path_isbn,
            "groups_with_text_isbn": groups_with_text_isbn,
            "groups_with_hybrid_isbn": groups_with_hybrid_isbn,
            "groups_with_conflict": groups_with_conflict,
            "groups_unresolved": groups_unresolved,
            "errors": errors,
            "best_source_kind_counts": dict(best_source_kind_counts),
            "best_source_label_counts": dict(best_source_label_counts),
            "best_page_number_counts": dict(best_page_number_counts),
            "selection_priority_counts": dict(selection_priority_counts),
            "status_counts": dict(status_counts),
        },
        "sample_rows": sample_rows,
        "candidate_rows": candidate_rows,
        "sample_group_ids": [row["group_id"] for row in sample_rows],
    }

    write_jsonl(work_dir / "isbn_source_sample_rows.jsonl", sample_rows)
    write_jsonl(work_dir / "isbn_source_sample_candidates.jsonl", candidate_rows)
    write_json(work_dir / "isbn_source_sample_manifest.json", manifest)
    write_json(artifact_dir / "isbn_source_sample_summary.json", manifest)
    (artifact_dir / "isbn_source_sample_summary.md").write_text(
        _render_summary_md(manifest),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "sampled": groups_sampled,
                "with_isbn": groups_with_isbn,
                "unresolved": groups_unresolved,
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
