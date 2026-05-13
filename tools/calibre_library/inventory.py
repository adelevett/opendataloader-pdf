from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path, PureWindowsPath
from typing import Any

from .paths import default_inventory_path

ARTIFACT_FILE_PREFIX = "._"
ARTIFACT_PATH_MARKER = "__MACOSX"

FILE_CLASS_PRIORITY = {
    "full_pdf_candidate": 100,
    "isbn_named": 95,
    "front_matter_pdf": 90,
    "toc_pdf": 88,
    "index_pdf": 86,
    "preface_intro_pdf": 84,
    "appendix_pdf": 82,
    "glossary_pdf": 80,
    "bibliography_pdf": 78,
    "answers_or_solutions_pdf": 72,
    "page_range_pdf": 65,
    "part_unit_section_pdf": 60,
    "chapter_split_pdf": 55,
    "unknown_pdf": 40,
    "kes_split": 35,
    "artifact": -1000,
}

SCAN_PRIORITY = {
    "front_matter_pdf": 100,
    "toc_pdf": 95,
    "index_pdf": 94,
    "preface_intro_pdf": 92,
    "full_pdf_candidate": 90,
    "isbn_named": 89,
    "appendix_pdf": 70,
    "chapter_split_pdf": 60,
    "page_range_pdf": 58,
    "part_unit_section_pdf": 55,
    "glossary_pdf": 50,
    "bibliography_pdf": 48,
    "answers_or_solutions_pdf": 45,
    "unknown_pdf": 40,
    "kes_split": 35,
    "artifact": -1000,
}

ARTIFACT_CLASS_RE = re.compile(r"(?i)\b(__macosx|\.ds_store|thumbs\.db)\b")
FRONT_MATTER_RE = re.compile(r"(?i)\b(front[ _-]?matter|frontmatter|fm)\b")
TOC_RE = re.compile(r"(?i)\b(toc|contents|table[ _-]?of[ _-]?contents)\b")
INDEX_RE = re.compile(r"(?i)\b(index|idx|cindx)\b")
APPENDIX_RE = re.compile(r"(?i)\bappendix\b|\bappendices\b|\bapp[ _-]?[a-z0-9]+\b")
GLOSSARY_RE = re.compile(r"(?i)\bglossar")
BIBLIOGRAPHY_RE = re.compile(r"(?i)\bbibliograph")
PREFACE_RE = re.compile(r"(?i)\b(preface|foreword|prologue|epilogue)\b")
INTRO_RE = re.compile(r"(?i)\b(introduction|intro)\b")
ANSWERS_RE = re.compile(r"(?i)\b(answer|answers|solution|solutions|self-test|review questions)\b")
PAGE_RANGE_RE = re.compile(r"(?i)\b(?:pg|pp|p|page|pages)\b.*\d+.*(?:-|to|_|\u2013)\s*\d+|\b\d+\s*(?:-|to|_|\u2013)\s*\d+\b")
PART_SECTION_RE = re.compile(r"(?i)\b(part|unit|section|lesson|session|book|module|chapter)\b")
ISBN_STEM_RE = re.compile(r"(?i)^(?:isbn[: _-]*)?(97[89]\d{10}|\d{9}[\dX])$")
NOISE_TOKENS_RE = re.compile(
    r"(?i)\b(pdf|scanned|ocrd|image|images|lg|sm|very|small|large|divided|partial|final|copy|"
    r"book|file|files|folder|edition|ed|vol|volume|part|chapter)\b"
)
ISBN_KEY_RE = re.compile(r"(?i)^(?:97[89]\d{10}|\d{9}[\dX])$")


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (TypeError, ValueError):
        return None


def load_inventory_rows(inventory_path: Path | str | None = None) -> list[dict[str, Any]]:
    path = Path(inventory_path) if inventory_path else default_inventory_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        rows = data.get("rows")
    elif isinstance(data, list):
        rows = data
    else:
        raise TypeError(f"Unsupported inventory JSON shape: {type(data)!r}")
    if not isinstance(rows, list):
        raise TypeError("Inventory JSON does not contain a rows list")
    return rows


def is_artifact_row(row: dict[str, Any]) -> bool:
    source_path = str(row.get("path") or "")
    file_name = str(row.get("file_name") or "")
    stem = str(row.get("stem") or "")
    if ARTIFACT_PATH_MARKER in source_path:
        return True
    if file_name.startswith(ARTIFACT_FILE_PREFIX):
        return True
    if ARTIFACT_CLASS_RE.search(source_path) or ARTIFACT_CLASS_RE.search(file_name) or ARTIFACT_CLASS_RE.search(stem):
        return True
    return False


def normalize_title_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("&", " and ")
    text = text.replace("_", " ")
    text = re.sub(r"(?i)\b(?:19|20)\d{2}\b", " ", text)
    text = NOISE_TOKENS_RE.sub(" ", text)
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def title_key_for_parent_dir(parent_dir: str) -> str:
    leaf = PureWindowsPath(parent_dir).name if parent_dir else ""
    normalized = normalize_title_text(leaf)
    if normalized:
        if normalized.isdigit() and not ISBN_KEY_RE.fullmatch(normalized):
            return ""
        return normalized
    fallback = normalize_title_text(parent_dir)
    if fallback.isdigit() and not ISBN_KEY_RE.fullmatch(fallback):
        return ""
    return fallback or parent_dir.lower().strip()


def classify_row(row: dict[str, Any]) -> dict[str, Any]:
    stem = str(row.get("stem") or "")
    file_name = str(row.get("file_name") or "")
    source_path = str(row.get("path") or "")
    extension = Path(file_name or source_path).suffix.lower()
    chapter_candidate = bool(row.get("is_chapter_candidate"))
    chapter_match_type = str(row.get("chapter_match_type") or "").strip()

    if is_artifact_row(row):
        return {
            "file_class": "artifact",
            "file_confidence": 1.0,
        }

    if extension in {".kes", ".kesi"}:
        return {
            "file_class": "kes_split",
            "file_confidence": 0.9,
        }

    if chapter_candidate:
        return {
            "file_class": "chapter_split_pdf",
            "file_confidence": 0.98 if chapter_match_type else 0.9,
        }

    stem_clean = normalize_title_text(stem)
    file_name_clean = normalize_title_text(file_name)
    if ISBN_STEM_RE.fullmatch(stem.replace(" ", "")):
        return {
            "file_class": "isbn_named",
            "file_confidence": 0.99,
        }
    if FRONT_MATTER_RE.search(stem_clean) or FRONT_MATTER_RE.search(file_name_clean):
        return {
            "file_class": "front_matter_pdf",
            "file_confidence": 0.95,
        }
    if TOC_RE.search(stem_clean) or TOC_RE.search(file_name_clean):
        return {
            "file_class": "toc_pdf",
            "file_confidence": 0.95,
        }
    if INDEX_RE.search(stem_clean) or INDEX_RE.search(file_name_clean):
        return {
            "file_class": "index_pdf",
            "file_confidence": 0.94,
        }
    if PREFACE_RE.search(stem_clean) or PREFACE_RE.search(file_name_clean):
        return {
            "file_class": "preface_intro_pdf",
            "file_confidence": 0.92,
        }
    if INTRO_RE.search(stem_clean) or INTRO_RE.search(file_name_clean):
        return {
            "file_class": "preface_intro_pdf",
            "file_confidence": 0.9,
        }
    if APPENDIX_RE.search(stem_clean) or APPENDIX_RE.search(file_name_clean):
        return {
            "file_class": "appendix_pdf",
            "file_confidence": 0.9,
        }
    if GLOSSARY_RE.search(stem_clean) or GLOSSARY_RE.search(file_name_clean):
        return {
            "file_class": "glossary_pdf",
            "file_confidence": 0.9,
        }
    if BIBLIOGRAPHY_RE.search(stem_clean) or BIBLIOGRAPHY_RE.search(file_name_clean):
        return {
            "file_class": "bibliography_pdf",
            "file_confidence": 0.9,
        }
    if ANSWERS_RE.search(stem) or ANSWERS_RE.search(file_name):
        return {
            "file_class": "answers_or_solutions_pdf",
            "file_confidence": 0.85,
        }
    if PAGE_RANGE_RE.search(stem) or PAGE_RANGE_RE.search(file_name):
        return {
            "file_class": "page_range_pdf",
            "file_confidence": 0.82,
        }
    if PART_SECTION_RE.search(stem) or PART_SECTION_RE.search(file_name):
        return {
            "file_class": "part_unit_section_pdf",
            "file_confidence": 0.8,
        }

    page_count = _safe_int(row.get("page_count"))
    file_size = _safe_int(row.get("file_size_bytes"))
    if page_count is not None and page_count >= 20:
        return {
            "file_class": "full_pdf_candidate",
            "file_confidence": 0.72,
        }
    if file_size is not None and file_size >= 512_000:
        return {
            "file_class": "full_pdf_candidate",
            "file_confidence": 0.68,
        }
    if stem_clean:
        return {
            "file_class": "full_pdf_candidate",
            "file_confidence": 0.62,
        }
    return {
        "file_class": "unknown_pdf",
        "file_confidence": 0.45,
    }


def normalize_row(row: dict[str, Any], *, check_source_exists: bool = False) -> dict[str, Any]:
    source_path = str(row.get("path") or "")
    relative_path = str(row.get("relative_path") or "")
    parent_dir = str(row.get("parent_dir") or "")
    file_name = str(row.get("file_name") or Path(source_path).name)
    stem = str(row.get("stem") or Path(file_name).stem)
    extension = Path(file_name or source_path).suffix.lower()
    classification = classify_row(row)
    parent_key = title_key_for_parent_dir(parent_dir or str(PureWindowsPath(relative_path).parent))
    source_exists = (
        bool(source_path) and Path(source_path).exists()
        if check_source_exists
        else None
    )

    normalized = dict(row)
    normalized.update(
        {
            "source_path": source_path,
            "relative_path": relative_path,
            "parent_dir": parent_dir,
            "file_name": file_name,
            "stem": stem,
            "extension": extension,
            "source_exists": source_exists,
            "parent_title_key": parent_key,
            "file_class": classification["file_class"],
            "file_confidence": classification["file_confidence"],
        }
    )
    return normalized


def _group_id(parent_dir: str) -> str:
    return hashlib.sha1(parent_dir.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _sort_scan_targets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]) -> tuple[int, int, int, str]:
        priority = SCAN_PRIORITY.get(str(row.get("file_class")), 0)
        page_count = _safe_int(row.get("page_count")) or 0
        file_size = _safe_int(row.get("file_size_bytes")) or 0
        return (-priority, -page_count, -file_size, str(row.get("source_path") or ""))

    return sorted(rows, key=sort_key)


def select_primary_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    active = [row for row in rows if row.get("file_class") != "artifact"]
    if not active:
        return None

    def sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
        priority = FILE_CLASS_PRIORITY.get(str(row.get("file_class")), 0)
        page_count = _safe_int(row.get("page_count")) or 0
        file_size = _safe_int(row.get("file_size_bytes")) or 0
        chapter_bonus = 10 if row.get("is_chapter_candidate") else 0
        return (priority + chapter_bonus, page_count, file_size, str(row.get("source_path") or ""))

    return max(active, key=sort_key)


def _group_type_and_confidence(active_rows: list[dict[str, Any]], primary_row: dict[str, Any] | None, nested_duplicate: bool) -> tuple[str, float]:
    if not active_rows:
        return "artifact_group", 1.0
    if len(active_rows) == 1:
        file_class = str(active_rows[0].get("file_class"))
        confidence = 0.95 if file_class in {"full_pdf_candidate", "isbn_named"} else 0.88
        return "single_file_book", confidence

    chapter_count = sum(1 for row in active_rows if row.get("file_class") == "chapter_split_pdf")
    nonchapter_count = len(active_rows) - chapter_count
    class_counts = Counter(str(row.get("file_class")) for row in active_rows)

    if chapter_count == len(active_rows):
        return "chapter_only_book", 0.8
    if chapter_count == 0:
        return "nonchapter_collection", 0.66
    if class_counts.get("full_pdf_candidate", 0) or class_counts.get("isbn_named", 0):
        return "full_pdf_plus_splits", 0.86
    if nonchapter_count == 1 and chapter_count > 1:
        return "split_only_book", 0.75
    return "mixed_book", 0.72


def build_group_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("parent_dir") or "")].append(row)

    duplicate_key_counts = Counter(title_key_for_parent_dir(parent_dir) for parent_dir in grouped)

    records: list[dict[str, Any]] = []
    for parent_dir, group_rows in sorted(grouped.items(), key=lambda item: item[0].lower()):
        active_rows = [row for row in group_rows if row.get("file_class") != "artifact"]
        primary = select_primary_row(active_rows)
        scan_targets = _sort_scan_targets(active_rows)[:5]
        active_sorted_rows = _sort_scan_targets(active_rows)
        active_source_paths = [str(row.get("source_path")) for row in active_sorted_rows]
        active_file_classes = [str(row.get("file_class")) for row in active_sorted_rows]
        active_file_names = [str(row.get("file_name")) for row in active_sorted_rows]
        nested_duplicate = False
        try:
            parts = PureWindowsPath(parent_dir).parts
            nested_duplicate = len(parts) >= 2 and parts[-1].lower() == parts[-2].lower()
        except Exception:
            nested_duplicate = False

        group_type, base_confidence = _group_type_and_confidence(active_rows, primary, nested_duplicate)
        duplicate_key = title_key_for_parent_dir(parent_dir)
        duplicate_cluster_size = duplicate_key_counts.get(duplicate_key, 0)
        confidence = base_confidence
        if nested_duplicate:
            confidence -= 0.1
        if duplicate_cluster_size > 1:
            confidence -= 0.05
        confidence = max(0.0, min(1.0, confidence))
        review_required = confidence < 0.8 or nested_duplicate or duplicate_cluster_size > 1
        class_counts = Counter(str(row.get("file_class")) for row in active_rows)

        records.append(
            {
                "group_id": _group_id(parent_dir),
                "parent_dir": parent_dir,
                "parent_title_key": duplicate_key,
                "group_type": group_type,
                "file_count": len(group_rows),
                "active_file_count": len(active_rows),
                "artifact_count": len(group_rows) - len(active_rows),
                "chapter_count": class_counts.get("chapter_split_pdf", 0),
                "nonchapter_count": len(active_rows) - class_counts.get("chapter_split_pdf", 0),
                "file_class_counts": dict(class_counts),
                "primary_source_path": str(primary.get("source_path")) if primary else None,
                "primary_file_class": str(primary.get("file_class")) if primary else None,
                "primary_file_confidence": primary.get("file_confidence") if primary else None,
                "active_source_paths": active_source_paths,
                "active_file_classes": active_file_classes,
                "active_file_names": active_file_names,
                "scan_targets": [str(row.get("source_path")) for row in scan_targets],
                "scan_target_classes": [str(row.get("file_class")) for row in scan_targets],
                "nested_duplicate_candidate": nested_duplicate,
                "duplicate_key": duplicate_key,
                "duplicate_cluster_size": duplicate_cluster_size,
                "confidence": round(confidence, 3),
                "review_required": review_required,
            }
        )
    return records


def build_duplicate_candidates(group_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in group_records:
        key = str(record.get("duplicate_key") or "").strip()
        if key:
            by_key[key].append(record)

    duplicates: list[dict[str, Any]] = []
    for key, records in sorted(by_key.items(), key=lambda item: item[0]):
        if len(records) < 2:
            continue
        duplicates.append(
            {
                "duplicate_key": key,
                "group_count": len(records),
                "group_ids": [record["group_id"] for record in records],
                "parent_dirs": [record["parent_dir"] for record in records],
                "primary_paths": [record["primary_source_path"] for record in records],
                "nested_duplicate_count": sum(1 for record in records if record["nested_duplicate_candidate"]),
            }
        )
    return duplicates


def classify_inventory_manifest(
    inventory_path: Path | str | None = None,
    *,
    check_source_exists: bool = False,
) -> dict[str, Any]:
    raw_rows = load_inventory_rows(inventory_path)
    rows = [normalize_row(row, check_source_exists=check_source_exists) for row in raw_rows]
    active_rows = [row for row in rows if not row.get("file_class") == "artifact"]
    artifact_rows = [row for row in rows if row.get("file_class") == "artifact"]
    group_records = build_group_records(rows)
    duplicate_candidates = build_duplicate_candidates(group_records)

    class_counts = Counter(str(row.get("file_class")) for row in rows)
    group_type_counts = Counter(str(group.get("group_type")) for group in group_records)
    review_required_count = sum(1 for group in group_records if group.get("review_required"))
    nested_duplicate_count = sum(1 for group in group_records if group.get("nested_duplicate_candidate"))

    summary = {
        "inventory_path": str(Path(inventory_path) if inventory_path else default_inventory_path()),
        "total_rows": len(rows),
        "active_rows": len(active_rows),
        "artifact_rows": len(artifact_rows),
        "group_count": len(group_records),
        "review_required_groups": review_required_count,
        "nested_duplicate_groups": nested_duplicate_count,
        "duplicate_cluster_count": len(duplicate_candidates),
        "file_class_counts": dict(class_counts),
        "group_type_counts": dict(group_type_counts),
    }
    return {
        "rows": rows,
        "group_records": group_records,
        "duplicate_candidates": duplicate_candidates,
        "summary": summary,
    }
