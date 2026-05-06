import base64
import json
import shutil
from pathlib import Path

from opendataloader_pdf import (
    FileSystemPageImageStore,
    InMemoryRemediDocumentStore,
    JsonFileRemediDocumentStore,
    RemediDocumentNotFoundError,
    RemediDocumentService,
    RemediDocumentServiceError,
    PAGE_RENDER_INFO_SCHEMA,
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


def _assert_service_error(func, *, code, status_code):
    try:
        func()
    except RemediDocumentServiceError as exc:
        assert exc.code == code
        assert exc.status_code == status_code
        return exc
    raise AssertionError("Expected RemediDocumentServiceError")


def _write_cached_page(cache_dir: Path, document_id: str, page_number: int) -> tuple[Path, bytes]:
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
    return page_dir, png_bytes


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


def test_get_page_overlay_returns_viewer_ready_regions_and_validates_page_number():
    raw = _raw_doc(
        _text_element("heading", 1, "Heading", **{"heading level": 1}),
        {
            "type": "image",
            "id": 2,
            "page number": 1,
            "bounding box": [10, 20, 30, 40],
            "alt": "Image alt",
        },
    )
    raw["number of pages"] = 2
    document = normalize_opendataloader_document(raw, document_id="doc:service")
    service = RemediDocumentService(InMemoryRemediDocumentStore({document["documentId"]: document}))

    overlay = service.get_page_overlay("doc:service", "1")

    assert overlay["schema"] == "remedipdf.page-overlay.v0"
    assert overlay["documentId"] == "doc:service"
    assert overlay["pageNumber"] == 1
    assert overlay["pageId"] == "page:1"
    assert overlay["pageSize"] is None
    assert overlay["regions"][0]["regionId"] == "region:odl:1"
    assert overlay["regions"][0]["readingOrderIndex"] == 0
    assert overlay["regions"][0]["textPreview"] == "Heading"
    assert overlay["regions"][1]["assetId"] == "asset:region:odl:2"
    assert overlay["regions"][1]["textPreview"] == "Image alt"
    assert overlay["regions"][1]["review"]["reasons"] == ["generated-alt-text"]

    empty_overlay = service.get_page_overlay("doc:service", 2)
    assert empty_overlay["regions"] == []

    exc = _assert_service_error(
        lambda: service.get_page_overlay("doc:service", "0"),
        code="invalid_page_number",
        status_code=400,
    )
    assert exc.document_id == "doc:service"
    assert exc.details["pageNumber"] == 0


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


def test_page_image_store_returns_image_and_render_info():
    document_id = "doc-render"
    raw = _raw_doc(_text_element("paragraph", 1, "Body"))
    document = normalize_opendataloader_document(raw, document_id=document_id)

    temp_dir = Path(__file__).resolve().parent / "temp-page-cache"
    temp_dir.mkdir(exist_ok=True)
    try:
        _, png_bytes = _write_cached_page(temp_dir, document_id, 1)
        service = RemediDocumentService(
            InMemoryRemediDocumentStore({document["documentId"]: document}),
            FileSystemPageImageStore(temp_dir),
        )

        image = service.get_page_image(document_id, 1)
        assert image["contentType"] == "image/png"
        assert Path(image["path"]).read_bytes() == png_bytes

        render_info = service.get_page_render_info(document_id, 1)
        assert render_info["schema"] == PAGE_RENDER_INFO_SCHEMA
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

        invalid_page = _assert_service_error(
            lambda: service.get_page_render_info(document_id, "0"),
            code="invalid_page_number",
            status_code=400,
        )
        assert invalid_page.document_id == document_id
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_page_image_store_reports_missing_image_explicitly():
    document_id = "doc-render"
    raw = _raw_doc(_text_element("paragraph", 1, "Body"))
    document = normalize_opendataloader_document(raw, document_id=document_id)
    temp_dir = Path(__file__).resolve().parent / "temp-page-cache-missing"
    temp_dir.mkdir(exist_ok=True)
    try:
        service = RemediDocumentService(
            InMemoryRemediDocumentStore({document["documentId"]: document}),
            FileSystemPageImageStore(temp_dir),
        )

        exc = _assert_service_error(
            lambda: service.get_page_image(document_id, 1),
            code="page_image_not_available",
            status_code=404,
        )
        assert exc.document_id == document_id
        assert exc.details["pageNumber"] == 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
