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
