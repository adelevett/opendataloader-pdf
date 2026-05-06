"""Minimal FastAPI prototype for RemediPDF structure operations.

The API delegates all state handling to RemediDocumentService and only
translates service errors into HTTP responses.
"""

from json import JSONDecodeError
from typing import Any

from .remedipdf_service import (
    InMemoryRemediDocumentStore,
    RemediDocumentService,
    RemediDocumentServiceError,
    RemediDocumentStore,
)

__all__ = ["create_app"]


def create_app(
    *,
    service: RemediDocumentService | None = None,
    store: RemediDocumentStore | None = None,
):
    """Create a FastAPI app backed by RemediDocumentService."""

    if service is not None and store is not None:
        raise ValueError("Pass either service or store, not both.")

    if service is None:
        service = RemediDocumentService(store or InMemoryRemediDocumentStore())

    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(title="RemediPDF API", version="0.1.0")

    @app.exception_handler(RemediDocumentServiceError)
    async def handle_service_error(_request: Request, exc: RemediDocumentServiceError):
        return JSONResponse(status_code=exc.status_code, content=exc.to_error_response())

    def invalid_document_error(document_id: str, message: str):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "invalid_document_id",
                    "message": message,
                    "documentId": document_id,
                }
            },
        )

    def invalid_patch_error(document_id: str, message: str):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "invalid_patch_schema",
                    "message": message,
                    "documentId": document_id,
                }
            },
        )

    @app.get("/documents/{document_id}/structure")
    async def get_structure(document_id: str):
        try:
            return service.get_structure(document_id)
        except ValueError as exc:
            return invalid_document_error(document_id, str(exc))

    @app.patch("/documents/{document_id}/structure")
    async def patch_structure(document_id: str, request: Request):
        try:
            body: Any = await request.json()
        except JSONDecodeError:
            return invalid_patch_error(document_id, "PatchSet body is not valid JSON.")

        try:
            return service.patch_structure(document_id, body)
        except ValueError as exc:
            return invalid_document_error(document_id, str(exc))

    @app.get("/documents/{document_id}/review-queue")
    async def get_review_queue(document_id: str):
        try:
            return service.get_review_queue(document_id)
        except ValueError as exc:
            return invalid_document_error(document_id, str(exc))

    return app
