from __future__ import annotations

import json
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ExtractionResult:
    backend: str
    pdf_path: Path
    pages: str | None
    output_dir: Path
    json_path: Path
    document: dict[str, Any]
    page_texts: dict[int, str]
    combined_text: str
    char_count: int
    word_count: int


def _import_convert():
    from opendataloader_pdf import convert

    return convert


def _coerce_page_number(value: Any) -> int:
    try:
        if value is None:
            return 0
        if isinstance(value, bool):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _collect_text_by_page(node: Any, current_page: int = 0, buckets: dict[int, list[str]] | None = None) -> dict[int, list[str]]:
    if buckets is None:
        buckets = defaultdict(list)

    if isinstance(node, dict):
        page_value = (
            node.get("page number")
            or node.get("page_no")
            or node.get("pageNumber")
            or node.get("page")
        )
        page_number = _coerce_page_number(page_value)
        if page_number:
            current_page = page_number

        for key in ("content", "text", "md_content", "html_content"):
            value = node.get(key)
            if isinstance(value, str):
                text = value.strip()
                if text:
                    buckets[current_page].append(text)

        for key, value in node.items():
            if key in {"content", "text", "md_content", "html_content"}:
                continue
            if isinstance(value, (dict, list)):
                _collect_text_by_page(value, current_page=current_page, buckets=buckets)
    elif isinstance(node, list):
        for item in node:
            _collect_text_by_page(item, current_page=current_page, buckets=buckets)

    return buckets


def _find_json_output(output_dir: Path, pdf_path: Path) -> Path:
    expected = output_dir / f"{pdf_path.stem}.json"
    if expected.exists():
        return expected

    matches = list(output_dir.rglob("*.json"))
    if not matches:
        raise FileNotFoundError(f"No JSON output was produced in {output_dir}")

    for match in matches:
        if match.stem == pdf_path.stem:
            return match
    return matches[0]


def extract_pdf_text(
    pdf_path: Path | str,
    *,
    pages: str | None = None,
    backend: str = "native",
    hybrid_backend: str | None = None,
    hybrid_mode: str | None = None,
    hybrid_url: str | None = None,
    hybrid_hancom_ai_ocr_strategy: str | None = None,
    hybrid_hancom_ai_regionlist_strategy: str | None = None,
    hybrid_hancom_ai_image_cache: str | None = None,
    quiet: bool = True,
    use_struct_tree: bool = False,
    output_dir: Path | None = None,
) -> ExtractionResult:
    pdf = Path(pdf_path)
    convert = _import_convert()

    with tempfile.TemporaryDirectory(prefix="calibre-audit-") if output_dir is None else tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir) if output_dir is None else Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        kwargs: dict[str, Any] = {
            "input_path": str(pdf),
            "output_dir": str(out_dir),
            "format": "json",
            "quiet": quiet,
            "pages": pages,
            "use_struct_tree": use_struct_tree,
        }
        if backend == "hybrid":
            selected_hybrid = hybrid_backend or "docling-fast"
            kwargs["hybrid"] = selected_hybrid
            kwargs["hybrid_mode"] = hybrid_mode or "full"
            if hybrid_url:
                kwargs["hybrid_url"] = hybrid_url
            if selected_hybrid == "hancom-ai":
                if hybrid_hancom_ai_ocr_strategy:
                    kwargs["hybrid_hancom_ai_ocr_strategy"] = hybrid_hancom_ai_ocr_strategy
                if hybrid_hancom_ai_regionlist_strategy:
                    kwargs["hybrid_hancom_ai_regionlist_strategy"] = hybrid_hancom_ai_regionlist_strategy
                if hybrid_hancom_ai_image_cache:
                    kwargs["hybrid_hancom_ai_image_cache"] = hybrid_hancom_ai_image_cache
            kwargs["hybrid_fallback"] = True
        convert(**kwargs)

        json_path = _find_json_output(out_dir, pdf)
        document = json.loads(json_path.read_text(encoding="utf-8"))

        page_buckets = _collect_text_by_page(document)
        page_texts = {
            page: " ".join(chunks).strip()
            for page, chunks in page_buckets.items()
            if " ".join(chunks).strip()
        }
        combined_parts = [page_texts[page] for page in sorted(page_texts) if page != 0]
        if 0 in page_texts:
            combined_parts.insert(0, page_texts[0])
        combined_text = "\n".join(part for part in combined_parts if part)
        char_count = len(combined_text)
        word_count = len(combined_text.split())

        return ExtractionResult(
            backend=backend,
            pdf_path=pdf,
            pages=pages,
            output_dir=out_dir,
            json_path=json_path,
            document=document,
            page_texts=page_texts,
            combined_text=combined_text,
            char_count=char_count,
            word_count=word_count,
        )
