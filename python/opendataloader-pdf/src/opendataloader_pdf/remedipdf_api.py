"""Minimal FastAPI prototype for RemediPDF structure and overlay operations.

The API delegates all state handling to RemediDocumentService and only
translates service errors into HTTP responses.
"""

from json import JSONDecodeError
from typing import Any
from pathlib import Path

from .remedipdf_service import (
    FileSystemPageImageStore,
    InMemoryRemediDocumentStore,
    RemediDocumentService,
    RemediDocumentServiceError,
    RemediDocumentStore,
    RemediPageImageNotAvailableError,
    RemediPageRenderStore,
)

__all__ = ["create_app"]


def create_app(
    *,
    service: RemediDocumentService | None = None,
    store: RemediDocumentStore | None = None,
    page_image_store: RemediPageRenderStore | None = None,
    page_image_dir: str | Path | None = None,
):
    """Create a FastAPI app backed by RemediDocumentService."""

    if service is not None and any(
        option is not None for option in (store, page_image_store, page_image_dir)
    ):
        raise ValueError("Pass either service or stores, not both.")
    if page_image_store is not None and page_image_dir is not None:
        raise ValueError("Pass either page_image_store or page_image_dir, not both.")

    if page_image_store is None and page_image_dir is not None:
        page_image_store = FileSystemPageImageStore(page_image_dir)

    if service is None:
        service = RemediDocumentService(
            store or InMemoryRemediDocumentStore(),
            page_image_store=page_image_store,
        )

    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from fastapi.responses import FileResponse

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

    @app.get("/documents/{document_id}/pages/{pageNumber}/overlay")
    async def get_page_overlay(document_id: str, pageNumber: str):
        try:
            return service.get_page_overlay(document_id, pageNumber)
        except ValueError as exc:
            return invalid_document_error(document_id, str(exc))

    @app.get("/documents/{document_id}/pages/{pageNumber}/render-info")
    async def get_page_render_info(document_id: str, pageNumber: str):
        try:
            return service.get_page_render_info(document_id, pageNumber)
        except ValueError as exc:
            return invalid_document_error(document_id, str(exc))

    @app.get("/documents/{document_id}/pages/{pageNumber}/image")
    async def get_page_image(document_id: str, pageNumber: str):
        try:
            image = service.get_page_image(document_id, pageNumber)
        except ValueError as exc:
            return invalid_document_error(document_id, str(exc))
        except RemediPageImageNotAvailableError as exc:
            return JSONResponse(status_code=exc.status_code, content=exc.to_error_response())
        return FileResponse(image["path"], media_type=image["contentType"])

    return app
