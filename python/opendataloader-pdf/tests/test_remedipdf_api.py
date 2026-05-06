from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from opendataloader_pdf import InMemoryRemediDocumentStore, normalize_opendataloader_document
from opendataloader_pdf.remedipdf_api import create_app


def _raw_doc(*kids):
    return {
        "file name": "api.pdf",
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


def _patch_set(doc, *operations, patch_set_id="patchset:api"):
    normalized_ops = []
    for index, operation in enumerate(operations, start=1):
        item = {"opId": f"op:{index}", "timestamp": "2026-05-06T00:00:00Z"}
        item.update(operation)
        normalized_ops.append(item)
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
    payload = {"op": op, "target": target}
    if value is not None:
        payload["value"] = value
    return payload


def _app_with_document(document):
    store = InMemoryRemediDocumentStore({document["documentId"]: document})
    return create_app(store=store)


def _write_cached_page(cache_dir: Path, document_id: str, page_number: int) -> bytes:
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/nXcAAAAASUVORK5CYII="
    )
    page_dir = cache_dir / document_id
    page_dir.mkdir(parents=True, exist_ok=True)
    (page_dir / f"page-{page_number}.png").write_bytes(png_bytes)
    (page_dir / f"page-{page_number}.json").write_text(
        json.dumps(
            {
                "pageSize": {"width": 612, "height": 792, "unit": "pt"},
                "imageWidth": 1224,
                "imageHeight": 1584,
            }
        ),
        encoding="utf-8",
    )
    return png_bytes


async def _request(app, method: str, url: str, **kwargs):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


@pytest.mark.asyncio
async def test_get_structure_returns_normalized_document():
    document = normalize_opendataloader_document(
        _raw_doc(
            _text_element("heading", 1, "Heading", **{"heading level": 1}),
            _text_element("paragraph", 2, "Body"),
        ),
        document_id="doc:api",
    )
    app = _app_with_document(document)

    response = await _request(app, "GET", "/documents/doc:api/structure")

    assert response.status_code == 200
    payload = response.json()
    assert payload["documentId"] == "doc:api"
    assert payload["readingOrder"]["regionIds"] == ["region:odl:1", "region:odl:2"]
    assert payload["reviewQueue"] == []


@pytest.mark.asyncio
async def test_patch_structure_applies_patch_and_updates_review_queue():
    document = normalize_opendataloader_document(
        _raw_doc(
            _text_element("heading", 1, "Heading", **{"heading level": 1}),
            {
                "type": "image",
                "id": 2,
                "page number": 1,
                "bounding box": [10, 20, 30, 40],
            },
        ),
        document_id="doc:api",
    )
    app = _app_with_document(document)

    response = await _request(
        app,
        "PATCH",
        "/documents/doc:api/structure",
        json=_patch_set(
            document,
            _operation(
                "setAltText",
                {"assetId": "asset:region:odl:2"},
                {"value": "An image description", "verified": True},
            ),
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "remedipdf.structure.patch-response.v0"
    assert payload["patches"]["count"] == 1
    assert payload["document"]["assets"]["asset:region:odl:2"]["altText"]["verified"] is True
    assert payload["document"]["reviewQueue"] == []

    queue_response = await _request(app, "GET", "/documents/doc:api/review-queue")
    assert queue_response.status_code == 200
    assert queue_response.json()["counts"]["open"] == 0


@pytest.mark.asyncio
async def test_missing_document_returns_document_not_found():
    app = create_app(store=InMemoryRemediDocumentStore())

    response = await _request(app, "GET", "/documents/doc:missing/structure")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "document_not_found"
    assert payload["error"]["documentId"] == "doc:missing"


@pytest.mark.asyncio
async def test_invalid_patch_body_returns_documented_error():
    document = normalize_opendataloader_document(
        _raw_doc(_text_element("paragraph", 1, "Body")), document_id="doc:api"
    )
    app = _app_with_document(document)

    response = await _request(app, "PATCH", "/documents/doc:api/structure", json=[])

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "invalid_patch_schema"
    assert payload["error"]["message"] == "PatchSet body must be an object."


@pytest.mark.asyncio
async def test_invalid_patch_json_returns_documented_error():
    document = normalize_opendataloader_document(
        _raw_doc(_text_element("paragraph", 1, "Body")), document_id="doc:api"
    )
    app = _app_with_document(document)

    response = await _request(
        app,
        "PATCH",
        "/documents/doc:api/structure",
        content="{not json}",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "invalid_patch_schema"
    assert payload["error"]["message"] == "PatchSet body is not valid JSON."


@pytest.mark.asyncio
async def test_raw_hash_mismatch_unknown_target_and_unsupported_op_errors():
    document = normalize_opendataloader_document(
        _raw_doc(_text_element("paragraph", 1, "Body")), document_id="doc:api"
    )
    app = _app_with_document(document)

    raw_hash_mismatch = _patch_set(document)
    raw_hash_mismatch["baseRawHash"] = "sha256:wrong"
    response = await _request(app, "PATCH", "/documents/doc:api/structure", json=raw_hash_mismatch)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "raw_hash_mismatch"

    unknown_target = _patch_set(
        document,
        _operation("setHeadingLevel", {"regionId": "region:missing"}, {"level": 2}),
    )
    response = await _request(app, "PATCH", "/documents/doc:api/structure", json=unknown_target)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_target_id"

    unsupported = _patch_set(
        document,
        _operation("splitRegion", {"regionId": "region:odl:1"}, {}),
    )
    response = await _request(app, "PATCH", "/documents/doc:api/structure", json=unsupported)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_operation"


@pytest.mark.asyncio
async def test_invalid_document_id_returns_documented_error():
    document = normalize_opendataloader_document(_raw_doc(_text_element("paragraph", 1, "Body")))
    app = _app_with_document(document)

    response = await _request(app, "GET", "/documents/bad%20id/structure")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "invalid_document_id"


@pytest.mark.asyncio
async def test_page_overlay_returns_only_page_regions_and_editor_ids():
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
    raw = _raw_doc(
        _text_element("heading", 1, "Heading", **{"heading level": 1}),
        _text_element("paragraph", 2, "Paragraph"),
        {
            "type": "image",
            "id": 3,
            "page number": 1,
            "bounding box": [10, 20, 30, 40],
            "alt": "Chart alt",
        },
        {
            "type": "formula",
            "id": 4,
            "page number": 1,
            "bounding box": [40, 20, 80, 40],
            "content": r"x+y",
        },
        _text_element("caption", 5, "Figure 1. Chart", **{"linked content id": 3}),
        {
            "type": "header",
            "id": 6,
            "page number": 1,
            "bounding box": [0, 750, 600, 780],
            "kids": [_text_element("paragraph", 7, "Header")],
        },
        {
            "type": "footer",
            "id": 8,
            "page number": 1,
            "bounding box": [0, 0, 600, 30],
            "kids": [_text_element("paragraph", 9, "Footer")],
        },
        table,
        raw_list,
    )
    raw["number of pages"] = 2
    document = normalize_opendataloader_document(raw, document_id="doc:api")
    app = _app_with_document(document)

    response = await _request(app, "GET", "/documents/doc:api/pages/1/overlay")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "remedipdf.page-overlay.v0"
    assert payload["documentId"] == "doc:api"
    assert payload["pageNumber"] == 1
    assert payload["pageId"] == "page:1"
    assert payload["pageSize"] is None
    assert all(item["pageId"] == "page:1" for item in payload["regions"])

    regions = {item["regionId"]: item for item in payload["regions"]}
    assert regions["region:odl:1"]["readingOrderIndex"] == 0
    assert regions["region:odl:2"]["readingOrderIndex"] == 1
    assert regions["region:odl:3"]["readingOrderIndex"] == 2
    assert regions["region:odl:3"]["assetId"] == "asset:region:odl:3"
    assert regions["region:odl:3"]["textPreview"] == "Chart alt"
    assert regions["region:odl:4"]["assetId"] == "asset:region:odl:4"
    assert regions["region:odl:4"]["textPreview"] == r"x+y"
    assert regions["region:odl:5"]["captionId"] == "caption:region:odl:5"
    assert regions["region:odl:5"]["textPreview"] == "Figure 1. Chart"
    assert regions["region:odl:6"]["artifact"] == {"isArtifact": False, "reason": "header"}
    assert regions["region:odl:6"]["review"]["reasons"] == ["possible-artifact"]
    assert regions["region:odl:8"]["artifact"] == {"isArtifact": False, "reason": "footer"}
    assert regions["region:odl:10"]["review"]["reasons"] == [
        "table-headers",
        "table-spans",
    ]
    assert regions["region:odl:10"]["tableId"] == "table:region:odl:10"
    assert regions["region:odl:11"]["tableId"] == "table:region:odl:10"
    assert regions["region:odl:11"]["readingOrderIndex"] is None
    assert regions["region:odl:20"]["listId"] == "list:region:odl:20"
    assert regions["region:odl:21"]["listId"] == "list:region:odl:20"
    assert regions["region:odl:21"]["readingOrderIndex"] is None

    empty_response = await _request(app, "GET", "/documents/doc:api/pages/2/overlay")
    assert empty_response.status_code == 200
    assert empty_response.json()["regions"] == []


@pytest.mark.asyncio
async def test_page_overlay_returns_documented_errors():
    document = normalize_opendataloader_document(
        _raw_doc(_text_element("paragraph", 1, "Body")), document_id="doc:api"
    )
    app = _app_with_document(document)

    missing = await _request(app, "GET", "/documents/doc:missing/pages/1/overlay")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "document_not_found"

    invalid = await _request(app, "GET", "/documents/doc:api/pages/0/overlay")
    assert invalid.status_code == 400
    payload = invalid.json()
    assert payload["error"]["code"] == "invalid_page_number"


@pytest.mark.asyncio
async def test_page_render_info_and_image_return_cached_fixture():
    document_id = "doc-render"
    document = normalize_opendataloader_document(
        _raw_doc(_text_element("paragraph", 1, "Body")), document_id=document_id
    )
    temp_dir = Path(__file__).resolve().parent / "temp-page-cache"
    temp_dir.mkdir(exist_ok=True)
    try:
        png_bytes = _write_cached_page(temp_dir, document_id, 1)
        app = create_app(
            store=InMemoryRemediDocumentStore({document["documentId"]: document}),
            page_image_dir=str(temp_dir),
        )

        render_info_response = await _request(
            app, "GET", f"/documents/{document_id}/pages/1/render-info"
        )
        assert render_info_response.status_code == 200
        render_info = render_info_response.json()
        assert render_info["schema"] == "remedipdf.page-render-info.v0"
        assert render_info["documentId"] == document_id
        assert render_info["pageNumber"] == 1
        assert render_info["pageId"] == "page:1"
        assert render_info["pageSize"] == {"width": 612, "height": 792, "unit": "pt"}
        assert render_info["imageWidth"] == 1224
        assert render_info["imageHeight"] == 1584
        assert render_info["scale"] == 2
        assert render_info["coordinateSystem"] == "pdf-bottom-left"
        assert render_info["overlayCoordinateSystem"] == "css-top-left"
        assert render_info["transform"]["left"] == "bbox.left * scaleX"

        image_response = await _request(app, "GET", f"/documents/{document_id}/pages/1/image")
        assert image_response.status_code == 200
        assert image_response.headers["content-type"].startswith("image/png")
        assert image_response.content == png_bytes
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_page_image_contract_returns_documented_errors():
    document_id = "doc-render"
    document = normalize_opendataloader_document(
        _raw_doc(_text_element("paragraph", 1, "Body")), document_id=document_id
    )
    app = create_app(store=InMemoryRemediDocumentStore({document["documentId"]: document}))

    missing_document = await _request(app, "GET", "/documents/doc-missing/pages/1/image")
    assert missing_document.status_code == 404
    assert missing_document.json()["error"]["code"] == "document_not_found"

    invalid_page = await _request(app, "GET", f"/documents/{document_id}/pages/0/render-info")
    assert invalid_page.status_code == 400
    assert invalid_page.json()["error"]["code"] == "invalid_page_number"

    missing_image = await _request(app, "GET", f"/documents/{document_id}/pages/1/image")
    assert missing_image.status_code == 404
    payload = missing_image.json()
    assert payload["error"]["code"] == "page_image_not_available"
