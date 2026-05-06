"""RemediPDF document service helpers.

This module wires the patch engine into a storage-backed document service.
It stays library-only so it can be reused by a future HTTP layer.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .remedipdf import RemediPatchError, apply_patch_set

PATCH_RESPONSE_SCHEMA = "remedipdf.structure.patch-response.v0"
REVIEW_QUEUE_RESPONSE_SCHEMA = "remedipdf.review-queue.v0"
PAGE_OVERLAY_RESPONSE_SCHEMA = "remedipdf.page-overlay.v0"
PAGE_RENDER_INFO_SCHEMA = "remedipdf.page-render-info.v0"

_SAFE_DOCUMENT_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")
_DOCUMENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
_PAGE_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
_PAGE_IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

__all__ = [
    "PATCH_RESPONSE_SCHEMA",
    "REVIEW_QUEUE_RESPONSE_SCHEMA",
    "PAGE_OVERLAY_RESPONSE_SCHEMA",
    "PAGE_RENDER_INFO_SCHEMA",
    "RemediDocumentServiceError",
    "RemediDocumentNotFoundError",
    "RemediPatchApplicationError",
    "RemediPageImageNotAvailableError",
    "RemediDocumentStore",
    "RemediPageRenderStore",
    "InMemoryRemediDocumentStore",
    "JsonFileRemediDocumentStore",
    "FileSystemPageImageStore",
    "RemediDocumentService",
]


def _validate_document_id(document_id: str) -> str:
    if (
        not isinstance(document_id, str)
        or not document_id
        or document_id in {".", ".."}
        or _DOCUMENT_ID_RE.fullmatch(document_id) is None
    ):
        raise ValueError("Document identifier is invalid.")
    return document_id


def _status_code_for_service_error(code: str) -> int:
    return {
        "document_not_found": 404,
        "invalid_patch_schema": 400,
        "invalid_page_number": 400,
        "page_image_not_available": 404,
        "raw_hash_mismatch": 409,
        "unknown_target_id": 422,
        "unsupported_operation": 422,
        "patch_conflict": 409,
        "invalid_document_id": 400,
    }.get(code, 400)


class RemediDocumentServiceError(Exception):
    """Base error for service-layer document operations."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
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
        self.status_code = status_code if status_code is not None else _status_code_for_service_error(code)

    def to_error_response(self) -> dict[str, Any]:
        error: dict[str, Any] = {
            "code": self.code,
            "message": str(self),
        }
        if self.document_id is not None:
            error["documentId"] = self.document_id
        if self.patch_set_id is not None:
            error["patchSetId"] = self.patch_set_id
        if self.op_id is not None:
            error["opId"] = self.op_id
        if self.target is not None:
            error["target"] = self.target
        if self.details:
            error["details"] = self.details
        return {"error": error}


class RemediDocumentNotFoundError(RemediDocumentServiceError):
    def __init__(self, document_id: str) -> None:
        super().__init__(
            "document_not_found",
            "Document was not found.",
            document_id=document_id,
            status_code=404,
        )


class RemediPatchApplicationError(RemediDocumentServiceError):
    pass


class RemediPageImageNotAvailableError(RemediDocumentServiceError):
    def __init__(self, document_id: str, page_number: int, *, details: dict[str, Any] | None = None):
        merged_details = {"pageNumber": page_number}
        if details:
            merged_details.update(details)
        super().__init__(
            "page_image_not_available",
            "Page image is not available.",
            document_id=document_id,
            details=merged_details,
            status_code=404,
        )


@runtime_checkable
class RemediDocumentStore(Protocol):
    def load(self, document_id: str) -> dict[str, Any] | None:
        """Return a stored RemediDocument or None if absent."""

    def save(self, document: dict[str, Any]) -> None:
        """Persist a RemediDocument."""


@runtime_checkable
class RemediPageRenderStore(Protocol):
    def resolve_image(self, document_id: str, page_number: int) -> dict[str, Any] | None:
        """Return cached page image metadata or None if missing."""

    def resolve_render_info(self, document_id: str, page_number: int) -> dict[str, Any] | None:
        """Return cached page render metadata or None if missing."""


class InMemoryRemediDocumentStore:
    """Simple in-memory store for tests and local tooling."""

    def __init__(self, documents: dict[str, dict[str, Any]] | None = None) -> None:
        self._documents = {
            document_id: deepcopy(document)
            for document_id, document in (documents or {}).items()
        }

    def load(self, document_id: str) -> dict[str, Any] | None:
        _validate_document_id(document_id)
        document = self._documents.get(document_id)
        return deepcopy(document) if document is not None else None

    def save(self, document: dict[str, Any]) -> None:
        if not isinstance(document, dict):
            raise ValueError("Document body must be an object.")
        document_id = document.get("documentId")
        _validate_document_id(document_id)
        self._documents[document_id] = deepcopy(document)


class JsonFileRemediDocumentStore:
    """Store each RemediDocument as JSON under a directory."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def load(self, document_id: str) -> dict[str, Any] | None:
        path = self._path_for_document_id(document_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, document: dict[str, Any]) -> None:
        if not isinstance(document, dict):
            raise ValueError("Document body must be an object.")
        document_id = document.get("documentId")
        path = self._path_for_document_id(document_id)
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False),
            encoding="utf-8",
        )

    def _path_for_document_id(self, document_id: str) -> Path:
        _validate_document_id(document_id)
        safe_document_id = _SAFE_DOCUMENT_ID_RE.sub("_", document_id).strip("_")
        path = (self.base_dir / f"{safe_document_id or 'document'}.json").resolve()
        if not path.is_relative_to(self.base_dir):
            raise ValueError("Document identifier resolves outside the base directory.")
        return path


class FileSystemPageImageStore:
    """Resolve cached page images and render metadata from a directory tree."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def resolve_image(self, document_id: str, page_number: int) -> dict[str, Any] | None:
        page_dir = self._page_dir_for_document_id(document_id)
        for extension in _PAGE_IMAGE_EXTENSIONS:
            image_path = page_dir / f"page-{page_number}{extension}"
            if image_path.is_file():
                return {
                    "path": str(image_path),
                    "contentType": _PAGE_IMAGE_CONTENT_TYPES[extension],
                }
        return None

    def resolve_render_info(self, document_id: str, page_number: int) -> dict[str, Any] | None:
        page_dir = self._page_dir_for_document_id(document_id)
        image = self.resolve_image(document_id, page_number)
        if image is None:
            return None

        metadata_path = page_dir / f"page-{page_number}.json"
        if not metadata_path.is_file():
            return None

        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        page_size = metadata.get("pageSize")
        if not isinstance(page_size, dict):
            return None
        width = page_size.get("width")
        height = page_size.get("height")
        unit = page_size.get("unit")
        image_width = metadata.get("imageWidth")
        image_height = metadata.get("imageHeight")
        if (
            not isinstance(width, (int, float))
            or not isinstance(height, (int, float))
            or unit != "pt"
            or not isinstance(image_width, (int, float))
            or not isinstance(image_height, (int, float))
            or width <= 0
            or height <= 0
            or image_width <= 0
            or image_height <= 0
        ):
            return None

        scale_x = image_width / width
        scale_y = image_height / height
        scale = scale_x if abs(scale_x - scale_y) < 1e-9 else None

        return {
            "schema": PAGE_RENDER_INFO_SCHEMA,
            "documentId": document_id,
            "pageNumber": page_number,
            "pageId": f"page:{page_number}",
            "pageSize": {
                "width": width,
                "height": height,
                "unit": "pt",
            },
            "imageWidth": image_width,
            "imageHeight": image_height,
            "scale": scale,
            "coordinateSystem": "pdf-bottom-left",
            "overlayCoordinateSystem": "css-top-left",
            "transform": {
                "scaleX": scale_x,
                "scaleY": scale_y,
                "left": "bbox.left * scaleX",
                "top": "(pageSize.height - bbox.top) * scaleY",
                "width": "(bbox.right - bbox.left) * scaleX",
                "height": "(bbox.top - bbox.bottom) * scaleY",
            },
        }

    def _page_dir_for_document_id(self, document_id: str) -> Path:
        _validate_document_id(document_id)
        safe_document_id = _SAFE_DOCUMENT_ID_RE.sub("_", document_id).strip("_")
        page_dir = (self.base_dir / (safe_document_id or "document")).resolve()
        if not page_dir.is_relative_to(self.base_dir):
            raise ValueError("Document identifier resolves outside the base directory.")
        return page_dir


class RemediDocumentService:
    """Load, patch, and persist RemediDocuments through a storage backend."""

    def __init__(
        self,
        store: RemediDocumentStore,
        page_image_store: RemediPageRenderStore | None = None,
    ) -> None:
        self.store = store
        self.page_image_store = page_image_store

    def get_structure(self, document_id: str) -> dict[str, Any]:
        document = self._load_document(document_id)
        return deepcopy(document)

    def patch_structure(
        self,
        document_id: str,
        patch_set: dict[str, Any],
    ) -> dict[str, Any]:
        _validate_document_id(document_id)
        if not isinstance(patch_set, dict):
            raise RemediPatchApplicationError(
                "invalid_patch_schema",
                "PatchSet body must be an object.",
                document_id=document_id,
                status_code=400,
            )
        if patch_set.get("documentId") != document_id:
            raise RemediPatchApplicationError(
                "invalid_patch_schema",
                "PatchSet.documentId does not match RemediDocument.documentId.",
                document_id=document_id,
                patch_set_id=patch_set.get("patchSetId"),
                details={
                    "expectedDocumentId": document_id,
                    "actualDocumentId": patch_set.get("documentId"),
                },
                status_code=400,
            )

        document = self._load_document(document_id)
        try:
            updated_document = apply_patch_set(document, patch_set)
        except RemediPatchError as exc:
            raise self._translate_patch_error(document_id, patch_set, exc) from exc

        self.store.save(updated_document)
        return _build_patch_response(updated_document, patch_set["patchSetId"])

    def get_review_queue(self, document_id: str) -> dict[str, Any]:
        document = self._load_document(document_id)
        return _build_review_queue_response(document)

    def get_page_overlay(self, document_id: str, page_number: Any) -> dict[str, Any]:
        document, page_number_int = self._load_page(document_id, page_number)
        return _build_page_overlay_response(document, page_number_int)

    def get_page_image(self, document_id: str, page_number: Any) -> dict[str, Any]:
        document, page_number_int = self._load_page(document_id, page_number)
        if self.page_image_store is None:
            raise RemediPageImageNotAvailableError(document_id, page_number_int)
        image = self.page_image_store.resolve_image(document_id, page_number_int)
        if image is None:
            raise RemediPageImageNotAvailableError(document_id, page_number_int)
        return image

    def get_page_render_info(self, document_id: str, page_number: Any) -> dict[str, Any]:
        document, page_number_int = self._load_page(document_id, page_number)
        if self.page_image_store is None:
            raise RemediPageImageNotAvailableError(document_id, page_number_int)
        render_info = self.page_image_store.resolve_render_info(document_id, page_number_int)
        if render_info is None:
            raise RemediPageImageNotAvailableError(document_id, page_number_int)
        return render_info

    def _load_document(self, document_id: str) -> dict[str, Any]:
        _validate_document_id(document_id)
        document = self.store.load(document_id)
        if document is None:
            raise RemediDocumentNotFoundError(document_id)
        return document

    def _load_page(self, document_id: str, page_number: Any) -> tuple[dict[str, Any], int]:
        document = self._load_document(document_id)
        page_number_int = _parse_page_number(page_number, document_id=document_id)
        return document, page_number_int

    @staticmethod
    def _translate_patch_error(
        document_id: str,
        patch_set: dict[str, Any],
        error: RemediPatchError,
    ) -> RemediPatchApplicationError:
        code = error.code or "patch_conflict"
        message = str(error)
        details = dict(error.details)
        if code == "invalid_patch_schema" and "baseRawHash" in message:
            code = "raw_hash_mismatch"
        if code == "patch_conflict":
            if message != "Patch operation conflicts with current document state.":
                details.setdefault("originalMessage", message)
            message = "Patch operation conflicts with current document state."
        if error.target is not None and "target" not in details:
            details["target"] = error.target
        return RemediPatchApplicationError(
            code,
            message,
            document_id=document_id,
            patch_set_id=patch_set.get("patchSetId"),
            op_id=error.op_id,
            target=error.target,
            details=details,
            status_code=error.status_code or _status_code_for_service_error(code),
        )


def _build_patch_response(
    document: dict[str, Any],
    applied_patch_set_id: str,
) -> dict[str, Any]:
    patches = document.get("patches") or {}
    return {
        "schema": PATCH_RESPONSE_SCHEMA,
        "documentId": document["documentId"],
        "appliedPatchSetId": applied_patch_set_id,
        "rawHash": document["source"]["rawHash"],
        "patches": {
            "count": patches.get("count", 0),
            "latestPatchSetId": patches.get("latestPatchSetId", applied_patch_set_id),
            "latestAppliedAt": patches.get("latestAppliedAt"),
        },
        "document": deepcopy(document),
    }


def _build_review_queue_response(document: dict[str, Any]) -> dict[str, Any]:
    items = deepcopy(document.get("reviewQueue") or [])
    counts = {"open": 0, "resolved": 0, "dismissed": 0}
    for item in items:
        state = item.get("state", "open")
        if state in counts:
            counts[state] += 1
    return {
        "schema": REVIEW_QUEUE_RESPONSE_SCHEMA,
        "documentId": document["documentId"],
        "rawHash": document["source"]["rawHash"],
        "items": items,
        "counts": counts,
    }


def _build_page_overlay_response(
    document: dict[str, Any],
    page_number: int,
) -> dict[str, Any]:
    pages = {
        page["number"]: page
        for page in document.get("pages") or []
        if isinstance(page, dict) and isinstance(page.get("number"), int)
    }
    if page_number not in pages:
        raise RemediDocumentServiceError(
            "invalid_page_number",
            "Page number does not exist in the document.",
            document_id=document["documentId"],
            details={
                "pageNumber": page_number,
                "pageCount": len(pages),
            },
            status_code=400,
        )

    page = pages[page_number]
    page_id = f"page:{page_number}"
    reading_order = document.get("readingOrder") if isinstance(document.get("readingOrder"), dict) else {}
    page_order = reading_order.get("pageOrder") if isinstance(reading_order, dict) else {}
    page_region_order = page_order.get(page_id) if isinstance(page_order, dict) else []
    reading_order_index = {
        region_id: index for index, region_id in enumerate(page_region_order or [])
    }

    regions = [
        _build_page_overlay_region(document, region, reading_order_index)
        for region in (document.get("regions") or {}).values()
        if isinstance(region, dict) and region.get("pageId") == page_id
    ]
    regions.sort(
        key=lambda item: (
            item["readingOrderIndex"] is None,
            item["readingOrderIndex"] if item["readingOrderIndex"] is not None else 0,
            -item["bbox"]["top"],
            item["bbox"]["left"],
            item["regionId"],
        )
    )

    return {
        "schema": PAGE_OVERLAY_RESPONSE_SCHEMA,
        "documentId": document["documentId"],
        "pageNumber": page_number,
        "pageId": page_id,
        "pageSize": _page_size_from_page(page),
        "rawHash": document["source"]["rawHash"],
        "regions": regions,
    }


def _build_page_overlay_region(
    document: dict[str, Any],
    region: dict[str, Any],
    reading_order_index: dict[str, int],
) -> dict[str, Any]:
    overlay = {
        "regionId": region["id"],
        "pageId": region["pageId"],
        "bbox": deepcopy(region.get("bbox") or {}),
        "type": region.get("type"),
        "pdfRole": region.get("pdfRole"),
        "textPreview": _text_preview_for_region(document, region),
        "artifact": deepcopy(region.get("artifact") or {"isArtifact": False}),
        "review": deepcopy(_overlay_review_for_region(document, region)),
        "readingOrderIndex": reading_order_index.get(region["id"]),
    }
    for key in ("tableId", "listId", "assetId", "captionId", "parentId"):
        if region.get(key) is not None:
            overlay[key] = region[key]
    if region.get("listItem") is not None:
        overlay["listItem"] = deepcopy(region["listItem"])
    if region.get("childIds"):
        overlay["childIds"] = list(region["childIds"])
    return overlay


def _overlay_review_for_region(
    document: dict[str, Any],
    region: dict[str, Any],
) -> dict[str, Any]:
    region_type = region.get("type")
    if region_type == "table" and region.get("tableId"):
        table = (document.get("tables") or {}).get(region["tableId"])
        if isinstance(table, dict) and isinstance(table.get("review"), dict):
            return table["review"]
    if region_type == "list" and region.get("listId"):
        list_model = (document.get("lists") or {}).get(region["listId"])
        if isinstance(list_model, dict) and isinstance(list_model.get("review"), dict):
            return list_model["review"]
    if region.get("assetId"):
        asset = (document.get("assets") or {}).get(region["assetId"])
        if isinstance(asset, dict) and isinstance(asset.get("review"), dict):
            return asset["review"]
    if region.get("captionId"):
        caption = (document.get("captions") or {}).get(region["captionId"])
        if isinstance(caption, dict) and isinstance(caption.get("review"), dict):
            return caption["review"]
    if isinstance(region.get("review"), dict):
        return region["review"]
    return {"state": "approved", "reasons": [], "updatedBy": "system"}


def _text_preview_for_region(
    document: dict[str, Any],
    region: dict[str, Any],
    *,
    _visited: set[str] | None = None,
) -> str | None:
    visited = _visited or set()
    region_id = region.get("id")
    if isinstance(region_id, str):
        if region_id in visited:
            return None
        visited = set(visited)
        visited.add(region_id)

    text = region.get("text") if isinstance(region.get("text"), dict) else None
    content = text.get("content") if isinstance(text, dict) else None
    if isinstance(content, str) and content.strip():
        return content.strip()

    asset_id = region.get("assetId")
    if isinstance(asset_id, str):
        asset = (document.get("assets") or {}).get(asset_id)
        if isinstance(asset, dict):
            alt_text = asset.get("altText") if isinstance(asset.get("altText"), dict) else None
            if isinstance(alt_text, dict):
                value = alt_text.get("value")
                if isinstance(value, str) and value.strip():
                    return value.strip()
            formula = asset.get("formula") if isinstance(asset.get("formula"), dict) else None
            if isinstance(formula, dict):
                latex = formula.get("latex")
                if isinstance(latex, str) and latex.strip():
                    return latex.strip()
                alt_text = formula.get("altText") if isinstance(formula.get("altText"), dict) else None
                if isinstance(alt_text, dict):
                    value = alt_text.get("value")
                    if isinstance(value, str) and value.strip():
                        return value.strip()

    child_ids = region.get("childIds")
    if isinstance(child_ids, list):
        previews: list[str] = []
        for child_id in child_ids:
            if not isinstance(child_id, str):
                continue
            child_region = (document.get("regions") or {}).get(child_id)
            if not isinstance(child_region, dict):
                continue
            preview = _text_preview_for_region(document, child_region, _visited=visited)
            if preview:
                previews.append(preview)
            if len(" ".join(previews)) > 120:
                break
        if previews:
            text_preview = " ".join(previews).strip()
            return text_preview[:160]

    return None


def _page_size_from_page(page: dict[str, Any]) -> dict[str, Any] | None:
    size = page.get("size")
    if not isinstance(size, dict):
        size = page.get("pageSize")
    if not isinstance(size, dict):
        return None
    width = size.get("width")
    height = size.get("height")
    unit = size.get("unit")
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        return None
    if unit != "pt":
        return None
    return {"width": width, "height": height, "unit": "pt"}


def _parse_page_number(page_number: Any, *, document_id: str | None = None) -> int:
    if isinstance(page_number, bool):
        raise RemediDocumentServiceError(
            "invalid_page_number",
            "Page number must be a positive integer.",
            document_id=document_id,
            details={"pageNumber": page_number},
            status_code=400,
        )
    if isinstance(page_number, int):
        value = page_number
    elif isinstance(page_number, str):
        try:
            value = int(page_number.strip())
        except ValueError as exc:
            raise RemediDocumentServiceError(
                "invalid_page_number",
                "Page number must be a positive integer.",
                document_id=document_id,
                details={"pageNumber": page_number},
                status_code=400,
            ) from exc
    else:
        raise RemediDocumentServiceError(
            "invalid_page_number",
            "Page number must be a positive integer.",
            document_id=document_id,
            details={"pageNumber": page_number},
            status_code=400,
        )
    if value < 1:
        raise RemediDocumentServiceError(
            "invalid_page_number",
            "Page number must be a positive integer.",
            document_id=document_id,
            details={"pageNumber": value},
            status_code=400,
        )
    return value
