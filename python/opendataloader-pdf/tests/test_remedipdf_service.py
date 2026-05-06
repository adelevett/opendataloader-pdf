import shutil
from pathlib import Path

from opendataloader_pdf import (
    InMemoryRemediDocumentStore,
    JsonFileRemediDocumentStore,
    RemediDocumentNotFoundError,
    RemediDocumentService,
    RemediPatchApplicationError,
    normalize_opendataloader_document,
)


def _raw_doc(*kids):
    return {
        "file name": "service.pdf",
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


def _patch_set(doc, *operations):
    normalized_ops = []
    for index, operation in enumerate(operations, start=1):
        item = {"opId": f"op:{index}", "timestamp": "2026-05-06T00:00:00Z"}
        item.update(operation)
        normalized_ops.append(item)
    return {
        "schema": "remedipdf.patch.v0",
        "documentId": doc["documentId"],
        "baseRawHash": doc["source"]["rawHash"],
        "patchSetId": "patchset:service",
        "createdAt": "2026-05-06T00:00:01Z",
        "author": {"kind": "user", "id": "user:test"},
        "operations": normalized_ops,
    }


def _operation(op, target, value=None):
    payload = {"op": op, "target": target}
    if value is not None:
        payload["value"] = value
    return payload


def _assert_raises_value_error(func, message_part):
    try:
        func()
    except ValueError as exc:
        assert message_part in str(exc)
        return
    raise AssertionError("Expected ValueError")


def test_patch_structure_persists_document_and_returns_response_shape():
    raw = _raw_doc(
        _text_element("heading", 1, "Heading", **{"heading level": 1}),
        {
            "type": "image",
            "id": 2,
            "page number": 1,
            "bounding box": [10, 20, 30, 40],
        },
    )
    document = normalize_opendataloader_document(raw, document_id="doc:service")
    store = InMemoryRemediDocumentStore({document["documentId"]: document})
    service = RemediDocumentService(store)

    response = service.patch_structure(
        "doc:service",
        _patch_set(
            document,
            _operation("setHeadingLevel", {"regionId": "region:odl:1"}, {"level": 4}),
            _operation(
                "setAltText",
                {"assetId": "asset:region:odl:2"},
                {"value": "A service test image", "verified": True},
            ),
        ),
    )

    persisted = store.load("doc:service")
    assert persisted is not None
    assert persisted["regions"]["region:odl:1"]["pdfRole"] == "H4"
    assert persisted["assets"]["asset:region:odl:2"]["altText"]["verified"] is True
    assert response["schema"] == "remedipdf.structure.patch-response.v0"
    assert response["documentId"] == "doc:service"
    assert response["appliedPatchSetId"] == "patchset:service"
    assert response["patches"]["count"] == 1
    assert response["document"]["regions"]["region:odl:1"]["pdfRole"] == "H4"
    assert response["document"]["patches"]["latestPatchSetId"] == "patchset:service"
    assert service.get_review_queue("doc:service")["counts"]["open"] == 0


def test_patch_structure_raises_document_not_found():
    service = RemediDocumentService(InMemoryRemediDocumentStore())

    try:
        service.patch_structure(
            "doc:missing",
            {
                "schema": "remedipdf.patch.v0",
                "documentId": "doc:missing",
                "baseRawHash": "sha256:missing",
                "patchSetId": "patchset:missing",
                "createdAt": "2026-05-06T00:00:00Z",
                "author": {"kind": "user"},
                "operations": [],
            },
        )
    except RemediDocumentNotFoundError as exc:
        assert exc.code == "document_not_found"
        assert exc.document_id == "doc:missing"
        assert exc.status_code == 404
        return
    raise AssertionError("Expected RemediDocumentNotFoundError")


def test_patch_structure_raises_document_id_mismatch():
    document = normalize_opendataloader_document(_raw_doc(_text_element("paragraph", 1, "Body")))
    service = RemediDocumentService(InMemoryRemediDocumentStore({document["documentId"]: document}))

    patch_set = _patch_set(document, _operation("setMetadata", {"document": True}, {"title": "x"}))
    patch_set["documentId"] = "doc:other"

    try:
        service.patch_structure("doc:service", patch_set)
    except RemediPatchApplicationError as exc:
        assert exc.code == "invalid_patch_schema"
        assert exc.document_id == "doc:service"
        assert exc.status_code == 400
        return
    raise AssertionError("Expected RemediPatchApplicationError")


def test_service_rejects_invalid_document_ids():
    service = RemediDocumentService(InMemoryRemediDocumentStore())

    _assert_raises_value_error(lambda: service.get_structure("../evil"), "invalid")


def test_json_file_store_round_trips_document():
    document = normalize_opendataloader_document(_raw_doc(_text_element("paragraph", 1, "Body")))

    temp_dir = Path(__file__).resolve().parent / "temp-service-store"
    temp_dir.mkdir(exist_ok=True)
    try:
        store = JsonFileRemediDocumentStore(temp_dir)
        store.save(document)
        loaded = store.load(document["documentId"])
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    assert loaded is not None
    assert loaded["documentId"] == document["documentId"]


def test_json_file_store_rejects_invalid_document_ids():
    temp_dir = Path(__file__).resolve().parent / "temp-service-store-invalid"
    temp_dir.mkdir(exist_ok=True)
    try:
        store = JsonFileRemediDocumentStore(temp_dir)
        _assert_raises_value_error(
            lambda: store.save({"documentId": "../evil", "schema": "remedipdf.intermediate.v0"}),
            "invalid",
        )
        _assert_raises_value_error(lambda: store.load("../evil"), "invalid")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
