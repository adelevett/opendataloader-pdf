from __future__ import annotations

import argparse
import json
import platform
import sys
from collections import Counter
from dataclasses import asdict
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

from tools.calibre_library.extract import extract_pdf_text
from tools.calibre_library.io import load_jsonl, write_json, write_jsonl
from tools.calibre_library.isbn import IsbnCandidate, find_isbn_candidates
from tools.calibre_library.paths import calibre_artifacts_dir, calibre_work_dir, ensure_calibre_dirs


SOURCE_KIND_PRIORITY = {
    "path": 3,
    "hybrid_text": 2,
    "native_text": 1,
}

PATH_CLASS_CONFIDENCE = {
    "isbn_named": 0.99,
    "front_matter_pdf": 0.97,
    "toc_pdf": 0.96,
    "index_pdf": 0.95,
    "preface_intro_pdf": 0.93,
    "full_pdf_candidate": 0.91,
    "chapter_split_pdf": 0.89,
    "appendix_pdf": 0.84,
    "glossary_pdf": 0.84,
    "bibliography_pdf": 0.84,
    "answers_or_solutions_pdf": 0.82,
    "page_range_pdf": 0.8,
    "part_unit_section_pdf": 0.78,
    "unknown_pdf": 0.72,
    "artifact": 0.0,
}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit ISBN coverage for Calibre import groups.")
    parser.add_argument(
        "--groups-jsonl",
        type=Path,
        default=calibre_work_dir() / "book_groups.jsonl",
        help="Grouped inventory manifest produced by classify_inventory.py",
    )
    parser.add_argument(
        "--inventory-json",
        type=Path,
        default=calibre_work_dir() / "inventory_manifest.json",
        help="Classification manifest with inventory metadata",
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
        default="1-4",
        help="Page range to inspect in each target PDF when text extraction is needed",
    )
    parser.add_argument(
        "--max-scan-targets",
        type=int,
        default=5,
        help="Maximum number of target files to inspect per group when text extraction is needed",
    )
    parser.add_argument(
        "--group-limit",
        type=int,
        default=0,
        help="Limit the number of groups processed for a smoke test",
    )
    parser.add_argument(
        "--path-confidence-threshold",
        type=float,
        default=0.9,
        help="Minimum path-confidence needed to skip PDF text extraction",
    )
    parser.add_argument(
        "--verify-path-candidates",
        action="store_true",
        help="Always inspect PDF text even when a path-based ISBN is already present",
    )
    parser.add_argument(
        "--allow-hybrid-fallback",
        action="store_true",
        help="Run the hybrid extractor when native text extraction is too sparse",
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
        help="Hybrid mode used when the fallback OCR path is exercised",
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


def _score_candidate(candidate: IsbnCandidate) -> tuple[float, int, int]:
    page_number = candidate.page_number if candidate.page_number is not None else 9999
    return (
        candidate.confidence,
        SOURCE_KIND_PRIORITY.get(candidate.source_kind, 0),
        1000 - page_number,
    )


def _candidate_payload(candidate: IsbnCandidate) -> dict[str, Any]:
    return asdict(candidate)


def _consolidate_candidates(candidates: list[IsbnCandidate]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        canonical = candidate.canonical_isbn or candidate.isbn
        entry = grouped.setdefault(
            canonical,
            {
                "isbn": candidate.isbn,
                "canonical_isbn": canonical,
                "best": candidate,
                "evidence": [],
                "raw_examples": [],
            },
        )
        payload = _candidate_payload(candidate)
        entry["evidence"].append(payload)
        if payload["raw"] not in entry["raw_examples"] and len(entry["raw_examples"]) < 3:
            entry["raw_examples"].append(payload["raw"])
        if _score_candidate(candidate) > _score_candidate(entry["best"]):
            entry["best"] = candidate

    consolidated: list[dict[str, Any]] = []
    for canonical, entry in grouped.items():
        best = entry["best"]
        consolidated.append(
            {
                "isbn": best.isbn,
                "canonical_isbn": canonical,
                "best_confidence": best.confidence,
                "best_source_kind": best.source_kind,
                "best_source_label": best.source_label,
                "best_page_number": best.page_number,
                "evidence_count": len(entry["evidence"]),
                "raw_examples": entry["raw_examples"],
                "evidence": entry["evidence"],
            }
        )

    consolidated.sort(
        key=lambda item: (
            -float(item["best_confidence"]),
            -SOURCE_KIND_PRIORITY.get(str(item["best_source_kind"]), 0),
            item["best_page_number"] if item["best_page_number"] is not None else 9999,
            str(item["canonical_isbn"]),
        )
    )
    return consolidated


def _path_entries(group: dict[str, Any]) -> list[tuple[str, str, float]]:
    entries: list[tuple[str, str, float]] = []
    seen: set[str] = set()

    def add(value: Any, label: str, confidence: float) -> None:
        text = str(value or "").strip()
        if not text or text in seen:
            return
        seen.add(text)
        entries.append((text, label, confidence))

    add(group.get("primary_source_path"), "primary_source_path", 0.99)
    active_paths = list(group.get("active_source_paths") or [])
    active_classes = list(group.get("active_file_classes") or [])
    for index, path_text in enumerate(active_paths):
        file_class = str(active_classes[index]) if index < len(active_classes) else "unknown_pdf"
        add(path_text, f"active_source_paths[{index}]/{file_class}", PATH_CLASS_CONFIDENCE.get(file_class, 0.72))
    add(group.get("parent_dir"), "parent_dir", 0.72)
    add(group.get("parent_title_key"), "parent_title_key", 0.74)
    add(group.get("duplicate_key"), "duplicate_key", 0.7)
    return entries


def _collect_path_candidates(group: dict[str, Any]) -> list[IsbnCandidate]:
    candidates: list[IsbnCandidate] = []
    for text, label, confidence in _path_entries(group):
        candidates.extend(
            find_isbn_candidates(
                text,
                source_kind="path",
                source_label=label,
                confidence=confidence,
            )
        )
    return candidates


def _extract_text_candidates(
    source_path: Path,
    *,
    pages: str,
    backend: str,
    hybrid_url: str,
    hybrid_backend: str,
    hybrid_mode: str,
    hybrid_ocr_strategy: str,
    use_struct_tree: bool,
) -> tuple[list[IsbnCandidate], dict[str, Any]]:
    extraction = extract_pdf_text(
        source_path,
        pages=pages,
        backend=backend,
        hybrid_backend=hybrid_backend,
        hybrid_mode=hybrid_mode,
        hybrid_url=hybrid_url,
        hybrid_hancom_ai_ocr_strategy=hybrid_ocr_strategy,
        quiet=True,
        use_struct_tree=use_struct_tree,
    )

    candidates: list[IsbnCandidate] = []
    base_confidence = 0.84 if backend == "native" else 0.92
    size_bonus = min(extraction.char_count / 10000.0, 0.05)
    confidence = min(0.99, base_confidence + size_bonus)
    for page_number, text in sorted(extraction.page_texts.items()):
        page_label = f"{source_path.name}:page:{page_number}"
        page_confidence = confidence + (0.02 if page_number and page_number <= 2 else 0.0)
        candidates.extend(
            find_isbn_candidates(
                text,
                source_kind="native_text" if backend == "native" else "hybrid_text",
                source_label=page_label,
                page_number=page_number,
                confidence=min(0.99, page_confidence),
            )
        )

    if extraction.combined_text:
        candidates.extend(
            find_isbn_candidates(
                extraction.combined_text,
                source_kind="native_text" if backend == "native" else "hybrid_text",
                source_label=f"{source_path.name}:combined",
                confidence=confidence,
            )
        )

    return candidates, {
        "backend": backend,
        "pages": pages,
        "json_path": str(extraction.json_path),
        "char_count": extraction.char_count,
        "word_count": extraction.word_count,
        "page_count": len(extraction.page_texts),
    }


def _scan_group(
    group: dict[str, Any],
    *,
    pages: str,
    max_scan_targets: int,
    path_confidence_threshold: float,
    verify_path_candidates: bool,
    allow_hybrid_fallback: bool,
    hybrid_url: str,
    hybrid_backend: str,
    hybrid_mode: str,
    hybrid_ocr_strategy: str,
    use_struct_tree: bool,
    native_char_threshold: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    collected: list[IsbnCandidate] = []

    path_candidates = _collect_path_candidates(group)
    path_records = _consolidate_candidates(path_candidates)
    best_path_confidence = path_records[0]["best_confidence"] if path_records else 0.0
    unique_path_isbns = {record["canonical_isbn"] for record in path_records}

    needs_text_scan = verify_path_candidates or not path_records
    if path_records and (len(unique_path_isbns) > 1 or best_path_confidence < path_confidence_threshold):
        needs_text_scan = True

    if needs_text_scan:
        scanned_targets: set[str] = set()

        def scan_target_batch(targets: list[str], classes: list[str], *, phase: str) -> None:
            for index, target in enumerate(targets):
                target_path = Path(str(target))
                target_key = str(target_path)
                if target_key in scanned_targets:
                    continue
                scanned_targets.add(target_key)
                target_class = str(classes[index]) if index < len(classes) else "unknown_pdf"
                if not target_path.exists():
                    attempts.append(
                        {
                            "source_path": str(target_path),
                            "file_class": target_class,
                            "status": "missing",
                            "backend": None,
                            "scan_phase": phase,
                            "candidates": 0,
                        }
                    )
                    continue

                try:
                    native_candidates, extraction_summary = _extract_text_candidates(
                        target_path,
                        pages=pages,
                        backend="native",
                        hybrid_url=hybrid_url,
                        hybrid_backend=hybrid_backend,
                        hybrid_mode=hybrid_mode,
                        hybrid_ocr_strategy=hybrid_ocr_strategy,
                        use_struct_tree=use_struct_tree,
                    )
                    collected.extend(native_candidates)
                    fallback_used = False
                    backend_used = "native"
                    attempt_candidate_count = len(native_candidates)

                    hybrid_candidates: list[IsbnCandidate] = []
                    if (
                        allow_hybrid_fallback
                        and extraction_summary["char_count"] < native_char_threshold
                        and not native_candidates
                    ):
                        hybrid_candidates, hybrid_summary = _extract_text_candidates(
                            target_path,
                            pages=pages,
                            backend="hybrid",
                            hybrid_url=hybrid_url,
                            hybrid_backend=hybrid_backend,
                            hybrid_mode=hybrid_mode,
                            hybrid_ocr_strategy=hybrid_ocr_strategy,
                            use_struct_tree=use_struct_tree,
                        )
                        collected.extend(hybrid_candidates)
                        extraction_summary = hybrid_summary
                        fallback_used = True
                        backend_used = "hybrid"
                        attempt_candidate_count = len(hybrid_candidates)
                    attempts.append(
                        {
                            "source_path": str(target_path),
                            "file_class": target_class,
                            "status": "ok",
                            "backend": backend_used,
                            "fallback_used": fallback_used,
                            "scan_phase": phase,
                            "char_count": extraction_summary["char_count"],
                            "word_count": extraction_summary["word_count"],
                            "page_count": extraction_summary["page_count"],
                            "candidate_count": attempt_candidate_count,
                        }
                    )
                except Exception as exc:
                    attempts.append(
                        {
                            "source_path": str(target_path),
                            "file_class": target_class,
                            "status": "error",
                            "backend": "native",
                            "scan_phase": phase,
                            "error": str(exc),
                            "candidates": 0,
                        }
                    )

        scan_targets = list(group.get("scan_targets") or [])[:max_scan_targets]
        scan_classes = list(group.get("scan_target_classes") or [])
        scan_target_batch(scan_targets, scan_classes, phase="priority")

        if not collected:
            active_paths = list(group.get("active_source_paths") or [])
            active_classes = list(group.get("active_file_classes") or [])
            fallback_targets: list[str] = []
            fallback_classes: list[str] = []
            for index, target in enumerate(active_paths):
                target_key = str(target)
                if target_key in scanned_targets:
                    continue
                fallback_targets.append(target_key)
                fallback_classes.append(str(active_classes[index]) if index < len(active_classes) else "unknown_pdf")
            scan_target_batch(fallback_targets, fallback_classes, phase="fallback")

    consolidated = _consolidate_candidates(path_candidates + collected)
    best_candidate = consolidated[0] if consolidated else None
    candidate_isbns = [record["canonical_isbn"] for record in consolidated]
    candidate_source_kinds = [record["best_source_kind"] for record in consolidated]

    if not consolidated:
        status = "unresolved"
    elif len(consolidated) > 1:
        status = "conflict"
    elif consolidated[0]["best_source_kind"] == "path":
        status = "path_resolved"
    elif consolidated[0]["best_source_kind"] == "hybrid_text":
        status = "hybrid_resolved"
    else:
        status = "text_resolved"

    group_record = {
        "group_id": group.get("group_id"),
        "parent_dir": group.get("parent_dir"),
        "group_type": group.get("group_type"),
        "primary_source_path": group.get("primary_source_path"),
        "scan_targets": group.get("scan_targets", []),
        "scan_target_classes": group.get("scan_target_classes", []),
        "candidate_count": len(consolidated),
        "candidate_isbns": candidate_isbns,
        "candidate_source_kinds": candidate_source_kinds,
        "best_isbn": best_candidate["isbn"] if best_candidate else None,
        "best_canonical_isbn": best_candidate["canonical_isbn"] if best_candidate else None,
        "best_confidence": best_candidate["best_confidence"] if best_candidate else None,
        "best_source_kind": best_candidate["best_source_kind"] if best_candidate else None,
        "best_source_label": best_candidate["best_source_label"] if best_candidate else None,
        "best_page_number": best_candidate["best_page_number"] if best_candidate else None,
        "status": status,
        "needs_metadata_fetch": bool(best_candidate) and len(consolidated) == 1,
        "needs_manual_review": not best_candidate or len(consolidated) != 1 or (
            best_candidate and float(best_candidate["best_confidence"]) < 0.85
        ),
        "scan_attempts": attempts,
        "path_candidate_count": len(path_records),
        "path_candidate_isbns": [record["canonical_isbn"] for record in path_records],
        "path_candidate_best_confidence": best_path_confidence,
        "path_candidate_best_source_kind": path_records[0]["best_source_kind"] if path_records else None,
    }
    return group_record, consolidated


def _render_summary_md(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    lines: list[str] = [
        "# Calibre ISBN Audit Summary",
        "",
        f"- generated_utc: {manifest['generated_utc']}",
        f"- inventory_manifest: {manifest['inventory_manifest']}",
        f"- groups_jsonl: {manifest['groups_jsonl']}",
        f"- pages: {manifest['pages']}",
        f"- max_scan_targets: {manifest['max_scan_targets']}",
        f"- allow_hybrid_fallback: {manifest['allow_hybrid_fallback']}",
        f"- hybrid_url: {manifest['hybrid_url']}",
        "",
        "## Counts",
        f"- groups_total: {summary['groups_total']}",
        f"- groups_scanned: {summary['groups_scanned']}",
        f"- groups_with_isbn: {summary['groups_with_isbn']}",
        f"- groups_with_path_isbn: {summary['groups_with_path_isbn']}",
        f"- groups_with_text_isbn: {summary['groups_with_text_isbn']}",
        f"- groups_with_hybrid_isbn: {summary['groups_with_hybrid_isbn']}",
        f"- groups_with_conflict: {summary['groups_with_conflict']}",
        f"- groups_unresolved: {summary['groups_unresolved']}",
        f"- candidate_count: {summary['candidate_count']}",
        f"- path_candidate_count: {summary['path_candidate_count']}",
        f"- text_candidate_count: {summary['text_candidate_count']}",
        f"- hybrid_candidate_count: {summary['hybrid_candidate_count']}",
        f"- errors: {summary['errors']}",
        "",
        "## Status Breakdown",
    ]
    for name, count in sorted(summary.get("status_counts", {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Source Kind Breakdown"])
    for name, count in sorted(summary.get("candidate_source_kind_counts", {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Sample Resolved Groups"])
    for record in manifest.get("resolved_groups", [])[:20]:
        lines.append(
            f"- {record['group_id']} | {record['status']} | {record['best_isbn']} | "
            f"{record['parent_dir']}"
        )

    lines.extend(["", "## Sample Unresolved Groups"])
    for record in manifest.get("unresolved_groups", [])[:20]:
        lines.append(f"- {record['group_id']} | {record['status']} | {record['parent_dir']}")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.groups_jsonl.exists():
        raise FileNotFoundError(
            f"Group manifest not found: {args.groups_jsonl}. Run classify_inventory.py first."
        )
    if not args.inventory_json.exists():
        raise FileNotFoundError(
            f"Inventory manifest not found: {args.inventory_json}. Run classify_inventory.py first."
        )

    work_dir, artifact_dir = ensure_calibre_dirs(args.work_dir, args.artifact_dir)
    groups = load_jsonl(args.groups_jsonl)
    if args.group_limit and args.group_limit > 0:
        groups = groups[: args.group_limit]

    inventory_manifest = json.loads(args.inventory_json.read_text(encoding="utf-8"))
    if not isinstance(inventory_manifest, dict):
        raise TypeError("Inventory manifest must be a JSON object")

    group_audits: list[dict[str, Any]] = []
    candidate_records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    source_kind_counts: Counter[str] = Counter()
    errors = 0
    resolved_groups: list[dict[str, Any]] = []
    unresolved_groups: list[dict[str, Any]] = []

    for group in groups:
        group_record, consolidated = _scan_group(
            group,
            pages=args.pages,
            max_scan_targets=args.max_scan_targets,
            path_confidence_threshold=args.path_confidence_threshold,
            verify_path_candidates=args.verify_path_candidates,
            allow_hybrid_fallback=args.allow_hybrid_fallback,
            hybrid_url=args.hybrid_url,
            hybrid_backend=args.hybrid_backend,
            hybrid_mode=args.hybrid_mode,
            hybrid_ocr_strategy=args.hybrid_ocr_strategy,
            use_struct_tree=args.use_struct_tree,
            native_char_threshold=args.native_char_threshold,
        )
        group_audits.append(group_record)
        candidate_records.extend(
            {
                "group_id": group_record["group_id"],
                "parent_dir": group_record["parent_dir"],
                "group_type": group_record["group_type"],
                **candidate,
            }
            for candidate in consolidated
        )
        status_counts[group_record["status"]] += 1
        for candidate in consolidated:
            source_kind_counts[str(candidate["best_source_kind"])] += 1
        if group_record["status"] == "unresolved":
            unresolved_groups.append(group_record)
        else:
            resolved_groups.append(group_record)
        if any(attempt.get("status") == "error" for attempt in group_record.get("scan_attempts", [])):
            errors += 1

    groups_total = len(groups)
    groups_scanned = len(group_audits)
    groups_with_isbn = sum(1 for record in group_audits if record["best_isbn"])
    groups_with_path_isbn = sum(1 for record in group_audits if record["best_source_kind"] == "path")
    groups_with_text_isbn = sum(1 for record in group_audits if record["best_source_kind"] == "native_text")
    groups_with_hybrid_isbn = sum(1 for record in group_audits if record["best_source_kind"] == "hybrid_text")
    groups_with_conflict = sum(1 for record in group_audits if record["status"] == "conflict")
    groups_unresolved = sum(1 for record in group_audits if record["status"] == "unresolved")
    candidate_count = len(candidate_records)
    path_candidate_count = sum(1 for candidate in candidate_records if candidate["best_source_kind"] == "path")
    text_candidate_count = sum(1 for candidate in candidate_records if candidate["best_source_kind"] == "native_text")
    hybrid_candidate_count = sum(1 for candidate in candidate_records if candidate["best_source_kind"] == "hybrid_text")

    manifest = {
        "generated_utc": _utc_now(),
        "repo_root": str(REPO_ROOT),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "command": list(sys.argv if argv is None else [sys.argv[0], *argv]),
        "groups_jsonl": str(args.groups_jsonl),
        "inventory_manifest": str(args.inventory_json),
        "pages": args.pages,
        "max_scan_targets": args.max_scan_targets,
        "allow_hybrid_fallback": args.allow_hybrid_fallback,
        "hybrid_url": args.hybrid_url,
        "summary": {
            "groups_total": groups_total,
            "groups_scanned": groups_scanned,
            "groups_with_isbn": groups_with_isbn,
            "groups_with_path_isbn": groups_with_path_isbn,
            "groups_with_text_isbn": groups_with_text_isbn,
            "groups_with_hybrid_isbn": groups_with_hybrid_isbn,
            "groups_with_conflict": groups_with_conflict,
            "groups_unresolved": groups_unresolved,
            "candidate_count": candidate_count,
            "path_candidate_count": path_candidate_count,
            "text_candidate_count": text_candidate_count,
            "hybrid_candidate_count": hybrid_candidate_count,
            "errors": errors,
            "status_counts": dict(status_counts),
            "candidate_source_kind_counts": dict(source_kind_counts),
        },
        "resolved_groups": resolved_groups,
        "unresolved_groups": unresolved_groups,
    }

    write_jsonl(work_dir / "isbn_audit_candidates.jsonl", candidate_records)
    write_jsonl(work_dir / "isbn_audit_groups.jsonl", group_audits)
    write_json(work_dir / "isbn_audit_manifest.json", manifest)
    write_json(artifact_dir / "isbn_audit_summary.json", manifest)
    (artifact_dir / "isbn_audit_summary.md").write_text(
        _render_summary_md(manifest),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "groups": groups_total,
                "resolved": groups_with_isbn,
                "unresolved": groups_unresolved,
                "conflicts": groups_with_conflict,
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
