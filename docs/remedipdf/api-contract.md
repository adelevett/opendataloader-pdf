# RemediPDF Structure API Contract v0

This contract defines the HTTP surface for reading and patching RemediPDF structure state. It is a documentation-only contract and does not define a Python API, HTTP server, or patch-engine implementation.

## Schema References

The API uses the normalized schema from [`intermediate-schema.md`](./intermediate-schema.md):

- `RemediDocument`, defined at `intermediate-schema.md:206`, is the response shape for `GET /documents/{id}/structure`.
- `PatchSet`, defined under the Layer 3 patch model in `intermediate-schema.md`, is the request shape for `PATCH /documents/{id}/structure`.
- `ReviewQueueItem`, defined in the review queue section of `intermediate-schema.md`, is the item shape for `GET /documents/{id}/review-queue`.

All request and response bodies use `application/json`.

## Common Types

```ts
type DocumentId = string;

type ErrorCode =
  | "document_not_found"
  | "raw_hash_mismatch"
  | "invalid_patch_schema"
  | "invalid_page_number"
  | "page_image_not_available"
  | "unknown_target_id"
  | "unsupported_operation"
  | "patch_conflict";

type ErrorResponse = {
  error: {
    code: ErrorCode;
    message: string;
    documentId?: DocumentId;
    patchSetId?: string;
    opId?: string;
    target?: {
      regionId?: string;
      tableId?: string;
      tableCellId?: string;
      listId?: string;
      listItemId?: string;
      assetId?: string;
      captionId?: string;
      document?: true;
    };
    details?: Record<string, unknown>;
  };
};
```

## GET /documents/{id}/structure

Returns the current effective RemediPDF structure state for a document.

### Request

```http
GET /documents/{id}/structure
Accept: application/json
```

Path parameters:

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | `DocumentId` | yes | Document identifier. Must match `RemediDocument.documentId` in the response. |

### 200 Response

Shape:

```ts
type GetStructureResponse = RemediDocument;
```

Example:

```json
{
  "schema": "remedipdf.intermediate.v0",
  "documentId": "doc:123",
  "source": {
    "fileName": "sample.pdf",
    "rawSchema": "opendataloader.schema.json",
    "rawHash": "sha256:8f3e1d5a",
    "analyzedAt": "2026-05-06T17:00:00Z"
  },
  "metadata": {
    "title": "Sample",
    "author": null,
    "creationDate": null,
    "modificationDate": null
  },
  "pages": [
    {
      "id": "page:1",
      "number": 1,
      "regionIds": ["region:odl:1"]
    }
  ],
  "regions": {
    "region:odl:1": {
      "id": "region:odl:1",
      "rawRef": {
        "source": "opendataloader",
        "rawId": 1,
        "rawPath": "/kids/0",
        "rawType": "heading"
      },
      "pageId": "page:1",
      "type": "heading",
      "pdfRole": "H1",
      "bbox": {
        "left": 200.891,
        "bottom": 706.938,
        "right": 394.152,
        "top": 745.132,
        "unit": "pt",
        "origin": "bottom-left"
      },
      "text": {
        "content": "Sample",
        "font": "Pretendard-Regular",
        "fontSize": 32.005,
        "textColor": "[0.0]"
      },
        "childIds": [],
        "artifact": {
          "isArtifact": false
        },
        "provenance": [
          {
            "source": "opendataloader-local",
            "rawType": "heading",
            "rawId": 1
          }
      ],
      "review": {
        "state": "approved",
        "reasons": [],
        "updatedBy": "system"
      }
    }
  },
  "readingOrder": {
    "mode": "region-list",
    "regionIds": ["region:odl:1"],
    "pageOrder": {
      "page:1": ["region:odl:1"]
    },
    "provenance": [
      {
        "source": "opendataloader-local"
      }
    ]
  },
  "tables": {},
  "lists": {},
  "assets": {},
  "captions": {},
  "reviewQueue": [],
  "patches": {
    "count": 0
  }
}
```

### Status Codes

| Status | Meaning |
| --- | --- |
| `200 OK` | Structure state was returned. |
| `404 Not Found` | The document does not exist. |

## GET /documents/{id}/pages/{pageNumber}/overlay

Returns viewer-ready overlay data for a single page. The response is derived from the normalized RemediPDF document and includes the page's regions plus the editor identifiers needed by a PAVE-style viewer.

### Request

```http
GET /documents/{id}/pages/{pageNumber}/overlay
Accept: application/json
```

Path parameters:

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | `DocumentId` | yes | Document identifier. |
| `pageNumber` | `number` | yes | Positive page number. Invalid or out-of-range values return `400`. |

### 200 Response

Shape:

```ts
type GetPageOverlayResponse = {
  schema: "remedipdf.page-overlay.v0";
  documentId: DocumentId;
  pageNumber: number;
  pageId: PageId;
  pageSize: { width: number; height: number; unit: "pt" } | null;
  rawHash: string;
  regions: PageOverlayRegion[];
};

type PageOverlayRegion = {
  regionId: RegionId;
  pageId: PageId;
  bbox: BBox;
  type: RegionType;
  pdfRole: PdfRole;
  textPreview: string | null;
  artifact: ArtifactState;
  review: ReviewStatus;
  readingOrderIndex: number | null;
  tableId?: TableId;
  listId?: ListId;
  listItem?: { level: number; ordinal: number; parentItemId?: ListItemId };
  assetId?: AssetId;
  captionId?: CaptionId;
  parentId?: RegionId;
  childIds?: RegionId[];
};
```

`readingOrderIndex` is the zero-based position of the overlay region within `readingOrder.pageOrder[pageId]`. Nested table cells, list items, and other non-top-level regions return `null`.

### Example

```json
{
  "schema": "remedipdf.page-overlay.v0",
  "documentId": "doc:123",
  "pageNumber": 1,
  "pageId": "page:1",
  "pageSize": null,
  "rawHash": "sha256:8f3e1d5a",
  "regions": [
    {
      "regionId": "region:odl:1",
      "pageId": "page:1",
      "bbox": {
        "left": 200.891,
        "bottom": 706.938,
        "right": 394.152,
        "top": 745.132,
        "unit": "pt",
        "origin": "bottom-left"
      },
      "type": "heading",
      "pdfRole": "H1",
      "textPreview": "Sample",
      "artifact": {
        "isArtifact": false
      },
      "review": {
        "state": "approved",
        "reasons": [],
        "updatedBy": "system"
      },
      "readingOrderIndex": 0
    }
  ]
}
```

### Status Codes

| Status | Meaning |
| --- | --- |
| `200 OK` | Page overlay data was returned. |
| `400 Bad Request` | The page number is invalid or out of range. |
| `404 Not Found` | The document does not exist. |

## GET /documents/{id}/pages/{pageNumber}/render-info

Returns render metadata for a cached page image. The endpoint is a contract stub for a PAVE-style viewer and does not rasterize PDFs. The service reads page images and their metadata from a configured cache directory.

### Cache Layout

When configured with `page_image_dir`, the service looks for page assets under a document-specific directory:

```text
<page_image_dir>/<documentId-safe>/page-<pageNumber>.png
<page_image_dir>/<documentId-safe>/page-<pageNumber>.json
```

The JSON sidecar must contain:

```ts
type PageRenderCacheMetadata = {
  pageSize: { width: number; height: number; unit: "pt" };
  imageWidth: number;
  imageHeight: number;
};
```

### Request

```http
GET /documents/{id}/pages/{pageNumber}/render-info
Accept: application/json
```

### 200 Response

Shape:

```ts
type PageRenderInfo = {
  schema: "remedipdf.page-render-info.v0";
  documentId: DocumentId;
  pageNumber: number;
  pageId: PageId;
  pageSize: { width: number; height: number; unit: "pt" };
  imageWidth: number;
  imageHeight: number;
  scale: number | null;
  coordinateSystem: "pdf-bottom-left";
  overlayCoordinateSystem: "css-top-left";
  transform: {
    scaleX: number;
    scaleY: number;
    left: string;
    top: string;
    width: string;
    height: string;
  };
};
```

`scale` is the uniform scale factor when the cached image preserves aspect ratio. When the horizontal and vertical scales differ, `scale` is `null` and the viewer should use `transform.scaleX` and `transform.scaleY`.

The `transform` fields are intended for CSS overlay math:

- `left = bbox.left * scaleX`
- `top = (pageSize.height - bbox.top) * scaleY`
- `width = (bbox.right - bbox.left) * scaleX`
- `height = (bbox.top - bbox.bottom) * scaleY`

### Example

```json
{
  "schema": "remedipdf.page-render-info.v0",
  "documentId": "doc:123",
  "pageNumber": 1,
  "pageId": "page:1",
  "pageSize": {
    "width": 612,
    "height": 792,
    "unit": "pt"
  },
  "imageWidth": 1224,
  "imageHeight": 1584,
  "scale": 2,
  "coordinateSystem": "pdf-bottom-left",
  "overlayCoordinateSystem": "css-top-left",
  "transform": {
    "scaleX": 2,
    "scaleY": 2,
    "left": "bbox.left * scaleX",
    "top": "(pageSize.height - bbox.top) * scaleY",
    "width": "(bbox.right - bbox.left) * scaleX",
    "height": "(bbox.top - bbox.bottom) * scaleY"
  }
}
```

### Status Codes

| Status | Meaning |
| --- | --- |
| `200 OK` | Page render metadata was returned. |
| `400 Bad Request` | The page number is invalid or out of range. |
| `404 Not Found` | The document does not exist or the page image metadata is unavailable. |

## GET /documents/{id}/pages/{pageNumber}/image

Returns the cached page image when the configured cache contains one. This endpoint is a stub for the viewer contract and does not rasterize PDFs.

### Status Codes

| Status | Meaning |
| --- | --- |
| `200 OK` | Cached image was returned. |
| `400 Bad Request` | The page number is invalid or out of range. |
| `404 Not Found` | The document does not exist or the page image is unavailable. |

### Image Error

When no cached image exists, the server returns:

```json
{
  "error": {
    "code": "page_image_not_available",
    "message": "Page image is not available.",
    "documentId": "doc:123",
    "details": {
      "pageNumber": 1
    }
  }
}
```

## PATCH /documents/{id}/structure

Applies one ordered `PatchSet` to the document structure. Patch application is synchronous in this contract: a successful response includes the effective structure after applying the patch set.

### Request

```http
PATCH /documents/{id}/structure
Content-Type: application/json
Accept: application/json
```

Path parameters:

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | `DocumentId` | yes | Document identifier. Must match `PatchSet.documentId`. |

Body shape:

```ts
type PatchStructureRequest = PatchSet;
```

Example:

```json
{
  "schema": "remedipdf.patch.v0",
  "documentId": "doc:123",
  "baseRawHash": "sha256:8f3e1d5a",
  "patchSetId": "patchset:7",
  "createdAt": "2026-05-06T17:05:00Z",
  "author": {
    "kind": "user",
    "id": "user:local"
  },
  "operations": [
    {
      "opId": "op:1",
      "op": "setHeadingLevel",
      "target": {
        "regionId": "region:odl:1"
      },
      "value": {
        "level": 2
      },
      "reason": "Demote title candidate",
      "timestamp": "2026-05-06T17:05:00Z"
    }
  ]
}
```

### 200 Response

Shape:

```ts
type PatchStructureResponse = {
  schema: "remedipdf.structure.patch-response.v0";
  documentId: DocumentId;
  appliedPatchSetId: string;
  rawHash: string;
  patches: {
    count: number;
    latestPatchSetId: string;
    latestAppliedAt: string;
  };
  document: RemediDocument;
};
```

Example:

```json
{
  "schema": "remedipdf.structure.patch-response.v0",
  "documentId": "doc:123",
  "appliedPatchSetId": "patchset:7",
  "rawHash": "sha256:8f3e1d5a",
  "patches": {
    "count": 1,
    "latestPatchSetId": "patchset:7",
    "latestAppliedAt": "2026-05-06T17:05:00Z"
  },
  "document": {
    "schema": "remedipdf.intermediate.v0",
    "documentId": "doc:123",
    "source": {
      "fileName": "sample.pdf",
      "rawSchema": "opendataloader.schema.json",
      "rawHash": "sha256:8f3e1d5a",
      "analyzedAt": "2026-05-06T17:00:00Z"
    },
    "metadata": {
      "title": "Sample",
      "author": null,
      "creationDate": null,
      "modificationDate": null
    },
    "pages": [
      {
        "id": "page:1",
        "number": 1,
        "regionIds": ["region:odl:1"]
      }
    ],
    "regions": {
      "region:odl:1": {
        "id": "region:odl:1",
        "rawRef": {
          "source": "opendataloader",
          "rawId": 1,
          "rawPath": "/kids/0",
          "rawType": "heading"
        },
        "pageId": "page:1",
        "type": "heading",
        "pdfRole": "H2",
        "bbox": {
          "left": 200.891,
          "bottom": 706.938,
          "right": 394.152,
          "top": 745.132,
          "unit": "pt",
          "origin": "bottom-left"
        },
        "text": {
          "content": "Sample",
          "font": "Pretendard-Regular",
          "fontSize": 32.005,
          "textColor": "[0.0]"
        },
        "childIds": [],
        "artifact": {
          "isArtifact": false
        },
        "provenance": [
          {
            "source": "opendataloader-local",
            "rawType": "heading",
            "rawId": 1
          }
        ],
        "review": {
          "state": "approved",
          "reasons": [],
          "updatedBy": "system"
        }
      }
    },
    "readingOrder": {
      "mode": "region-list",
      "regionIds": ["region:odl:1"],
      "pageOrder": {
        "page:1": ["region:odl:1"]
      },
      "provenance": [
        {
          "source": "opendataloader-local"
        }
      ]
    },
    "tables": {},
    "lists": {},
    "assets": {},
    "captions": {},
    "reviewQueue": [],
    "patches": {
      "count": 1,
      "latestPatchSetId": "patchset:7",
      "latestAppliedAt": "2026-05-06T17:05:00Z"
    }
  }
}
```

### Status Codes

| Status | Meaning |
| --- | --- |
| `200 OK` | Patch set was applied and the effective structure was returned. |
| `400 Bad Request` | Patch body is not valid `PatchSet` JSON. |
| `404 Not Found` | The document does not exist. |
| `409 Conflict` | `baseRawHash` does not match the stored raw hash, or the patch conflicts with current state. |
| `422 Unprocessable Entity` | Patch schema is valid JSON, but an operation target or operation type is not valid for this document. |

## GET /documents/{id}/review-queue

Returns the review queue derived from the current effective RemediPDF structure state.

### Request

```http
GET /documents/{id}/review-queue
Accept: application/json
```

Path parameters:

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | `DocumentId` | yes | Document identifier. |

### 200 Response

Shape:

```ts
type GetReviewQueueResponse = {
  schema: "remedipdf.review-queue.v0";
  documentId: DocumentId;
  rawHash: string;
  items: ReviewQueueItem[];
  counts: {
    open: number;
    resolved: number;
    dismissed: number;
  };
};
```

Example:

```json
{
  "schema": "remedipdf.review-queue.v0",
  "documentId": "doc:123",
  "rawHash": "sha256:8f3e1d5a",
  "items": [
    {
      "id": "review:asset:region:odl:42:needs-alt-text",
      "category": "needs-alt-text",
      "assetId": "asset:region:odl:42",
      "regionId": "region:odl:42",
      "priority": "high",
      "state": "open"
    },
    {
      "id": "review:table:region:odl:9:table-headers",
      "category": "table-headers",
      "tableId": "table:region:odl:9",
      "regionId": "region:odl:9",
      "priority": "medium",
      "state": "open"
    }
  ],
  "counts": {
    "open": 2,
    "resolved": 0,
    "dismissed": 0
  }
}
```

### Status Codes

| Status | Meaning |
| --- | --- |
| `200 OK` | Review queue was returned. |
| `404 Not Found` | The document does not exist. |

## Error Cases

All error responses use `ErrorResponse`.

### Document Not Found

Status: `404 Not Found`

Example:

```json
{
  "error": {
    "code": "document_not_found",
    "message": "Document was not found.",
    "documentId": "doc:missing"
  }
}
```

### Raw Hash Mismatch

Status: `409 Conflict`

Raised when `PatchSet.baseRawHash` differs from the stored `RemediDocument.source.rawHash`.

Example:

```json
{
  "error": {
    "code": "raw_hash_mismatch",
    "message": "PatchSet.baseRawHash does not match RemediDocument.source.rawHash.",
    "documentId": "doc:123",
    "patchSetId": "patchset:7",
    "details": {
      "expectedRawHash": "sha256:8f3e1d5a",
      "actualBaseRawHash": "sha256:old"
    }
  }
}
```

### Invalid Patch Schema

Status: `400 Bad Request`

Raised when the request body is not valid `PatchSet` JSON or fails required-field/type validation.

Example:

```json
{
  "error": {
    "code": "invalid_patch_schema",
    "message": "PatchSet.operations must be an array.",
    "documentId": "doc:123",
    "patchSetId": "patchset:7",
    "details": {
      "field": "operations",
      "expected": "array"
    }
  }
}
```

### Unknown Target ID

Status: `422 Unprocessable Entity`

Raised when an operation target references an ID that is not present in the current effective state.

Example:

```json
{
  "error": {
    "code": "unknown_target_id",
    "message": "Patch target regionId was not found.",
    "documentId": "doc:123",
    "patchSetId": "patchset:7",
    "opId": "op:1",
    "target": {
      "regionId": "region:odl:999"
    }
  }
}
```

### Unsupported Operation

Status: `422 Unprocessable Entity`

Raised when an operation name is not in the `PatchOp` union or when the operation is valid in the schema but not supported by the current API version.

Example:

```json
{
  "error": {
    "code": "unsupported_operation",
    "message": "Patch operation is not supported.",
    "documentId": "doc:123",
    "patchSetId": "patchset:7",
    "opId": "op:2",
    "details": {
      "op": "rotateRegion",
      "supportedSchema": "remedipdf.patch.v0"
    }
  }
}
```

### Patch Conflict

Status: `409 Conflict`

Raised when the operation is individually valid but cannot be applied to the current effective state without violating structure invariants.

Example:

```json
{
  "error": {
    "code": "patch_conflict",
    "message": "Patch operation conflicts with current document state.",
    "documentId": "doc:123",
    "patchSetId": "patchset:7",
    "opId": "op:3",
    "target": {
      "tableCellId": "cell:region:odl:9:r1:c1"
    },
    "details": {
      "reason": "Cell span overlaps an existing table cell.",
      "conflictingTarget": {
        "tableCellId": "cell:region:odl:9:r1:c2"
      }
    }
  }
}
```
