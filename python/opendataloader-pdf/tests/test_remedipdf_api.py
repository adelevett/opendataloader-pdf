from __future__ import annotations

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
