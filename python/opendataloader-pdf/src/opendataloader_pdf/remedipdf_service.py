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

_SAFE_DOCUMENT_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")
_DOCUMENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]+$")

__all__ = [
    "PATCH_RESPONSE_SCHEMA",
    "REVIEW_QUEUE_RESPONSE_SCHEMA",
    "RemediDocumentServiceError",
    "RemediDocumentNotFoundError",
    "RemediPatchApplicationError",
    "RemediDocumentStore",
    "InMemoryRemediDocumentStore",
    "JsonFileRemediDocumentStore",
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


@runtime_checkable
class RemediDocumentStore(Protocol):
    def load(self, document_id: str) -> dict[str, Any] | None:
        """Return a stored RemediDocument or None if absent."""

    def save(self, document: dict[str, Any]) -> None:
        """Persist a RemediDocument."""


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


class RemediDocumentService:
    """Load, patch, and persist RemediDocuments through a storage backend."""

    def __init__(self, store: RemediDocumentStore) -> None:
        self.store = store

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

    def _load_document(self, document_id: str) -> dict[str, Any]:
        _validate_document_id(document_id)
        document = self.store.load(document_id)
        if document is None:
            raise RemediDocumentNotFoundError(document_id)
        return document

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
