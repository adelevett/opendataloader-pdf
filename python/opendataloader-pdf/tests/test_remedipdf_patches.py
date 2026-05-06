from copy import deepcopy

from opendataloader_pdf import RemediPatchError, apply_patch_set, normalize_opendataloader_document


def _raw_doc(*kids):
    return {
        "file name": "patches.pdf",
        "number of pages": 1,
        "author": "author",
        "title": "title",
        "creation date": None,
        "modification date": None,
        "kids": list(kids),
    }


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
    return element


def _patch_set(doc, *operations, patch_set_id="patchset:test"):
    normalized_ops = []
    for index, operation in enumerate(operations, start=1):
        normalized = {
            "opId": f"op:{index}",
            "timestamp": "2026-05-06T00:00:00Z",
        }
        normalized.update(operation)
        normalized_ops.append(normalized)
    return {
        "schema": "remedipdf.patch.v0",
        "documentId": doc["documentId"],
        "baseRawHash": doc["source"]["rawHash"],
        "patchSetId": patch_set_id,
        "createdAt": "2026-05-06T00:00:01Z",
        "author": {"kind": "user", "id": "user:test"},
        "operations": normalized_ops,
    }


def _operation(op, target, value=None):
    operation = {"op": op, "target": target}
    if value is not None:
        operation["value"] = value
    return operation


def _assert_raises(message_part, func, *, code=None, status_code=None):
    try:
        func()
    except RemediPatchError as exc:
        assert message_part in str(exc)
        if code is not None:
            assert exc.code == code
        if status_code is not None:
            assert exc.status_code == status_code
        return
    raise AssertionError("Expected RemediPatchError")


def _queue_categories(doc):
    return {item["category"] for item in doc["reviewQueue"]}


def _document_with_common_objects():
    image = {
        "type": "image",
        "id": 3,
        "page number": 1,
        "bounding box": [10, 20, 30, 40],
    }
    formula = {
        "type": "formula",
        "id": 4,
        "page number": 1,
        "bounding box": [40, 20, 80, 40],
        "content": r"x+y",
    }
    caption = _text_element(
        "caption",
        5,
        "Unresolved caption",
        **{"linked content id": 999},
    )
    header = {
        "type": "header",
        "id": 6,
        "page number": 1,
        "bounding box": [0, 750, 600, 780],
        "kids": [_text_element("paragraph", 7, "Header")],
    }
    table = {
        "type": "table",
        "id": 10,
        "page number": 1,
        "bounding box": [0, 0, 100, 100],
        "number of rows": 1,
        "number of columns": 1,
        "rows": [
            {
                "type": "table row",
                "row number": 1,
                "cells": [
                    {
                        "type": "table cell",
                        "id": 11,
                        "page number": 1,
                        "bounding box": [0, 0, 100, 100],
                        "row number": 1,
                        "column number": 1,
                        "row span": 1,
                        "column span": 2,
                        "kids": [_text_element("paragraph", 12, "Cell")],
                    }
                ],
            }
        ],
    }
    raw_list = {
        "type": "list",
        "id": 20,
        "page number": 1,
        "bounding box": [0, 100, 100, 200],
        "numbering style": "decimal",
        "number of list items": 2,
        "list items": [
            _text_element("list item", 21, "First", kids=[]),
            _text_element("list item", 22, "Second", kids=[]),
        ],
    }
    return normalize_opendataloader_document(
        _raw_doc(
            _text_element("heading", 1, "Heading", **{"heading level": 1}),
            _text_element("paragraph", 2, "Paragraph"),
            image,
            formula,
            caption,
            header,
            table,
            raw_list,
        ),
        document_id="doc:test",
        analyzed_at="2026-05-06T00:00:00Z",
    )


def test_set_heading_level_changes_heading_pdf_role():
    doc = _document_with_common_objects()
    patched = apply_patch_set(
        doc,
        _patch_set(
            doc,
            _operation("setHeadingLevel", {"regionId": "region:odl:1"}, {"level": 3}),
        ),
    )

    assert patched["regions"]["region:odl:1"]["pdfRole"] == "H3"
    assert doc["regions"]["region:odl:1"]["pdfRole"] == "H1"
    assert patched["patches"]["count"] == 1
    assert patched["patches"]["latestPatchSetId"] == "patchset:test"
    assert patched["patches"]["latestAppliedAt"] == "2026-05-06T00:00:01Z"


def test_apply_patch_set_does_not_mutate_input_document():
    doc = _document_with_common_objects()
    original = deepcopy(doc)

    patched = apply_patch_set(
        doc,
        _patch_set(
            doc,
            _operation("setHeadingLevel", {"regionId": "region:odl:1"}, {"level": 3}),
        ),
    )

    assert doc == original
    assert patched is not doc


def test_set_artifact_marks_header_and_resolves_possible_artifact_review():
    doc = _document_with_common_objects()
    patched = apply_patch_set(
        doc,
        _patch_set(
            doc,
            _operation(
                "setArtifact",
                {"regionId": "region:odl:6"},
                {"isArtifact": True, "reason": "header"},
            ),
        ),
    )

    header = patched["regions"]["region:odl:6"]
    assert header["artifact"] == {"isArtifact": True, "reason": "header"}
    assert header["pdfRole"] == "Artifact"
    assert header["review"]["state"] == "approved"
    assert "possible-artifact" not in _queue_categories(patched)


def test_set_alt_text_verifies_image_and_resolves_alt_review_items():
    doc = _document_with_common_objects()
    patched = apply_patch_set(
        doc,
        _patch_set(
            doc,
            _operation(
                "setAltText",
                {"assetId": "asset:region:odl:3"},
                {"value": "A chart with two bars.", "verified": True},
            ),
        ),
    )

    asset = patched["assets"]["asset:region:odl:3"]
    assert asset["altText"] == {
        "value": "A chart with two bars.",
        "source": "user",
        "verified": True,
    }
    assert asset["review"]["state"] == "approved"
    assert "needs-alt-text" not in _queue_categories(patched)


def test_set_formula_latex_updates_latex_and_verification_state():
    doc = _document_with_common_objects()
    patched = apply_patch_set(
        doc,
        _patch_set(
            doc,
            _operation(
                "setFormulaLatex",
                {"assetId": "asset:region:odl:4"},
                {"latex": r"x^2+y^2=z^2", "verified": True},
            ),
        ),
    )

    asset = patched["assets"]["asset:region:odl:4"]
    assert asset["formula"]["latex"] == r"x^2+y^2=z^2"
    assert asset["formula"]["verified"] is True
    assert asset["review"]["state"] == "approved"
    assert "formula-latex" not in _queue_categories(patched)


def test_set_formula_alt_text_updates_formula_alt_payload():
    doc = _document_with_common_objects()
    patched = apply_patch_set(
        doc,
        _patch_set(
            doc,
            _operation(
                "setFormulaAltText",
                {"assetId": "asset:region:odl:4"},
                {"value": "x plus y", "verified": True},
            ),
        ),
    )

    assert patched["assets"]["asset:region:odl:4"]["formula"]["altText"] == {
        "value": "x plus y",
        "source": "user",
        "verified": True,
    }


def test_set_caption_target_resolves_unresolved_caption_linkage():
    doc = _document_with_common_objects()
    patched = apply_patch_set(
        doc,
        _patch_set(
            doc,
            _operation(
                "setCaptionTarget",
                {"captionId": "caption:region:odl:5"},
                {"targetRegionId": "region:odl:3"},
            ),
        ),
    )

    caption = patched["captions"]["caption:region:odl:5"]
    assert caption["targetRegionId"] == "region:odl:3"
    assert caption["review"]["state"] == "approved"
    assert "caption-link" not in _queue_categories(patched)


def test_table_cell_role_scope_and_span_patches_mutate_tables():
    doc = _document_with_common_objects()
    patched = apply_patch_set(
        doc,
        _patch_set(
            doc,
            _operation("setTableCellRole", {"tableCellId": "region:odl:11"}, {"role": "TH"}),
            _operation(
                "setTableCellScope",
                {"tableCellId": "region:odl:11"},
                {"scope": "column"},
            ),
            _operation(
                "setTableCellSpan",
                {"tableCellId": "region:odl:11"},
                {"rowSpan": 1, "columnSpan": 1},
            ),
        ),
    )

    cell = patched["tables"]["table:region:odl:10"]["cells"]["region:odl:11"]
    assert cell["role"] == "TH"
    assert cell["scope"] == "column"
    assert cell["rowSpan"] == 1
    assert cell["columnSpan"] == 1
    assert patched["regions"]["region:odl:11"]["pdfRole"] == "TH"
    assert patched["tables"]["table:region:odl:10"]["review"]["state"] == "approved"


def test_set_list_item_level_updates_list_model_and_region_state():
    doc = _document_with_common_objects()
    patched = apply_patch_set(
        doc,
        _patch_set(
            doc,
            _operation(
                "setListItemLevel",
                {"listItemId": "region:odl:22"},
                {"level": 2, "parentItemId": "region:odl:21"},
            ),
        ),
    )

    item = patched["lists"]["list:region:odl:20"]["items"]["region:odl:22"]
    assert item["level"] == 2
    assert item["parentItemId"] == "region:odl:21"
    assert patched["regions"]["region:odl:22"]["listItem"]["level"] == 2


def test_set_region_type_bbox_metadata_and_review_status():
    doc = _document_with_common_objects()
    bbox = {
        "left": 9,
        "bottom": 8,
        "right": 70,
        "top": 80,
        "unit": "pt",
        "origin": "bottom-left",
    }
    patched = apply_patch_set(
        doc,
        _patch_set(
            doc,
            _operation(
                "setRegionType",
                {"regionId": "region:odl:2"},
                {"type": "heading", "pdfRole": "H2"},
            ),
            _operation("setBBox", {"regionId": "region:odl:2"}, bbox),
            _operation("setMetadata", {"document": True}, {"title": "Updated"}),
            _operation(
                "setReviewStatus",
                {"regionId": "region:odl:2"},
                {
                    "state": "needs-review",
                    "reasons": ["style-rule-conflict"],
                    "updatedBy": "user",
                    "updatedAt": "2026-05-06T00:00:02Z",
                },
            ),
        ),
    )

    region = patched["regions"]["region:odl:2"]
    assert region["type"] == "heading"
    assert region["pdfRole"] == "H2"
    assert region["bbox"] == bbox
    assert patched["metadata"]["title"] == "Updated"
    assert region["review"]["reasons"] == ["style-rule-conflict"]
    assert "style-rule-conflict" in _queue_categories(patched)


def test_move_reading_order_moves_region_after_reference():
    doc = _document_with_common_objects()
    patched = apply_patch_set(
        doc,
        _patch_set(
            doc,
            _operation(
                "moveReadingOrder",
                {"regionId": "region:odl:2"},
                {"afterRegionId": "region:odl:6"},
            ),
        ),
    )

    assert patched["readingOrder"]["regionIds"] == [
        "region:odl:1",
        "region:odl:3",
        "region:odl:4",
        "region:odl:5",
        "region:odl:6",
        "region:odl:2",
        "region:odl:10",
        "region:odl:20",
    ]
    assert patched["readingOrder"]["pageOrder"]["page:1"] == patched["readingOrder"]["regionIds"]


def test_ordered_patch_conflicts_use_last_operation():
    doc = _document_with_common_objects()
    patched = apply_patch_set(
        doc,
        _patch_set(
            doc,
            _operation("setHeadingLevel", {"regionId": "region:odl:1"}, {"level": 2}),
            _operation("setHeadingLevel", {"regionId": "region:odl:1"}, {"level": 5}),
            _operation("setMetadata", {"document": True}, {"title": "First"}),
            _operation("setMetadata", {"document": True}, {"title": "Last"}),
        ),
    )

    assert patched["regions"]["region:odl:1"]["pdfRole"] == "H5"
    assert patched["metadata"]["title"] == "Last"


def test_invalid_document_id_raw_hash_unknown_target_and_unsupported_op_raise():
    doc = _document_with_common_objects()

    wrong_doc = _patch_set(doc)
    wrong_doc["documentId"] = "doc:other"
    _assert_raises(
        "PatchSet.documentId does not match",
        lambda: apply_patch_set(doc, wrong_doc),
        code="invalid_patch_schema",
        status_code=400,
    )

    wrong_hash = _patch_set(doc)
    wrong_hash["baseRawHash"] = "sha256:wrong"
    _assert_raises(
        "PatchSet.baseRawHash does not match",
        lambda: apply_patch_set(doc, wrong_hash),
        code="raw_hash_mismatch",
        status_code=409,
    )

    unknown_target = _patch_set(
        doc,
        _operation("setHeadingLevel", {"regionId": "region:missing"}, {"level": 2}),
    )
    _assert_raises(
        "Patch target regionId was not found.",
        lambda: apply_patch_set(doc, unknown_target),
        code="unknown_target_id",
        status_code=422,
    )

    unsupported = _patch_set(
        doc,
        _operation("splitRegion", {"regionId": "region:odl:1"}, {}),
    )
    _assert_raises(
        "Patch operation is not supported.",
        lambda: apply_patch_set(doc, unsupported),
        code="unsupported_operation",
        status_code=422,
    )


def test_non_object_patch_set_raises_clear_schema_error():
    doc = _document_with_common_objects()

    _assert_raises(
        "PatchSet body must be an object.",
        lambda: apply_patch_set(doc, None),
        code="invalid_patch_schema",
        status_code=400,
    )
