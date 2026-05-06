import json
from pathlib import Path

from opendataloader_pdf import normalize_opendataloader_document


def _raw_doc(*kids, **overrides):
    doc = {
        "file name": "sample.pdf",
        "number of pages": 1,
        "author": "author",
        "title": "title",
        "creation date": None,
        "modification date": None,
        "kids": list(kids),
    }
    doc.update(overrides)
    return doc


def _text_element(raw_type, raw_id, content, **overrides):
    element = {
        "type": raw_type,
        "id": raw_id,
        "page number": 1,
        "bounding box": [1, 2, 3, 4],
        "font": "Helvetica",
        "font size": 12,
        "text color": "[0.0]",
        "content": content,
    }
    element.update(overrides)
    if raw_id is None:
        element.pop("id")
    return element


def _queue_categories(doc):
    return {item["category"] for item in doc["reviewQueue"]}


def test_lorem_sample_normalizes_to_heading_and_paragraph():
    repo_root = Path(__file__).resolve().parents[3]
    raw = json.loads((repo_root / "samples" / "json" / "lorem.json").read_text())

    doc = normalize_opendataloader_document(raw, analyzed_at="2026-05-06T00:00:00Z")

    assert doc["schema"] == "remedipdf.intermediate.v0"
    for key in (
        "reviewQueue",
        "readingOrder",
        "regions",
        "tables",
        "lists",
        "assets",
        "captions",
    ):
        assert key in doc

    regions = doc["regions"]
    assert len([region for region in regions.values() if region["type"] == "heading"]) == 1
    assert len([region for region in regions.values() if region["type"] == "paragraph"]) == 1
    assert doc["readingOrder"]["regionIds"] == ["region:odl:1", "region:odl:2"]

    heading = regions["region:odl:1"]
    assert heading["pdfRole"] == "H1"
    assert heading["bbox"] == {
        "left": 200.891,
        "bottom": 706.938,
        "right": 394.152,
        "top": 745.132,
        "unit": "pt",
        "origin": "bottom-left",
    }
    assert doc["readingOrder"]["provenance"] == [{"source": "opendataloader-local"}]


def test_heading_paragraph_caption_linkage():
    image = {
        "type": "image",
        "id": 10,
        "page number": 1,
        "bounding box": [10, 20, 30, 40],
        "alt": "Chart alt",
    }
    caption = _text_element(
        "caption",
        11,
        "Figure 1. Chart",
        **{"linked content id": 10},
    )
    raw = _raw_doc(
        _text_element("heading", 1, "Title", **{"heading level": 2}),
        _text_element("paragraph", 2, "Body"),
        image,
        caption,
    )

    doc = normalize_opendataloader_document(raw)

    assert doc["regions"]["region:odl:1"]["pdfRole"] == "H2"
    assert doc["regions"]["region:odl:2"]["pdfRole"] == "P"
    caption_link = doc["captions"]["caption:region:odl:11"]
    assert caption_link["targetRegionId"] == "region:odl:10"
    assert "caption-link" not in _queue_categories(doc)


def test_missing_image_alt_and_unresolved_caption_target_are_queued():
    image = {
        "type": "image",
        "id": 12,
        "page number": 1,
        "bounding box": [10, 20, 30, 40],
    }
    caption = _text_element(
        "caption",
        13,
        "Figure 2. Missing target",
        **{"linked content id": 999},
    )

    doc = normalize_opendataloader_document(_raw_doc(image, caption))

    assert doc["assets"]["asset:region:odl:12"]["review"]["reasons"] == ["needs-alt-text"]
    assert doc["captions"]["caption:region:odl:13"]["review"]["reasons"] == ["caption-link"]
    assert {"needs-alt-text", "caption-link"}.issubset(_queue_categories(doc))


def test_table_spans_and_header_review():
    table = {
        "type": "table",
        "id": 20,
        "page number": 1,
        "bounding box": [0, 0, 100, 100],
        "number of rows": 1,
        "number of columns": 2,
        "rows": [
            {
                "type": "table row",
                "row number": 1,
                "cells": [
                    {
                        "type": "table cell",
                        "id": 21,
                        "page number": 1,
                        "bounding box": [0, 0, 50, 100],
                        "row number": 1,
                        "column number": 1,
                        "row span": 1,
                        "column span": 2,
                        "kids": [_text_element("paragraph", 22, "Cell")],
                    }
                ],
            }
        ],
    }

    doc = normalize_opendataloader_document(_raw_doc(table))

    table_model = doc["tables"]["table:region:odl:20"]
    assert table_model["rows"] == [{"index": 1, "cellIds": ["region:odl:21"]}]
    assert table_model["cells"]["region:odl:21"]["columnSpan"] == 2
    assert table_model["cells"]["region:odl:21"]["rowSpan"] == 1
    assert set(table_model["review"]["reasons"]) == {"table-headers", "table-spans"}
    assert {"table-headers", "table-spans"}.issubset(_queue_categories(doc))


def test_list_items_preserve_order_and_text():
    raw_list = {
        "type": "list",
        "id": 30,
        "page number": 1,
        "bounding box": [0, 0, 100, 100],
        "numbering style": "decimal",
        "number of list items": 2,
        "list items": [
            _text_element("list item", 31, "First", kids=[]),
            _text_element("list item", 32, "Second", kids=[]),
        ],
    }

    doc = normalize_opendataloader_document(_raw_doc(raw_list))

    list_model = doc["lists"]["list:region:odl:30"]
    assert list_model["itemIds"] == ["region:odl:31", "region:odl:32"]
    assert list_model["items"]["region:odl:31"]["level"] == 1
    assert list_model["items"]["region:odl:32"]["ordinal"] == 2
    assert doc["regions"]["region:odl:31"]["text"]["content"] == "First"


def test_image_alt_text_prefers_raw_alt_and_keeps_description_provenance():
    image = {
        "type": "image",
        "id": 40,
        "page number": 1,
        "bounding box": [0, 0, 100, 100],
        "alt": "Explicit alt",
        "description": "Generated description",
        "source": "images/40.png",
        "format": "png",
    }

    doc = normalize_opendataloader_document(_raw_doc(image))

    asset = doc["assets"]["asset:region:odl:40"]
    assert asset["kind"] == "image"
    assert asset["altText"] == {
        "value": "Explicit alt",
        "source": "raw-alt",
        "verified": False,
    }
    assert asset["review"]["reasons"] == ["generated-alt-text"]
    details = doc["regions"]["region:odl:40"]["provenance"][0]["details"]
    assert details["rawAlt"] == "Explicit alt"
    assert details["rawDescription"] == "Generated description"


def test_formula_latex_asset_requires_review():
    formula = {
        "type": "formula",
        "id": 50,
        "page number": 1,
        "bounding box": [0, 0, 100, 20],
        "content": r"E = mc^2",
    }

    doc = normalize_opendataloader_document(_raw_doc(formula))

    asset = doc["assets"]["asset:region:odl:50"]
    assert asset["kind"] == "formula"
    assert asset["formula"] == {"latex": r"E = mc^2", "verified": False}
    assert asset["review"]["reasons"] == ["formula-latex"]
    assert "formula-latex" in _queue_categories(doc)


def test_header_and_footer_are_artifact_candidates():
    header = {
        "type": "header",
        "id": 60,
        "page number": 1,
        "bounding box": [0, 750, 600, 780],
        "kids": [_text_element("paragraph", 61, "Header")],
    }
    footer = {
        "type": "footer",
        "id": 62,
        "page number": 1,
        "bounding box": [0, 0, 600, 30],
        "kids": [_text_element("paragraph", 63, "Footer")],
    }

    doc = normalize_opendataloader_document(_raw_doc(header, footer))

    assert doc["regions"]["region:odl:60"]["pdfRole"] == "Artifact"
    assert doc["regions"]["region:odl:60"]["artifact"] == {
        "isArtifact": False,
        "reason": "header",
    }
    assert doc["regions"]["region:odl:62"]["artifact"]["reason"] == "footer"
    assert doc["regions"]["region:odl:60"]["review"]["reasons"] == ["possible-artifact"]
    assert "possible-artifact" in _queue_categories(doc)


def test_hybrid_confidence_sets_provenance_and_low_confidence_review():
    paragraph = _text_element(
        "paragraph",
        70,
        "Hybrid text",
        confidence=0.25,
        **{"text source": "ocr"},
    )
    raw = _raw_doc(paragraph, hybrid={"backend": "docling"})

    doc = normalize_opendataloader_document(raw, low_confidence_threshold=0.5)

    region = doc["regions"]["region:odl:70"]
    assert region["provenance"][0]["source"] == "hybrid"
    assert region["provenance"][0]["confidence"] == 0.25
    assert region["provenance"][0]["details"]["textSource"] == "ocr"
    assert region["review"]["reasons"] == ["low-confidence"]
    assert "low-confidence" in _queue_categories(doc)


def test_missing_raw_id_gets_deterministic_fallback_id_and_review():
    raw = _raw_doc(_text_element("paragraph", None, "No id"))

    first = normalize_opendataloader_document(raw)
    second = normalize_opendataloader_document(raw)

    first_id = first["readingOrder"]["regionIds"][0]
    second_id = second["readingOrder"]["regionIds"][0]
    assert first_id == second_id
    assert first_id.startswith("region:page:1:path:")
    assert first["regions"][first_id]["rawRef"] == {
        "source": "opendataloader",
        "rawPath": "/kids/0",
        "rawType": "paragraph",
    }
    assert first["regions"][first_id]["review"]["reasons"] == ["missing-raw-id"]
    assert "missing-raw-id" in _queue_categories(first)
