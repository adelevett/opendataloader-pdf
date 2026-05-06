"""OpenDataLoader JSON to RemediPDF intermediate normalization."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

SCHEMA_NAME = "remedipdf.intermediate.v0"
PATCH_SCHEMA_NAME = "remedipdf.patch.v0"
RAW_SCHEMA_NAME = "opendataloader.schema.json"
DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.8

__all__ = [
    "SCHEMA_NAME",
    "PATCH_SCHEMA_NAME",
    "RAW_SCHEMA_NAME",
    "DEFAULT_LOW_CONFIDENCE_THRESHOLD",
    "RemediPatchError",
    "normalize_opendataloader_document",
    "to_remedi_document",
    "apply_patch_set",
]

_REGION_TYPES = {
    "paragraph",
    "heading",
    "caption",
    "table",
    "tableCell",
    "list",
    "listItem",
    "figure",
    "formula",
    "artifact",
    "textBlock",
    "header",
    "footer",
    "unknown",
}

_PDF_ROLES = {
    "P",
    "H1",
    "H2",
    "H3",
    "H4",
    "H5",
    "H6",
    "Caption",
    "Table",
    "TR",
    "TH",
    "TD",
    "L",
    "LI",
    "Figure",
    "Formula",
    "Artifact",
    "Div",
    "Unknown",
}

_SUPPORTED_PATCH_OPS = {
    "setRegionType",
    "setArtifact",
    "setBBox",
    "moveReadingOrder",
    "setHeadingLevel",
    "setTableCellRole",
    "setTableCellScope",
    "setTableCellSpan",
    "setListItemLevel",
    "setAltText",
    "setFormulaLatex",
    "setFormulaAltText",
    "setCaptionTarget",
    "setMetadata",
    "setReviewStatus",
}

_REVIEW_PRIORITY = {
    "needs-alt-text": "high",
    "generated-alt-text": "medium",
    "formula-latex": "medium",
    "table-headers": "medium",
    "table-spans": "medium",
    "caption-link": "high",
    "reading-order": "medium",
    "possible-artifact": "medium",
    "style-rule-conflict": "medium",
    "missing-raw-id": "low",
    "low-confidence": "high",
}

_PATCH_ERROR_STATUS_CODES = {
    "invalid_patch_schema": 400,
    "raw_hash_mismatch": 409,
    "unsupported_operation": 422,
    "unknown_target_id": 422,
    "patch_conflict": 409,
}


def normalize_opendataloader_document(
    raw_document: dict[str, Any],
    *,
    document_id: str | None = None,
    analyzed_at: str | None = None,
    low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    """Normalize raw OpenDataLoader JSON into a RemediPDF document dictionary."""

    normalizer = _Normalizer(raw_document, low_confidence_threshold)
    return normalizer.normalize(document_id=document_id, analyzed_at=analyzed_at)


def to_remedi_document(
    raw_document: dict[str, Any],
    *,
    document_id: str | None = None,
    analyzed_at: str | None = None,
    low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    """Alias for normalize_opendataloader_document()."""

    return normalize_opendataloader_document(
        raw_document,
        document_id=document_id,
        analyzed_at=analyzed_at,
        low_confidence_threshold=low_confidence_threshold,
    )


class RemediPatchError(ValueError):
    """Raised when a RemediPDF patch set is invalid or cannot be applied."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        document_id: str | None = None,
        patch_set_id: str | None = None,
        op_id: str | None = None,
        target: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.document_id = document_id
        self.patch_set_id = patch_set_id
        self.op_id = op_id
        self.target = target
        self.details = dict(details or {})
        self.status_code = (
            status_code if status_code is not None else _status_code_for_patch_error_code(code)
        )

    def with_context(
        self,
        *,
        code: str | None = None,
        document_id: str | None = None,
        patch_set_id: str | None = None,
        op_id: str | None = None,
        target: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> "RemediPatchError":
        merged_details = dict(self.details)
        if details:
            merged_details.update(details)
        return RemediPatchError(
            str(self),
            code=code or self.code or _infer_patch_error_code(str(self)),
            document_id=document_id or self.document_id,
            patch_set_id=patch_set_id or self.patch_set_id,
            op_id=op_id or self.op_id,
            target=target or self.target,
            details=merged_details,
            status_code=(
                status_code
                if status_code is not None
                else self.status_code
                if self.status_code is not None
                else _status_code_for_patch_error_code(code or self.code or _infer_patch_error_code(str(self)))
            ),
        )


def apply_patch_set(
    remedi_document: dict[str, Any],
    patch_set: dict[str, Any],
) -> dict[str, Any]:
    """Apply a RemediPDF patch set and return a patched document copy."""

    patch_set_id = patch_set.get("patchSetId") if isinstance(patch_set, dict) else None
    document_id = patch_set.get("documentId") if isinstance(patch_set, dict) else None
    try:
        _validate_patch_set(remedi_document, patch_set)
    except RemediPatchError as exc:
        raise exc.with_context(
            document_id=document_id,
            patch_set_id=patch_set_id,
        ) from exc
    patched = deepcopy(remedi_document)
    author = patch_set.get("author") if isinstance(patch_set.get("author"), dict) else {}
    updated_by = author.get("kind") if author.get("kind") in {"system", "user", "rule"} else "user"

    for operation in patch_set.get("operations") or []:
        try:
            _apply_operation(patched, operation, updated_by=updated_by)
        except RemediPatchError as exc:
            inferred_code = _infer_patch_error_code(str(exc))
            resolved_code = exc.code or inferred_code
            resolved_status_code = exc.status_code or _status_code_for_patch_error_code(resolved_code)
            if resolved_code == "patch_conflict":
                conflict_details = dict(exc.details)
                conflict_details.setdefault("originalMessage", str(exc))
                raise RemediPatchError(
                    "Patch operation conflicts with current document state.",
                    code="patch_conflict",
                    document_id=document_id,
                    patch_set_id=patch_set_id,
                    op_id=operation.get("opId") if isinstance(operation, dict) else None,
                    target=operation.get("target") if isinstance(operation, dict) else None,
                    details=conflict_details,
                    status_code=resolved_status_code,
                ) from exc
            raise exc.with_context(
                document_id=document_id,
                patch_set_id=patch_set_id,
                op_id=operation.get("opId") if isinstance(operation, dict) else None,
                target=operation.get("target") if isinstance(operation, dict) else None,
                code=resolved_code,
                status_code=resolved_status_code,
            ) from exc

    patched["reviewQueue"] = _review_queue_from_document(patched)
    patches = dict(patched.get("patches") or {})
    patches["count"] = int(patches.get("count") or 0) + 1
    patches["latestPatchSetId"] = patch_set["patchSetId"]
    patches["latestAppliedAt"] = patch_set.get("createdAt") or _utc_now()
    patched["patches"] = patches
    return patched


def _validate_patch_set(remedi_document: dict[str, Any], patch_set: dict[str, Any]) -> None:
    if not isinstance(remedi_document, dict):
        raise RemediPatchError(
            "RemediDocument body must be an object.",
            code="invalid_patch_schema",
            details={"field": "remediDocument"},
        )
    if not isinstance(patch_set, dict):
        raise RemediPatchError(
            "PatchSet body must be an object.",
            code="invalid_patch_schema",
            details={"field": "patchSet"},
        )
    if remedi_document.get("schema") != SCHEMA_NAME:
        raise RemediPatchError(
            "RemediDocument schema is invalid.",
            code="invalid_patch_schema",
            details={
                "field": "schema",
                "expected": SCHEMA_NAME,
                "actual": remedi_document.get("schema"),
            },
        )
    if patch_set.get("schema") != PATCH_SCHEMA_NAME:
        raise RemediPatchError(
            "PatchSet schema is invalid.",
            code="invalid_patch_schema",
            details={
                "field": "schema",
                "expected": PATCH_SCHEMA_NAME,
                "actual": patch_set.get("schema"),
            },
        )
    if patch_set.get("documentId") != remedi_document.get("documentId"):
        raise RemediPatchError(
            "PatchSet.documentId does not match RemediDocument.documentId.",
            code="invalid_patch_schema",
            details={
                "field": "documentId",
                "expected": remedi_document.get("documentId"),
                "actual": patch_set.get("documentId"),
            },
        )

    raw_hash = (remedi_document.get("source") or {}).get("rawHash")
    if patch_set.get("baseRawHash") != raw_hash:
        raise RemediPatchError(
            "PatchSet.baseRawHash does not match RemediDocument.source.rawHash.",
            code="raw_hash_mismatch",
            details={
                "expectedRawHash": raw_hash,
                "actualBaseRawHash": patch_set.get("baseRawHash"),
            },
        )
    if not patch_set.get("patchSetId"):
        raise RemediPatchError(
            "PatchSet.patchSetId is required.",
            code="invalid_patch_schema",
            details={"field": "patchSetId", "expected": "string"},
        )
    if not isinstance(patch_set.get("operations"), list):
        raise RemediPatchError(
            "PatchSet.operations must be an array.",
            code="invalid_patch_schema",
            details={"field": "operations", "expected": "array"},
        )


def _apply_operation(
    remedi_document: dict[str, Any],
    operation: dict[str, Any],
    *,
    updated_by: str,
) -> None:
    if not isinstance(operation, dict):
        raise RemediPatchError("Patch operation must be an object.")
    op = operation.get("op")
    if op not in _SUPPORTED_PATCH_OPS:
        raise RemediPatchError(
            "Patch operation is not supported.",
            code="unsupported_operation",
            details={"op": op},
        )

    target = operation.get("target") if isinstance(operation.get("target"), dict) else {}
    value = operation.get("value")
    updated_at = operation.get("timestamp")

    if op == "setRegionType":
        _apply_set_region_type(remedi_document, target, value)
    elif op == "setArtifact":
        _apply_set_artifact(remedi_document, target, value, updated_by, updated_at)
    elif op == "setBBox":
        _apply_set_bbox(remedi_document, target, value)
    elif op == "moveReadingOrder":
        _apply_move_reading_order(remedi_document, target, value)
    elif op == "setHeadingLevel":
        _apply_set_heading_level(remedi_document, target, value)
    elif op == "setTableCellRole":
        _apply_set_table_cell_role(remedi_document, target, value, updated_by, updated_at)
    elif op == "setTableCellScope":
        _apply_set_table_cell_scope(remedi_document, target, value, updated_by, updated_at)
    elif op == "setTableCellSpan":
        _apply_set_table_cell_span(remedi_document, target, value, updated_by, updated_at)
    elif op == "setListItemLevel":
        _apply_set_list_item_level(remedi_document, target, value)
    elif op == "setAltText":
        _apply_set_alt_text(remedi_document, target, value, updated_by, updated_at)
    elif op == "setFormulaLatex":
        _apply_set_formula_latex(remedi_document, target, value, updated_by, updated_at)
    elif op == "setFormulaAltText":
        _apply_set_formula_alt_text(remedi_document, target, value)
    elif op == "setCaptionTarget":
        _apply_set_caption_target(remedi_document, target, value, updated_by, updated_at)
    elif op == "setMetadata":
        _apply_set_metadata(remedi_document, value)
    elif op == "setReviewStatus":
        _apply_set_review_status(remedi_document, target, value)


def _apply_set_region_type(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
) -> None:
    region = _get_region(remedi_document, _target_id(target, "regionId"))
    value = _require_value_dict("setRegionType", value)
    region_type = value.get("type")
    if region_type not in _REGION_TYPES:
        raise RemediPatchError(
            "setRegionType value.type is invalid.",
            code="invalid_patch_schema",
            details={"field": "type", "actual": region_type},
        )
    region["type"] = region_type

    pdf_role = value.get("pdfRole") or _default_pdf_role_for_region_type(region_type)
    if pdf_role not in _PDF_ROLES:
        raise RemediPatchError(
            "setRegionType value.pdfRole is invalid.",
            code="invalid_patch_schema",
            details={"field": "pdfRole", "actual": pdf_role},
        )
    region["pdfRole"] = pdf_role


def _apply_set_artifact(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
    updated_by: str,
    updated_at: str | None,
) -> None:
    region = _get_region(remedi_document, _target_id(target, "regionId"))
    value = _require_value_dict("setArtifact", value)
    if not isinstance(value.get("isArtifact"), bool):
        raise RemediPatchError(
            "setArtifact value.isArtifact must be a boolean.",
            code="invalid_patch_schema",
            details={"field": "isArtifact"},
        )

    artifact = {"isArtifact": value["isArtifact"]}
    if value.get("reason") is not None:
        artifact["reason"] = value["reason"]
    elif value["isArtifact"] and region.get("type") in {"header", "footer"}:
        artifact["reason"] = region["type"]
    region["artifact"] = artifact
    if value["isArtifact"]:
        region["pdfRole"] = "Artifact"
        _discard_review_reason(region, "possible-artifact", updated_by, updated_at)


def _apply_set_bbox(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
) -> None:
    region = _get_region(remedi_document, _target_id(target, "regionId"))
    region["bbox"] = _validate_bbox_value(value)


def _apply_move_reading_order(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
) -> None:
    region_id = _target_id(target, "regionId")
    region = _get_region(remedi_document, region_id)
    value = _require_value_dict("moveReadingOrder", value)
    before_id = value.get("beforeRegionId")
    after_id = value.get("afterRegionId")
    if before_id and after_id:
        raise RemediPatchError(
            "moveReadingOrder value cannot set both beforeRegionId and afterRegionId.",
            code="invalid_patch_schema",
        )
    if before_id is not None:
        _get_region(remedi_document, before_id)
    if after_id is not None:
        _get_region(remedi_document, after_id)

    reading_order = remedi_document.setdefault("readingOrder", {})
    region_ids = reading_order.setdefault("regionIds", [])
    _move_id_in_order(region_ids, region_id, before_id=before_id, after_id=after_id)

    page_id = value.get("pageId") or region["pageId"]
    if page_id != region["pageId"]:
        raise RemediPatchError(
            "moveReadingOrder value.pageId does not match the region pageId.",
            code="invalid_patch_schema",
            details={"pageId": page_id, "regionPageId": region["pageId"]},
        )
    page_order = reading_order.setdefault("pageOrder", {}).setdefault(page_id, [])
    _move_id_in_order(page_order, region_id, before_id=before_id, after_id=after_id)


def _apply_set_heading_level(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
) -> None:
    region = _get_region(remedi_document, _target_id(target, "regionId"))
    value = _require_value_dict("setHeadingLevel", value)
    level = value.get("level")
    if not isinstance(level, int) or not 1 <= level <= 6:
        raise RemediPatchError(
            "setHeadingLevel value.level must be an integer from 1 to 6.",
            code="invalid_patch_schema",
            details={"field": "level", "actual": level},
        )
    region["type"] = "heading"
    region["pdfRole"] = f"H{level}"


def _apply_set_table_cell_role(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
    updated_by: str,
    updated_at: str | None,
) -> None:
    table, cell = _get_table_cell(remedi_document, _target_id(target, "tableCellId"))
    value = _require_value_dict("setTableCellRole", value)
    role = value.get("role")
    if role not in {"TH", "TD"}:
        raise RemediPatchError(
            "setTableCellRole value.role is invalid.",
            code="invalid_patch_schema",
            details={"field": "role", "actual": role},
        )
    cell["role"] = role
    _get_region(remedi_document, cell["regionId"])["pdfRole"] = role
    _refresh_table_review(table, updated_by, updated_at)


def _apply_set_table_cell_scope(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
    updated_by: str,
    updated_at: str | None,
) -> None:
    table, cell = _get_table_cell(remedi_document, _target_id(target, "tableCellId"))
    value = _require_value_dict("setTableCellScope", value)
    scope = value.get("scope")
    if scope not in {"row", "column", "both", "none"}:
        raise RemediPatchError(
            "setTableCellScope value.scope is invalid.",
            code="invalid_patch_schema",
            details={"field": "scope", "actual": scope},
        )
    cell["scope"] = scope
    _refresh_table_review(table, updated_by, updated_at)


def _apply_set_table_cell_span(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
    updated_by: str,
    updated_at: str | None,
) -> None:
    table, cell = _get_table_cell(remedi_document, _target_id(target, "tableCellId"))
    value = _require_value_dict("setTableCellSpan", value)
    row_span = value.get("rowSpan")
    column_span = value.get("columnSpan")
    if not isinstance(row_span, int) or row_span < 1:
        raise RemediPatchError(
            "setTableCellSpan value.rowSpan must be a positive integer.",
            code="invalid_patch_schema",
            details={"field": "rowSpan", "actual": row_span},
        )
    if not isinstance(column_span, int) or column_span < 1:
        raise RemediPatchError(
            "setTableCellSpan value.columnSpan must be a positive integer.",
            code="invalid_patch_schema",
            details={"field": "columnSpan", "actual": column_span},
        )
    cell["rowSpan"] = row_span
    cell["columnSpan"] = column_span
    _refresh_table_review(table, updated_by, updated_at)


def _apply_set_list_item_level(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
) -> None:
    list_model, item = _get_list_item(remedi_document, _target_id(target, "listItemId"))
    value = _require_value_dict("setListItemLevel", value)
    level = value.get("level")
    if not isinstance(level, int) or level < 1:
        raise RemediPatchError(
            "setListItemLevel value.level must be a positive integer.",
            code="invalid_patch_schema",
            details={"field": "level", "actual": level},
        )

    parent_item_id = value.get("parentItemId")
    if parent_item_id is not None and parent_item_id not in list_model.get("items", {}):
        raise RemediPatchError(
            "Patch target parentItemId was not found.",
            code="unknown_target_id",
            details={"listItemId": parent_item_id},
        )
    item["level"] = level
    if parent_item_id is None:
        item.pop("parentItemId", None)
    else:
        item["parentItemId"] = parent_item_id

    region = _get_region(remedi_document, item["regionId"])
    list_item_state = region.setdefault("listItem", {})
    list_item_state["level"] = level
    if parent_item_id is None:
        list_item_state.pop("parentItemId", None)
    else:
        list_item_state["parentItemId"] = parent_item_id


def _apply_set_alt_text(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
    updated_by: str,
    updated_at: str | None,
) -> None:
    asset = _get_asset(remedi_document, _target_id(target, "assetId"))
    if asset.get("kind") != "image":
        raise RemediPatchError(
            "setAltText target is not an image asset.",
            code="unknown_target_id",
            details={"assetId": asset.get("id"), "kind": asset.get("kind")},
        )
    value = _require_value_dict("setAltText", value)
    text = value.get("value")
    verified = value.get("verified")
    if not isinstance(text, str):
        raise RemediPatchError(
            "setAltText value.value must be a string.",
            code="invalid_patch_schema",
            details={"field": "value"},
        )
    if not isinstance(verified, bool):
        raise RemediPatchError(
            "setAltText value.verified must be a boolean.",
            code="invalid_patch_schema",
            details={"field": "verified"},
        )

    asset["altText"] = {"value": text, "source": "user", "verified": verified}
    reasons = _review_reasons(asset)
    reasons.discard("needs-alt-text")
    reasons.discard("generated-alt-text")
    if not text:
        reasons.add("needs-alt-text")
    elif not verified:
        reasons.add("generated-alt-text")
    _set_review_reasons(asset, reasons, updated_by, updated_at)


def _apply_set_formula_latex(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
    updated_by: str,
    updated_at: str | None,
) -> None:
    asset = _get_asset(remedi_document, _target_id(target, "assetId"))
    if asset.get("kind") != "formula":
        raise RemediPatchError(
            "setFormulaLatex target is not a formula asset.",
            code="unknown_target_id",
            details={"assetId": asset.get("id"), "kind": asset.get("kind")},
        )
    value = _require_value_dict("setFormulaLatex", value)
    latex = value.get("latex")
    verified = value.get("verified")
    if not isinstance(latex, str):
        raise RemediPatchError(
            "setFormulaLatex value.latex must be a string.",
            code="invalid_patch_schema",
            details={"field": "latex"},
        )
    if not isinstance(verified, bool):
        raise RemediPatchError(
            "setFormulaLatex value.verified must be a boolean.",
            code="invalid_patch_schema",
            details={"field": "verified"},
        )

    formula = asset.setdefault("formula", {})
    formula["latex"] = latex
    formula["verified"] = verified
    reasons = _review_reasons(asset)
    if verified and latex:
        reasons.discard("formula-latex")
    else:
        reasons.add("formula-latex")
    _set_review_reasons(asset, reasons, updated_by, updated_at)


def _apply_set_formula_alt_text(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
) -> None:
    asset = _get_asset(remedi_document, _target_id(target, "assetId"))
    if asset.get("kind") != "formula":
        raise RemediPatchError(
            "setFormulaAltText target is not a formula asset.",
            code="unknown_target_id",
            details={"assetId": asset.get("id"), "kind": asset.get("kind")},
        )
    value = _require_value_dict("setFormulaAltText", value)
    text = value.get("value")
    verified = value.get("verified")
    if not isinstance(text, str):
        raise RemediPatchError(
            "setFormulaAltText value.value must be a string.",
            code="invalid_patch_schema",
            details={"field": "value"},
        )
    if not isinstance(verified, bool):
        raise RemediPatchError(
            "setFormulaAltText value.verified must be a boolean.",
            code="invalid_patch_schema",
            details={"field": "verified"},
        )
    asset.setdefault("formula", {})["altText"] = {
        "value": text,
        "source": "user",
        "verified": verified,
    }


def _apply_set_caption_target(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
    updated_by: str,
    updated_at: str | None,
) -> None:
    caption = _get_caption(remedi_document, _target_id(target, "captionId"))
    value = _require_value_dict("setCaptionTarget", value)
    target_region_id = value.get("targetRegionId")
    reasons = _review_reasons(caption)
    if target_region_id is None:
        caption.pop("targetRegionId", None)
        caption.pop("confidence", None)
        reasons.add("caption-link")
    else:
        _get_region(remedi_document, target_region_id)
        caption["targetRegionId"] = target_region_id
        caption["confidence"] = 1.0
        reasons.discard("caption-link")
    _set_review_reasons(caption, reasons, updated_by, updated_at)


def _apply_set_metadata(remedi_document: dict[str, Any], value: Any) -> None:
    value = _require_value_dict("setMetadata", value)
    allowed_keys = {"title", "author", "language", "creationDate", "modificationDate"}
    unknown_keys = sorted(set(value) - allowed_keys)
    if unknown_keys:
        raise RemediPatchError(
            "setMetadata contains unsupported field(s).",
            code="invalid_patch_schema",
            details={"fields": unknown_keys},
        )
    remedi_document.setdefault("metadata", {}).update(value)


def _apply_set_review_status(
    remedi_document: dict[str, Any],
    target: dict[str, Any],
    value: Any,
) -> None:
    review_target = _get_review_target(remedi_document, target)
    review_target["review"] = _validate_review_status(value)


def _get_region(remedi_document: dict[str, Any], region_id: str) -> dict[str, Any]:
    regions = remedi_document.get("regions") or {}
    if region_id not in regions:
        raise RemediPatchError(
            "Patch target regionId was not found.",
            code="unknown_target_id",
            details={"regionId": region_id},
        )
    return regions[region_id]


def _get_asset(remedi_document: dict[str, Any], asset_id: str) -> dict[str, Any]:
    assets = remedi_document.get("assets") or {}
    if asset_id not in assets:
        raise RemediPatchError(
            "Patch target assetId was not found.",
            code="unknown_target_id",
            details={"assetId": asset_id},
        )
    return assets[asset_id]


def _get_caption(remedi_document: dict[str, Any], caption_id: str) -> dict[str, Any]:
    captions = remedi_document.get("captions") or {}
    if caption_id not in captions:
        raise RemediPatchError(
            "Patch target captionId was not found.",
            code="unknown_target_id",
            details={"captionId": caption_id},
        )
    return captions[caption_id]


def _get_table_cell(
    remedi_document: dict[str, Any],
    table_cell_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    for table in (remedi_document.get("tables") or {}).values():
        cells = table.get("cells") or {}
        if table_cell_id in cells:
            return table, cells[table_cell_id]
    raise RemediPatchError(
        "Patch target tableCellId was not found.",
        code="unknown_target_id",
        details={"tableCellId": table_cell_id},
    )


def _get_list_item(
    remedi_document: dict[str, Any],
    list_item_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    for list_model in (remedi_document.get("lists") or {}).values():
        items = list_model.get("items") or {}
        if list_item_id in items:
            return list_model, items[list_item_id]
    raise RemediPatchError(
        "Patch target listItemId was not found.",
        code="unknown_target_id",
        details={"listItemId": list_item_id},
    )


def _get_review_target(remedi_document: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    if target.get("regionId"):
        return _get_region(remedi_document, target["regionId"])
    if target.get("tableId"):
        tables = remedi_document.get("tables") or {}
        table_id = target["tableId"]
        if table_id not in tables:
            raise RemediPatchError(
                "Patch target tableId was not found.",
                code="unknown_target_id",
                details={"tableId": table_id},
            )
        return tables[table_id]
    if target.get("listId"):
        lists = remedi_document.get("lists") or {}
        list_id = target["listId"]
        if list_id not in lists:
            raise RemediPatchError(
                "Patch target listId was not found.",
                code="unknown_target_id",
                details={"listId": list_id},
            )
        return lists[list_id]
    if target.get("assetId"):
        return _get_asset(remedi_document, target["assetId"])
    if target.get("captionId"):
        return _get_caption(remedi_document, target["captionId"])
    raise RemediPatchError(
        "Patch operation target is invalid for setReviewStatus.",
        code="unknown_target_id",
        details={"target": target},
    )


def _target_id(target: dict[str, Any], key: str) -> str:
    target_id = target.get(key)
    if not isinstance(target_id, str) or not target_id:
        raise RemediPatchError(
            f"Patch operation target.{key} is required.",
            code="invalid_patch_schema",
            details={"field": f"target.{key}"},
        )
    return target_id


def _require_value_dict(operation: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RemediPatchError(
            f"{operation} value must be an object.",
            code="invalid_patch_schema",
            details={"operation": operation, "field": "value"},
        )
    return value


def _validate_bbox_value(value: Any) -> dict[str, Any]:
    value = _require_value_dict("setBBox", value)
    required = {"left", "bottom", "right", "top", "unit", "origin"}
    missing = sorted(required - set(value))
    if missing:
        raise RemediPatchError(
            "setBBox value is missing required field(s).",
            code="invalid_patch_schema",
            details={"missing": missing},
        )
    if value["unit"] != "pt" or value["origin"] != "bottom-left":
        raise RemediPatchError(
            "setBBox value must use unit='pt' and origin='bottom-left'.",
            code="invalid_patch_schema",
        )
    for key in ("left", "bottom", "right", "top"):
        if not isinstance(value[key], (int, float)):
            raise RemediPatchError(
                "setBBox value coordinates must be numeric.",
                code="invalid_patch_schema",
                details={"field": key},
            )
    return {
        "left": value["left"],
        "bottom": value["bottom"],
        "right": value["right"],
        "top": value["top"],
        "unit": "pt",
        "origin": "bottom-left",
    }


def _validate_review_status(value: Any) -> dict[str, Any]:
    value = _require_value_dict("setReviewStatus", value)
    state = value.get("state")
    if state not in {"unresolved", "approved", "rejected", "needs-review"}:
        raise RemediPatchError(
            "setReviewStatus value.state is invalid.",
            code="invalid_patch_schema",
            details={"field": "state", "actual": state},
        )
    reasons = value.get("reasons")
    if not isinstance(reasons, list) or not all(isinstance(reason, str) for reason in reasons):
        raise RemediPatchError(
            "setReviewStatus value.reasons must be an array of strings.",
            code="invalid_patch_schema",
            details={"field": "reasons"},
        )
    updated_by = value.get("updatedBy")
    if updated_by not in {"system", "user", "rule"}:
        raise RemediPatchError(
            "setReviewStatus value.updatedBy is invalid.",
            code="invalid_patch_schema",
            details={"field": "updatedBy", "actual": updated_by},
        )

    review = {
        "state": state,
        "reasons": sorted(reasons),
        "updatedBy": updated_by,
    }
    if value.get("updatedAt") is not None:
        review["updatedAt"] = value["updatedAt"]
    return review


def _move_id_in_order(
    ordered_ids: list[str],
    region_id: str,
    *,
    before_id: str | None,
    after_id: str | None,
) -> None:
    if region_id in ordered_ids:
        ordered_ids.remove(region_id)
    if before_id is not None:
        if before_id not in ordered_ids:
            raise RemediPatchError(
                "moveReadingOrder value.beforeRegionId is not in the current order.",
                code="invalid_patch_schema",
                details={"field": "beforeRegionId", "regionId": before_id},
            )
        ordered_ids.insert(ordered_ids.index(before_id), region_id)
        return
    if after_id is not None:
        if after_id not in ordered_ids:
            raise RemediPatchError(
                "moveReadingOrder value.afterRegionId is not in the current order.",
                code="invalid_patch_schema",
                details={"field": "afterRegionId", "regionId": after_id},
            )
        ordered_ids.insert(ordered_ids.index(after_id) + 1, region_id)
        return
    ordered_ids.append(region_id)


def _refresh_table_review(
    table: dict[str, Any],
    updated_by: str,
    updated_at: str | None,
) -> None:
    reasons = _review_reasons(table)
    reasons.discard("table-headers")
    reasons.discard("table-spans")

    cells = table.get("cells") or {}
    if cells and not any(cell.get("role") == "TH" for cell in cells.values()):
        reasons.add("table-headers")
    if any(
        cell.get("rowSpan", 1) > 1 or cell.get("columnSpan", 1) > 1
        for cell in cells.values()
    ):
        reasons.add("table-spans")
    _set_review_reasons(table, reasons, updated_by, updated_at)


def _review_reasons(target: dict[str, Any]) -> set[str]:
    review = target.get("review") if isinstance(target.get("review"), dict) else {}
    reasons = review.get("reasons") if isinstance(review, dict) else []
    return {reason for reason in reasons if isinstance(reason, str)}


def _discard_review_reason(
    target: dict[str, Any],
    reason: str,
    updated_by: str,
    updated_at: str | None,
) -> None:
    reasons = _review_reasons(target)
    reasons.discard(reason)
    _set_review_reasons(target, reasons, updated_by, updated_at)


def _set_review_reasons(
    target: dict[str, Any],
    reasons: set[str],
    updated_by: str,
    updated_at: str | None,
) -> None:
    target["review"] = {
        "state": "needs-review" if reasons else "approved",
        "reasons": sorted(reasons),
        "updatedBy": updated_by,
    }
    if updated_at is not None:
        target["review"]["updatedAt"] = updated_at


def _review_queue_from_document(remedi_document: dict[str, Any]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    _append_review_queue_items(queue, remedi_document.get("regions") or {}, "regionId")
    _append_review_queue_items(queue, remedi_document.get("tables") or {}, "tableId")
    _append_review_queue_items(queue, remedi_document.get("lists") or {}, "listId")
    _append_review_queue_items(queue, remedi_document.get("assets") or {}, "assetId")
    _append_review_queue_items(queue, remedi_document.get("captions") or {}, "captionId")
    return queue


def _append_review_queue_items(
    queue: list[dict[str, Any]],
    targets: dict[str, dict[str, Any]],
    target_key: str,
) -> None:
    for target_id in sorted(targets):
        review = targets[target_id].get("review") or {}
        if review.get("state") not in {"needs-review", "unresolved"}:
            continue
        for reason in sorted(review.get("reasons") or []):
            queue.append(
                {
                    "id": f"review:{reason}:{target_key}:{target_id}",
                    "category": reason,
                    target_key: target_id,
                    "priority": _REVIEW_PRIORITY.get(reason, "medium"),
                    "state": "open",
                }
            )


def _default_pdf_role_for_region_type(region_type: str) -> str:
    return {
        "paragraph": "P",
        "heading": "H1",
        "caption": "Caption",
        "table": "Table",
        "tableCell": "TD",
        "list": "L",
        "listItem": "LI",
        "figure": "Figure",
        "formula": "Formula",
        "artifact": "Artifact",
        "textBlock": "Div",
        "header": "Artifact",
        "footer": "Artifact",
    }.get(region_type, "Unknown")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _infer_patch_error_code(message: str) -> str:
    if message.startswith("RemediDocument schema is invalid"):
        return "invalid_patch_schema"
    if message.startswith("PatchSet schema is invalid"):
        return "invalid_patch_schema"
    if message.startswith("PatchSet.documentId does not match"):
        return "invalid_patch_schema"
    if message.startswith("PatchSet.patchSetId is required"):
        return "invalid_patch_schema"
    if message.startswith("PatchSet.operations must be an array"):
        return "invalid_patch_schema"
    if message.startswith("PatchSet.baseRawHash does not match"):
        return "raw_hash_mismatch"
    if message.startswith("Patch operation is not supported"):
        return "unsupported_operation"
    if message.startswith("Patch target ") and message.endswith("was not found."):
        return "unknown_target_id"
    if message.startswith("Patch operation target.") and message.endswith("is required."):
        return "invalid_patch_schema"
    if message.endswith("must be an object."):
        return "invalid_patch_schema"
    return "patch_conflict"


def _status_code_for_patch_error_code(code: str | None) -> int | None:
    if code is None:
        return None
    return _PATCH_ERROR_STATUS_CODES.get(code, 409)


class _Normalizer:
    def __init__(self, raw_document: dict[str, Any], low_confidence_threshold: float) -> None:
        self.raw_document = raw_document
        self.low_confidence_threshold = low_confidence_threshold

        self.regions: dict[str, dict[str, Any]] = {}
        self.tables: dict[str, dict[str, Any]] = {}
        self.lists: dict[str, dict[str, Any]] = {}
        self.assets: dict[str, dict[str, Any]] = {}
        self.captions: dict[str, dict[str, Any]] = {}

        self.raw_id_to_region_id: dict[int, str] = {}
        self.page_region_ids: dict[str, list[str]] = {}
        self.top_level_region_ids: list[str] = []
        self.top_level_page_order: dict[str, list[str]] = {}

        self.region_reasons: dict[str, set[str]] = {}
        self.table_reasons: dict[str, set[str]] = {}
        self.list_reasons: dict[str, set[str]] = {}
        self.asset_reasons: dict[str, set[str]] = {}
        self.caption_reasons: dict[str, set[str]] = {}

        self.pending_caption_targets: list[tuple[str, int]] = []

    def normalize(
        self,
        *,
        document_id: str | None,
        analyzed_at: str | None,
    ) -> dict[str, Any]:
        raw_hash = _raw_hash(self.raw_document)
        doc_id = document_id or f"doc:{raw_hash.removeprefix('sha256:')[:16]}"
        timestamp = analyzed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        for index, raw in enumerate(self.raw_document.get("kids") or []):
            region_id = self._normalize_element(raw, f"/kids/{index}", parent_id=None)
            if region_id is None:
                continue
            self.top_level_region_ids.append(region_id)
            page_id = self.regions[region_id]["pageId"]
            self.top_level_page_order.setdefault(page_id, []).append(region_id)

        self._resolve_caption_targets()
        self._apply_review_statuses()

        return {
            "schema": SCHEMA_NAME,
            "documentId": doc_id,
            "source": {
                "fileName": self.raw_document.get("file name"),
                "rawSchema": RAW_SCHEMA_NAME,
                "rawHash": raw_hash,
                "analyzedAt": timestamp,
            },
            "metadata": {
                "title": self.raw_document.get("title"),
                "author": self.raw_document.get("author"),
                "creationDate": self.raw_document.get("creation date"),
                "modificationDate": self.raw_document.get("modification date"),
            },
            "pages": self._build_pages(),
            "regions": self.regions,
            "readingOrder": {
                "mode": "region-list",
                "regionIds": self.top_level_region_ids,
                "pageOrder": self.top_level_page_order,
                "provenance": [{"source": "opendataloader-local"}],
            },
            "tables": self.tables,
            "lists": self.lists,
            "assets": self.assets,
            "captions": self.captions,
            "reviewQueue": self._build_review_queue(),
            "patches": {"count": 0},
        }

    def _normalize_element(
        self,
        raw: dict[str, Any],
        raw_path: str,
        *,
        parent_id: str | None,
    ) -> str | None:
        raw_type = raw.get("type", "unknown")
        if raw_type == "table row":
            return None
        if raw_type == "table":
            return self._normalize_table(raw, raw_path, parent_id=parent_id)
        if raw_type == "list":
            return self._normalize_list(raw, raw_path, parent_id=parent_id)
        if raw_type == "image":
            return self._normalize_image(raw, raw_path, parent_id=parent_id)
        if raw_type == "formula":
            return self._normalize_formula(raw, raw_path, parent_id=parent_id)
        if raw_type == "caption":
            return self._normalize_caption(raw, raw_path, parent_id=parent_id)
        if raw_type in {"header", "footer"}:
            return self._normalize_header_footer(raw, raw_path, parent_id=parent_id)
        if raw_type == "table cell":
            return self._normalize_table_cell(raw, raw_path, parent_id=parent_id, table_id=None)
        if raw_type == "list item":
            return self._normalize_list_item(
                raw,
                raw_path,
                parent_id=parent_id,
                list_id=None,
                level=1,
                ordinal=1,
            )
        return self._normalize_generic_region(raw, raw_path, parent_id=parent_id)

    def _normalize_generic_region(
        self,
        raw: dict[str, Any],
        raw_path: str,
        *,
        parent_id: str | None,
    ) -> str:
        region = self._base_region(raw, raw_path, parent_id=parent_id)
        raw_type = raw.get("type", "unknown")
        if raw_type in {"paragraph", "heading", "text block"}:
            region["text"] = _text_payload(raw)
        child_ids = self._normalize_kids(raw, raw_path, region["id"])
        region["childIds"] = child_ids
        self.regions[region["id"]] = region
        self._register_region(region["id"], raw)
        return region["id"]

    def _normalize_caption(
        self,
        raw: dict[str, Any],
        raw_path: str,
        *,
        parent_id: str | None,
    ) -> str:
        region = self._base_region(raw, raw_path, parent_id=parent_id)
        region["text"] = _text_payload(raw)
        caption_id = f"caption:{region['id']}"
        region["captionId"] = caption_id
        child_ids = self._normalize_kids(raw, raw_path, region["id"])
        region["childIds"] = child_ids
        self.regions[region["id"]] = region
        self._register_region(region["id"], raw)

        self.captions[caption_id] = {
            "id": caption_id,
            "regionId": region["id"],
            "review": _review_status(set()),
        }
        linked_raw_id = raw.get("linked content id")
        if isinstance(linked_raw_id, int):
            self.pending_caption_targets.append((caption_id, linked_raw_id))
        else:
            self.caption_reasons.setdefault(caption_id, set()).add("caption-link")
        return region["id"]

    def _normalize_table(
        self,
        raw: dict[str, Any],
        raw_path: str,
        *,
        parent_id: str | None,
    ) -> str:
        region = self._base_region(raw, raw_path, parent_id=parent_id)
        table_id = f"table:{region['id']}"
        region["tableId"] = table_id
        region["childIds"] = []
        self.regions[region["id"]] = region
        self._register_region(region["id"], raw)

        rows: list[dict[str, Any]] = []
        cells: dict[str, dict[str, Any]] = {}
        has_spans = False

        for row_index, row in enumerate(raw.get("rows") or []):
            row_cell_ids: list[str] = []
            for cell_index, cell in enumerate(row.get("cells") or []):
                cell_path = _path_join(_path_join(raw_path, "rows"), row_index)
                cell_path = _path_join(_path_join(cell_path, "cells"), cell_index)
                cell_id = self._normalize_table_cell(
                    cell,
                    cell_path,
                    parent_id=region["id"],
                    table_id=table_id,
                )
                row_cell_ids.append(cell_id)
                region["childIds"].append(cell_id)
                row_span = _int_or_default(cell.get("row span"), 1)
                column_span = _int_or_default(cell.get("column span"), 1)
                has_spans = has_spans or row_span > 1 or column_span > 1
                cells[cell_id] = {
                    "id": cell_id,
                    "regionId": cell_id,
                    "row": _int_or_default(cell.get("row number"), row_index + 1),
                    "column": _int_or_default(cell.get("column number"), cell_index + 1),
                    "rowSpan": row_span,
                    "columnSpan": column_span,
                    "role": "TD",
                    "childRegionIds": self.regions[cell_id]["childIds"],
                }
            rows.append(
                {
                    "index": _int_or_default(row.get("row number"), row_index + 1),
                    "cellIds": row_cell_ids,
                }
            )

        model = {
            "id": table_id,
            "regionId": region["id"],
            "rowCount": _int_or_default(raw.get("number of rows"), len(rows)),
            "columnCount": _int_or_default(raw.get("number of columns"), 0),
            "rows": rows,
            "cells": cells,
            "review": _review_status(set()),
        }
        if isinstance(raw.get("previous table id"), int):
            model["previousTableId"] = f"table:region:odl:{raw['previous table id']}"
        if isinstance(raw.get("next table id"), int):
            model["nextTableId"] = f"table:region:odl:{raw['next table id']}"

        self.tables[table_id] = model
        self.table_reasons.setdefault(table_id, set()).add("table-headers")
        if has_spans or raw.get("tsr") is not None:
            self.table_reasons.setdefault(table_id, set()).add("table-spans")
        return region["id"]

    def _normalize_table_cell(
        self,
        raw: dict[str, Any],
        raw_path: str,
        *,
        parent_id: str | None,
        table_id: str | None,
    ) -> str:
        region = self._base_region(raw, raw_path, parent_id=parent_id)
        if table_id is not None:
            region["tableId"] = table_id
        child_ids = self._normalize_kids(raw, raw_path, region["id"])
        region["childIds"] = child_ids
        self.regions[region["id"]] = region
        self._register_region(region["id"], raw)
        return region["id"]

    def _normalize_list(
        self,
        raw: dict[str, Any],
        raw_path: str,
        *,
        parent_id: str | None,
    ) -> str:
        region = self._base_region(raw, raw_path, parent_id=parent_id)
        list_id = f"list:{region['id']}"
        region["listId"] = list_id
        region["childIds"] = []
        self.regions[region["id"]] = region
        self._register_region(region["id"], raw)

        item_ids: list[str] = []
        items: dict[str, dict[str, Any]] = {}
        for index, item in enumerate(raw.get("list items") or []):
            item_path = _path_join(_path_join(raw_path, "list items"), index)
            item_id = self._normalize_list_item(
                item,
                item_path,
                parent_id=region["id"],
                list_id=list_id,
                level=1,
                ordinal=index + 1,
            )
            item_ids.append(item_id)
            region["childIds"].append(item_id)
            items[item_id] = {
                "id": item_id,
                "regionId": item_id,
                "level": 1,
                "ordinal": index + 1,
                "childRegionIds": self.regions[item_id]["childIds"],
            }

        model = {
            "id": list_id,
            "regionId": region["id"],
            "numberingStyle": raw.get("numbering style", "unknown"),
            "itemIds": item_ids,
            "items": items,
            "review": _review_status(set()),
        }
        if isinstance(raw.get("previous list id"), int):
            model["previousListId"] = f"list:region:odl:{raw['previous list id']}"
        if isinstance(raw.get("next list id"), int):
            model["nextListId"] = f"list:region:odl:{raw['next list id']}"
        self.lists[list_id] = model
        return region["id"]

    def _normalize_list_item(
        self,
        raw: dict[str, Any],
        raw_path: str,
        *,
        parent_id: str | None,
        list_id: str | None,
        level: int,
        ordinal: int,
    ) -> str:
        region = self._base_region(raw, raw_path, parent_id=parent_id)
        if list_id is not None:
            region["listId"] = list_id
            region["listItem"] = {
                "level": level,
                "ordinal": ordinal,
            }
        region["text"] = _text_payload(raw)
        child_ids = self._normalize_kids(raw, raw_path, region["id"])
        region["childIds"] = child_ids
        self.regions[region["id"]] = region
        self._register_region(region["id"], raw)
        return region["id"]

    def _normalize_image(
        self,
        raw: dict[str, Any],
        raw_path: str,
        *,
        parent_id: str | None,
    ) -> str:
        region = self._base_region(raw, raw_path, parent_id=parent_id)
        asset_id = f"asset:{region['id']}"
        region["assetId"] = asset_id
        region["childIds"] = self._normalize_kids(raw, raw_path, region["id"])
        self.regions[region["id"]] = region
        self._register_region(region["id"], raw)

        asset = {
            "id": asset_id,
            "regionId": region["id"],
            "kind": "image",
            "review": _review_status(set()),
        }
        for raw_key in ("source", "data", "format"):
            if raw.get(raw_key) is not None:
                asset[raw_key] = raw[raw_key]

        alt = _image_alt_text(raw)
        if alt is None:
            self.asset_reasons.setdefault(asset_id, set()).add("needs-alt-text")
        else:
            asset["altText"] = alt
            self.asset_reasons.setdefault(asset_id, set()).add("generated-alt-text")
        self.assets[asset_id] = asset
        return region["id"]

    def _normalize_formula(
        self,
        raw: dict[str, Any],
        raw_path: str,
        *,
        parent_id: str | None,
    ) -> str:
        region = self._base_region(raw, raw_path, parent_id=parent_id)
        asset_id = f"asset:{region['id']}"
        region["assetId"] = asset_id
        region["childIds"] = self._normalize_kids(raw, raw_path, region["id"])
        self.regions[region["id"]] = region
        self._register_region(region["id"], raw)

        self.assets[asset_id] = {
            "id": asset_id,
            "regionId": region["id"],
            "kind": "formula",
            "formula": {
                "latex": raw.get("content", ""),
                "verified": False,
            },
            "review": _review_status({"formula-latex"}),
        }
        self.asset_reasons.setdefault(asset_id, set()).add("formula-latex")
        return region["id"]

    def _normalize_header_footer(
        self,
        raw: dict[str, Any],
        raw_path: str,
        *,
        parent_id: str | None,
    ) -> str:
        region = self._base_region(raw, raw_path, parent_id=parent_id)
        raw_type = raw.get("type", "unknown")
        region["artifact"] = {"isArtifact": False, "reason": raw_type}
        region["childIds"] = self._normalize_kids(raw, raw_path, region["id"])
        self.regions[region["id"]] = region
        self._register_region(region["id"], raw)
        self.region_reasons.setdefault(region["id"], set()).add("possible-artifact")
        return region["id"]

    def _normalize_kids(self, raw: dict[str, Any], raw_path: str, parent_id: str) -> list[str]:
        child_ids: list[str] = []
        for index, child in enumerate(raw.get("kids") or []):
            child_id = self._normalize_element(
                child,
                _path_join(_path_join(raw_path, "kids"), index),
                parent_id=parent_id,
            )
            if child_id is not None:
                child_ids.append(child_id)
        return child_ids

    def _base_region(
        self,
        raw: dict[str, Any],
        raw_path: str,
        *,
        parent_id: str | None,
    ) -> dict[str, Any]:
        raw_type = raw.get("type", "unknown")
        page_number = _int_or_default(raw.get("page number"), 1)
        region_id = _region_id(raw, raw_path, page_number)
        raw_ref = {
            "source": "opendataloader",
            "rawPath": raw_path,
            "rawType": raw_type,
        }
        if isinstance(raw.get("id"), int):
            raw_ref["rawId"] = raw["id"]

        region = {
            "id": region_id,
            "rawRef": raw_ref,
            "pageId": f"page:{page_number}",
            "type": _region_type(raw_type),
            "pdfRole": _pdf_role(raw),
            "bbox": _normalize_bbox(raw.get("bounding box")),
            "childIds": [],
            "artifact": {"isArtifact": False},
            "provenance": [_provenance(raw, self.raw_document)],
            "review": _review_status(set()),
        }
        if parent_id is not None:
            region["parentId"] = parent_id

        if not isinstance(raw.get("id"), int):
            self.region_reasons.setdefault(region_id, set()).add("missing-raw-id")
        confidence = raw.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < self.low_confidence_threshold:
            self.region_reasons.setdefault(region_id, set()).add("low-confidence")

        return region

    def _register_region(self, region_id: str, raw: dict[str, Any]) -> None:
        raw_id = raw.get("id")
        if isinstance(raw_id, int) and raw_id not in self.raw_id_to_region_id:
            self.raw_id_to_region_id[raw_id] = region_id
        page_id = self.regions[region_id]["pageId"]
        self.page_region_ids.setdefault(page_id, []).append(region_id)

    def _resolve_caption_targets(self) -> None:
        for caption_id, linked_raw_id in self.pending_caption_targets:
            target_region_id = self.raw_id_to_region_id.get(linked_raw_id)
            if target_region_id is None:
                self.caption_reasons.setdefault(caption_id, set()).add("caption-link")
            else:
                self.captions[caption_id]["targetRegionId"] = target_region_id
                self.captions[caption_id]["confidence"] = 1.0

    def _apply_review_statuses(self) -> None:
        for region_id, region in self.regions.items():
            region["review"] = _review_status(self.region_reasons.get(region_id, set()))
        for table_id, table in self.tables.items():
            table["review"] = _review_status(self.table_reasons.get(table_id, set()))
        for list_id, list_model in self.lists.items():
            list_model["review"] = _review_status(self.list_reasons.get(list_id, set()))
        for asset_id, asset in self.assets.items():
            asset["review"] = _review_status(self.asset_reasons.get(asset_id, set()))
        for caption_id, caption in self.captions.items():
            caption["review"] = _review_status(self.caption_reasons.get(caption_id, set()))

    def _build_pages(self) -> list[dict[str, Any]]:
        declared_page_count = _int_or_default(self.raw_document.get("number of pages"), 0)
        discovered_page_numbers = [
            int(page_id.removeprefix("page:")) for page_id in self.page_region_ids
        ]
        page_count = max(
            [declared_page_count, *discovered_page_numbers],
            default=declared_page_count,
        )
        return [
            {
                "id": f"page:{page_number}",
                "number": page_number,
                "regionIds": self.page_region_ids.get(f"page:{page_number}", []),
            }
            for page_number in range(1, page_count + 1)
        ]

    def _build_review_queue(self) -> list[dict[str, Any]]:
        queue: list[dict[str, Any]] = []
        self._append_review_items(queue, self.region_reasons, "regionId")
        self._append_review_items(queue, self.table_reasons, "tableId")
        self._append_review_items(queue, self.list_reasons, "listId")
        self._append_review_items(queue, self.asset_reasons, "assetId")
        self._append_review_items(queue, self.caption_reasons, "captionId")
        return queue

    @staticmethod
    def _append_review_items(
        queue: list[dict[str, Any]],
        reasons_by_target: dict[str, set[str]],
        target_key: str,
    ) -> None:
        for target_id in sorted(reasons_by_target):
            for reason in sorted(reasons_by_target[target_id]):
                queue.append(
                    {
                        "id": f"review:{reason}:{target_key}:{target_id}",
                        "category": reason,
                        target_key: target_id,
                        "priority": _REVIEW_PRIORITY.get(reason, "medium"),
                        "state": "open",
                    }
                )


def _raw_hash(raw_document: dict[str, Any]) -> str:
    payload = json.dumps(
        raw_document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _region_id(raw: dict[str, Any], raw_path: str, page_number: int) -> str:
    raw_id = raw.get("id")
    if isinstance(raw_id, int):
        return f"region:odl:{raw_id}"
    raw_path_hash = hashlib.sha256(raw_path.encode("utf-8")).hexdigest()[:16]
    return f"region:page:{page_number}:path:{raw_path_hash}"


def _normalize_bbox(raw_bbox: Any) -> dict[str, Any]:
    if not isinstance(raw_bbox, list | tuple) or len(raw_bbox) != 4:
        left = bottom = right = top = 0
    else:
        left, bottom, right, top = raw_bbox
    return {
        "left": left,
        "bottom": bottom,
        "right": right,
        "top": top,
        "unit": "pt",
        "origin": "bottom-left",
    }


def _text_payload(raw: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {"content": raw.get("content", "")}
    if raw.get("font") is not None:
        payload["font"] = raw["font"]
    if raw.get("font size") is not None:
        payload["fontSize"] = raw["font size"]
    if raw.get("text color") is not None:
        payload["textColor"] = raw["text color"]
    if raw.get("hidden text") is not None:
        payload["hidden"] = bool(raw["hidden text"])
    return payload


def _image_alt_text(raw: dict[str, Any]) -> dict[str, Any] | None:
    if raw.get("alt"):
        return {
            "value": raw["alt"],
            "source": "raw-alt",
            "verified": False,
        }
    if raw.get("description"):
        return {
            "value": raw["description"],
            "source": "raw-description",
            "verified": False,
        }
    caption = raw.get("caption")
    if isinstance(caption, dict) and caption.get("text"):
        return {
            "value": caption["text"],
            "source": "hybrid-generated",
            "verified": False,
        }
    return None


def _region_type(raw_type: str) -> str:
    return {
        "paragraph": "paragraph",
        "heading": "heading",
        "caption": "caption",
        "table": "table",
        "table cell": "tableCell",
        "text block": "textBlock",
        "list": "list",
        "list item": "listItem",
        "image": "figure",
        "formula": "formula",
        "header": "header",
        "footer": "footer",
    }.get(raw_type, "unknown")


def _pdf_role(raw: dict[str, Any]) -> str:
    raw_type = raw.get("type")
    if raw_type == "heading":
        heading_level = raw.get("heading level")
        if isinstance(heading_level, int) and 1 <= heading_level <= 6:
            return f"H{heading_level}"
        return "Unknown"
    return {
        "paragraph": "P",
        "caption": "Caption",
        "table": "Table",
        "table cell": "TD",
        "text block": "Div",
        "list": "L",
        "list item": "LI",
        "image": "Figure",
        "formula": "Formula",
        "header": "Artifact",
        "footer": "Artifact",
    }.get(raw_type, "Unknown")


def _provenance(raw: dict[str, Any], raw_document: dict[str, Any]) -> dict[str, Any]:
    raw_type = raw.get("type", "unknown")
    source = "hybrid" if _has_hybrid_evidence(raw, raw_document) else "opendataloader-local"
    provenance: dict[str, Any] = {
        "source": source,
        "rawType": raw_type,
    }
    if isinstance(raw.get("id"), int):
        provenance["rawId"] = raw["id"]
    if isinstance(raw.get("confidence"), (int, float)):
        provenance["confidence"] = raw["confidence"]

    details: dict[str, Any] = {}
    detail_fields = {
        "source label": "sourceLabel",
        "heading inference": "headingInference",
        "tsr": "tsr",
        "caption": "caption",
        "regionlist resolution": "regionlistResolution",
        "word match": "wordMatch",
        "text source": "textSource",
        "stream ocr similarity": "streamOcrSimilarity",
    }
    for raw_key, detail_key in detail_fields.items():
        if raw.get(raw_key) is not None:
            details[detail_key] = raw[raw_key]
    if raw.get("alt") is not None:
        details["rawAlt"] = raw["alt"]
    if raw.get("description") is not None:
        details["rawDescription"] = raw["description"]
    if raw.get("type") not in {
        "paragraph",
        "heading",
        "caption",
        "table",
        "table cell",
        "text block",
        "list",
        "list item",
        "image",
        "formula",
        "header",
        "footer",
    }:
        details["raw"] = raw
    if details:
        provenance["details"] = details
    return provenance


def _has_hybrid_evidence(raw: dict[str, Any], raw_document: dict[str, Any]) -> bool:
    if raw_document.get("hybrid") is not None:
        return True
    return any(
        raw.get(key) is not None
        for key in (
            "confidence",
            "source label",
            "tsr",
            "caption",
            "regionlist resolution",
            "word match",
            "text source",
            "stream ocr similarity",
        )
    )


def _review_status(reasons: set[str]) -> dict[str, Any]:
    ordered_reasons = sorted(reasons)
    return {
        "state": "needs-review" if ordered_reasons else "approved",
        "reasons": ordered_reasons,
        "updatedBy": "system",
    }


def _path_join(raw_path: str, token: str | int) -> str:
    return f"{raw_path}/{_escape_path_token(str(token))}"


def _escape_path_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _int_or_default(value: Any, default: int) -> int:
    return value if isinstance(value, int) else default
