# RemediPDF Intermediate Schema v0

This document is the canonical RemediPDF intermediate schema for the roadmap phase that adapts OpenDataLoader PDF output into a PAVE-style remediation workflow.

The intermediate model has three layers:

1. Raw OpenDataLoader output.
2. Normalized RemediPDF remediation state.
3. Ordered patch log for user, rule, and system mutations.

The root `schema.json` remains the OpenDataLoader raw-output contract. This document defines the remediation contract layered on top of that output and records the mapping rules needed to move between layers.

## Layer 1: Raw OpenDataLoader Output

Raw output is immutable parser output. RemediPDF may index it, normalize it, and attach patches against it, but must not rewrite it in place. A persisted RemediPDF document stores the raw OpenDataLoader JSON as an input artifact and derives the editable state as:

```text
effectiveState = normalize(rawOpenDataLoaderJson) + orderedPatchLog
```

### Raw Document

The raw document root is the object produced by `format=json`.

```ts
type RawOpenDataLoaderDocument = {
  "file name": string;
  "number of pages": number;
  author: string | null;
  title: string | null;
  "creation date": string | null;
  "modification date": string | null;
  hybrid?: RawHybridInfo;
  kids: RawElement[];
};

type RawHybridInfo = Record<string, unknown>;
```

### Raw Element Fields

Every raw element is expected to carry the common OpenDataLoader element fields. `id` is optional because raw output only writes it when OpenDataLoader has a non-zero recognized structure ID.

```ts
type RawElementBase = {
  type: string;
  id?: number;
  level?: string;
  "page number": number;
  "bounding box": [left: number, bottom: number, right: number, top: number];

  confidence?: number;
  "source label"?: number;
  "heading inference"?: {
    method: string;
    "bbox height px"?: number;
  };
  tsr?: {
    "num cells"?: number;
    html?: string;
    "run time ms"?: number;
  };
  caption?: {
    text?: string;
    language?: string;
    "run time ms"?: number;
  };
  "regionlist resolution"?: {
    strategy: string;
    "tsr attempted": boolean;
    "tsr result"?: string;
  };
  "word match"?: {
    method: string;
    "matched words": number;
  };
  "text source"?: "stream" | "ocr" | "ocr-fallback" | string;
  "stream ocr similarity"?: number;
};
```

Coordinates are PDF points with a bottom-left page origin. Raw OpenDataLoader order is `[left, bottom, right, top]`.

### Raw Element Types

The raw layer preserves OpenDataLoader type names and field names exactly.

```ts
type RawTextFields = {
  font: string;
  "font size": number;
  "text color": string;
  content: string;
  "hidden text"?: boolean;
};

type RawParagraph = RawElementBase & RawTextFields & {
  type: "paragraph";
};

type RawHeading = RawElementBase & RawTextFields & {
  type: "heading";
  "heading level": number;
};

type RawCaption = RawElementBase & RawTextFields & {
  type: "caption";
  "linked content id"?: number;
};

type RawTable = RawElementBase & {
  type: "table";
  "number of rows": number;
  "number of columns": number;
  "previous table id"?: number;
  "next table id"?: number;
  rows: RawTableRow[];
};

type RawTableRow = {
  type: "table row";
  "row number": number;
  cells: RawTableCell[];
};

type RawTableCell = RawElementBase & {
  type: "table cell";
  "row number": number;
  "column number": number;
  "row span": number;
  "column span": number;
  kids: RawElement[];
};

type RawTextBlock = RawElementBase & {
  type: "text block";
  kids: RawElement[];
};

type RawList = RawElementBase & {
  type: "list";
  "numbering style": string;
  "number of list items": number;
  "previous list id"?: number;
  "next list id"?: number;
  "list items": RawListItem[];
};

type RawListItem = RawElementBase & RawTextFields & {
  type: "list item";
  kids: RawElement[];
};

type RawImage = RawElementBase & {
  type: "image";
  source?: string;
  data?: string;
  format?: "png" | "jpeg";
  alt?: string;
  description?: string;
};

type RawFormula = RawElementBase & {
  type: "formula";
  content: string;
};

type RawHeaderFooter = RawElementBase & {
  type: "header" | "footer";
  kids: RawElement[];
};

type RawElement =
  | RawParagraph
  | RawHeading
  | RawCaption
  | RawTable
  | RawTableCell
  | RawTextBlock
  | RawList
  | RawListItem
  | RawImage
  | RawFormula
  | RawHeaderFooter;
```

`formula`, `alt`, and `description` are emitted by current serializers but are not yet part of the root `schema.json` content-element union. RemediPDF treats them as supported raw extensions and must not drop them during normalization.

## Layer 2: Normalized RemediPDF State

The normalized layer is the editable state exposed by `GET /documents/{id}/structure`. It converts raw parser output into stable RemediPDF IDs, object-shaped coordinates, explicit provenance, review status, reading-order lists, and object models suitable for remediation UI controls.

### RemediDocument

```ts
type DocumentId = string;
type PageId = `page:${number}`;
type RegionId = string;
type TableId = string;
type TableCellId = string;
type ListId = string;
type ListItemId = string;
type AssetId = string;
type CaptionId = string;

type RemediDocument = {
  schema: "remedipdf.intermediate.v0";
  documentId: DocumentId;
  source: {
    fileName: string;
    rawSchema: "opendataloader.schema.json";
    rawHash: string;
    analyzedAt: string;
  };
  metadata: DocumentMetadata;
  pages: Page[];
  regions: Record<RegionId, Region>;
  readingOrder: ReadingOrder;
  tables: Record<TableId, TableModel>;
  lists: Record<ListId, ListModel>;
  assets: Record<AssetId, Asset>;
  captions: Record<CaptionId, CaptionLink>;
  reviewQueue: ReviewQueueItem[];
  patches: PatchSetSummary;
};

type PatchSetSummary = {
  count: number;
  latestPatchSetId?: string;
  latestAppliedAt?: string;
};

type DocumentMetadata = {
  title: string | null;
  author: string | null;
  language?: string | null;
  creationDate: string | null;
  modificationDate: string | null;
};
```

### Page

```ts
type Page = {
  id: PageId;
  number: number;
  size?: {
    width: number;
    height: number;
    unit: "pt";
  };
  regionIds: RegionId[];
};
```

`size` is optional in v0 because the current raw JSON does not expose page dimensions. Consumers that need overlay transforms must obtain page size from the PDF renderer or a page-image endpoint.

### Region

```ts
type Region = {
  id: RegionId;
  rawRef: RawRef | null;
  pageId: PageId;
  type: RegionType;
  pdfRole: PdfRole;
  bbox: BBox;
  text?: TextPayload;
  tableId?: TableId;
  listId?: ListId;
  assetId?: AssetId;
  captionId?: CaptionId;
  parentId?: RegionId;
  childIds: RegionId[];
  artifact: ArtifactState;
  provenance: Provenance[];
  review: ReviewStatus;
};

type BBox = {
  left: number;
  bottom: number;
  right: number;
  top: number;
  unit: "pt";
  origin: "bottom-left";
};

type TextPayload = {
  content: string;
  font?: string;
  fontSize?: number;
  textColor?: string;
  hidden?: boolean;
};

type ArtifactState = {
  isArtifact: boolean;
  reason?: "header" | "footer" | "decorative" | "background" | "deleted" | "user";
};

type RawRef = {
  source: "opendataloader";
  rawId?: number;
  rawPath: string;
  rawType: string;
};
```

### Region Types And PDF Roles

```ts
type RegionType =
  | "paragraph"
  | "heading"
  | "caption"
  | "table"
  | "tableCell"
  | "list"
  | "listItem"
  | "figure"
  | "formula"
  | "artifact"
  | "textBlock"
  | "header"
  | "footer"
  | "unknown";

type PdfRole =
  | "P"
  | "H1"
  | "H2"
  | "H3"
  | "H4"
  | "H5"
  | "H6"
  | "Caption"
  | "Table"
  | "TR"
  | "TH"
  | "TD"
  | "L"
  | "LI"
  | "Figure"
  | "Formula"
  | "Artifact"
  | "Div"
  | "Unknown";
```

### Reading Order

```ts
type ReadingOrder = {
  mode: "region-list";
  regionIds: RegionId[];
  pageOrder: Record<PageId, RegionId[]>;
  provenance: Provenance[];
};
```

Top-level raw `kids` order is the initial reading order. Nested table cells, list items, headers, and footers retain child order within their parent object and may also appear in page-level UI overlays.

### TableModel

```ts
type TableModel = {
  id: TableId;
  regionId: RegionId;
  rowCount: number;
  columnCount: number;
  previousTableId?: TableId;
  nextTableId?: TableId;
  rows: TableRow[];
  review: ReviewStatus;
};

type TableRow = {
  index: number;
  cellIds: TableCellId[];
};

type TableCell = {
  id: TableCellId;
  regionId: RegionId;
  row: number;
  column: number;
  rowSpan: number;
  columnSpan: number;
  role: "TH" | "TD";
  scope?: "row" | "column" | "both" | "none";
  childRegionIds: RegionId[];
};
```

Table cells default to `TD`. Header-cell status and scope are remediation decisions represented by patches.

### ListModel

```ts
type ListModel = {
  id: ListId;
  regionId: RegionId;
  numberingStyle: string;
  previousListId?: ListId;
  nextListId?: ListId;
  itemIds: ListItemId[];
  review: ReviewStatus;
};

type ListItem = {
  id: ListItemId;
  regionId: RegionId;
  parentItemId?: ListItemId;
  level: number;
  ordinal: number;
  childRegionIds: RegionId[];
};
```

Nested-list levels default to raw nesting when present. If raw output only provides flat list items, all items start at `level: 1`.

### Asset

```ts
type Asset = {
  id: AssetId;
  regionId: RegionId;
  kind: "image" | "formula";
  source?: string;
  data?: string;
  format?: "png" | "jpeg";
  altText?: AltText;
  formula?: FormulaPayload;
  review: ReviewStatus;
};

type AltText = {
  value: string;
  source: "raw-alt" | "raw-description" | "hybrid-generated" | "user" | "rule";
  verified: boolean;
};

type FormulaPayload = {
  latex: string;
  altText?: AltText;
  verified: boolean;
};
```

For raw `image`, prefer `alt` over `description` when both exist. Preserve both in provenance metadata if both are present.

### CaptionLink

```ts
type CaptionLink = {
  id: CaptionId;
  regionId: RegionId;
  targetRegionId?: RegionId;
  confidence?: number;
  review: ReviewStatus;
};
```

Raw `"linked content id"` maps to `targetRegionId` by raw ID lookup. If no target can be resolved, keep the caption region and mark the caption link unresolved.

### Provenance And Review Status

```ts
type Provenance = {
  source: "source-tag-tree" | "opendataloader-local" | "hybrid" | "user" | "rule";
  rawType?: string;
  rawId?: number;
  confidence?: number;
  details?: Record<string, unknown>;
};

type ReviewStatus = {
  state: "unresolved" | "approved" | "rejected" | "needs-review";
  reasons: ReviewReason[];
  updatedBy: "system" | "user" | "rule";
  updatedAt?: string;
};

type ReviewReason =
  | "needs-alt-text"
  | "generated-alt-text"
  | "formula-latex"
  | "table-headers"
  | "table-spans"
  | "caption-link"
  | "reading-order"
  | "possible-artifact"
  | "style-rule-conflict"
  | "missing-raw-id"
  | "low-confidence";
```

### Review Queue

```ts
type ReviewQueueItem = {
  id: string;
  category: ReviewReason;
  regionId?: RegionId;
  assetId?: AssetId;
  tableId?: TableId;
  captionId?: CaptionId;
  priority: "high" | "medium" | "low";
  state: "open" | "resolved" | "dismissed";
};
```

The review queue is generated from normalized state and patches. It is not authoritative state by itself.

## Layer 3: Patch And Mutation Model

Patch payloads are the write shape for `PATCH /documents/{id}/structure`. RemediPDF uses domain operations instead of generic JSON Patch so every operation can carry provenance, validation status, and write-back intent.

```ts
type PatchSet = {
  schema: "remedipdf.patch.v0";
  documentId: string;
  baseRawHash: string;
  patchSetId: string;
  createdAt: string;
  author: PatchAuthor;
  operations: PatchOperation[];
};

type PatchAuthor = {
  kind: "user" | "system" | "rule";
  id?: string;
  label?: string;
};

type PatchOperation = {
  opId: string;
  op: PatchOp;
  target: PatchTarget;
  value?: unknown;
  reason?: string;
  timestamp: string;
};

type PatchTarget = {
  regionId?: RegionId;
  tableId?: TableId;
  tableCellId?: TableCellId;
  listId?: ListId;
  listItemId?: ListItemId;
  assetId?: AssetId;
  captionId?: CaptionId;
  document?: true;
};
```

### Patch Operations

```ts
type PatchOp =
  | "setRegionType"
  | "setArtifact"
  | "setBBox"
  | "splitRegion"
  | "mergeRegions"
  | "moveReadingOrder"
  | "setHeadingLevel"
  | "setTableDimensions"
  | "setTableCellRole"
  | "setTableCellScope"
  | "setTableCellSpan"
  | "setListItemLevel"
  | "setListItemOrder"
  | "setAltText"
  | "setFormulaLatex"
  | "setFormulaAltText"
  | "setCaptionTarget"
  | "setMetadata"
  | "applyStyleRule"
  | "setReviewStatus";
```

### Operation Values

```ts
type PatchValues = {
  setRegionType: { type: RegionType; pdfRole?: PdfRole };
  setArtifact: { isArtifact: boolean; reason?: ArtifactState["reason"] };
  setBBox: BBox;
  splitRegion: { newRegions: Array<{ id: RegionId; bbox: BBox; text?: TextPayload }> };
  mergeRegions: { sourceRegionIds: RegionId[]; mergedRegionId: RegionId };
  moveReadingOrder: { beforeRegionId?: RegionId; afterRegionId?: RegionId; pageId?: PageId };
  setHeadingLevel: { level: 1 | 2 | 3 | 4 | 5 | 6 };
  setTableDimensions: { rowCount: number; columnCount: number };
  setTableCellRole: { role: "TH" | "TD" };
  setTableCellScope: { scope: "row" | "column" | "both" | "none" };
  setTableCellSpan: { rowSpan: number; columnSpan: number };
  setListItemLevel: { level: number; parentItemId?: ListItemId };
  setListItemOrder: { ordinal: number };
  setAltText: { value: string; verified: boolean };
  setFormulaLatex: { latex: string; verified: boolean };
  setFormulaAltText: { value: string; verified: boolean };
  setCaptionTarget: { targetRegionId: RegionId | null };
  setMetadata: Partial<DocumentMetadata>;
  applyStyleRule: StyleRuleApplication;
  setReviewStatus: ReviewStatus;
};

type StyleRuleApplication = {
  ruleId: string;
  selector: StyleRuleSelector;
  operation: PatchOp;
  value: unknown;
  affectedRegionIds: RegionId[];
};

type StyleRuleSelector = {
  type?: RegionType;
  font?: string;
  fontSize?: number;
  textColor?: string;
  contentPattern?: string;
  pageBand?: "top" | "bottom" | "body";
};
```

Patch application is ordered and deterministic. If two patches target the same field, the later operation wins unless the operation is structurally invalid. Structurally invalid operations must be rejected before persistence.

## Mapping Rules

### Raw Type To Region Type

| Raw OpenDataLoader type | RemediPDF region type | Default PDF role | Mapping rule |
| --- | --- | --- | --- |
| `paragraph` | `paragraph` | `P` | Copy text, style fields, bbox, raw ID, and provenance. |
| `heading` | `heading` | `Hn` | Map `"heading level"` to `H1` through `H6`; clamp only as a validation error, not silently. |
| `caption` | `caption` | `Caption` | Resolve `"linked content id"` to a target region when possible. |
| `table` | `table` | `Table` | Create `TableModel`, row records, and child cell regions. |
| `table row` | internal row | `TR` | Represent as `TableRow`, not as a top-level region. |
| `table cell` | `tableCell` | `TD` | Create `TableCell`; header role is unresolved until user or rule sets `TH`. |
| `text block` | `textBlock` | `Div` | Preserve children and expose as a grouping region. |
| `list` | `list` | `L` | Create `ListModel`; use raw numbering style. |
| `list item` | `listItem` | `LI` | Preserve child regions and inferred level. |
| `image` with `alt` or `description` | `figure` | `Figure` | Create image asset with generated or raw alt text requiring verification. |
| `image` without `alt` or `description` | `figure` | `Figure` | Create image asset and queue `needs-alt-text`. |
| `formula` | `formula` | `Formula` | Create formula asset from `content` as LaTeX and queue verification. |
| `header` | `header` | `Artifact` | Default to artifact candidate, not deleted content. |
| `footer` | `footer` | `Artifact` | Default to artifact candidate, not deleted content. |
| unknown | `unknown` | `Unknown` | Preserve raw fields in provenance and queue review. |

### ID Mapping

RemediPDF IDs are stable strings.

```text
raw id present:    region:odl:<rawId>
raw id missing:    region:page:<pageNumber>:path:<rawPathHash>
table id:          table:<regionId>
list id:           list:<regionId>
asset id:          asset:<regionId>
caption id:        caption:<regionId>
```

Raw IDs are preserved in `rawRef.rawId`. Missing raw IDs must add review reason `missing-raw-id` so write-back code does not assume operator-level identity is available.

### Coordinate Mapping

```ts
function normalizeBBox(raw: [number, number, number, number]): BBox {
  return {
    left: raw[0],
    bottom: raw[1],
    right: raw[2],
    top: raw[3],
    unit: "pt",
    origin: "bottom-left"
  };
}
```

### Provenance Mapping

| Raw evidence | Normalized provenance |
| --- | --- |
| `use_struct_tree=True` result, when known by the analyzer | `source-tag-tree` |
| Local OpenDataLoader result | `opendataloader-local` |
| `hybrid` document block or element metadata | `hybrid` |
| `confidence` | `provenance[].confidence` and `low-confidence` review reason when below the UI threshold |
| `source label` | `provenance[].details.sourceLabel` |
| `text source` | `provenance[].details.textSource` |
| `heading inference` | `provenance[].details.headingInference` |
| `tsr` | `provenance[].details.tsr` |
| `caption` metadata | `provenance[].details.caption` |

### Review Queue Rules

Initial normalization adds review items as follows:

| Condition | Review reason |
| --- | --- |
| Figure has no alt text | `needs-alt-text` |
| Figure alt text came from `alt`, `description`, or hybrid caption metadata | `generated-alt-text` |
| Formula exists | `formula-latex` |
| Table exists and no header cells are marked | `table-headers` |
| Table has spans greater than 1 or hybrid TSR metadata | `table-spans` |
| Caption target cannot be resolved | `caption-link` |
| Header/footer or repeated page-band text exists | `possible-artifact` |
| Confidence is below UI threshold | `low-confidence` |
| Raw ID is missing | `missing-raw-id` |

## Coverage Matrix

| Required scenario | Covered by |
| --- | --- |
| Heading | `RawHeading`, `RegionType: "heading"`, `setHeadingLevel`, heading example. |
| Paragraph | `RawParagraph`, `RegionType: "paragraph"`, raw type mapping. |
| Caption linkage | `RawCaption`, `CaptionLink`, `setCaptionTarget`, caption-link review rule. |
| Table cells and spans | `RawTableCell`, `TableCell`, `setTableCellSpan`, table-span review rule. |
| List items | `RawListItem`, `ListItem`, `setListItemLevel`, `setListItemOrder`. |
| Image alt text | `RawImage.alt`, `RawImage.description`, `Asset.altText`, `setAltText`. |
| Formula LaTeX | `RawFormula.content`, `FormulaPayload.latex`, `setFormulaLatex`. |
| Header/footer artifact decisions | `RawHeaderFooter`, `ArtifactState`, `setArtifact`. |
| Hybrid confidence/provenance | raw metadata fields, `Provenance`, low-confidence review rule. |
| Missing raw IDs | deterministic fallback ID rule and `missing-raw-id` review reason. |

## Examples

### Heading

Raw:

```json
{
  "type": "heading",
  "id": 1,
  "level": "Doctitle",
  "page number": 1,
  "bounding box": [200.891, 706.938, 394.152, 745.132],
  "heading level": 1,
  "font": "Pretendard-Regular",
  "font size": 32.005,
  "text color": "[0.0]",
  "content": "Lorem Ipsum"
}
```

Normalized:

```json
{
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
    "content": "Lorem Ipsum",
    "font": "Pretendard-Regular",
    "fontSize": 32.005,
    "textColor": "[0.0]"
  },
  "childIds": [],
  "artifact": {
    "isArtifact": false
  }
}
```

### Patch Set

```json
{
  "schema": "remedipdf.patch.v0",
  "documentId": "doc:123",
  "baseRawHash": "sha256:...",
  "patchSetId": "patchset:1",
  "createdAt": "2026-05-06T00:00:00Z",
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
      "reason": "User changed document title candidate to H2",
      "timestamp": "2026-05-06T00:00:00Z"
    },
    {
      "opId": "op:2",
      "op": "setAltText",
      "target": {
        "assetId": "asset:region:odl:42"
      },
      "value": {
        "value": "Line chart showing revenue increasing from 2022 to 2025.",
        "verified": true
      },
      "timestamp": "2026-05-06T00:01:00Z"
    }
  ]
}
```

## Write-Back Semantics

The normalized state is the remediation source of truth. Export code should read the effective state and patch log, then decide how to write the corrected PDF tag tree.

Required write-back decisions:

| RemediPDF state | Intended PDF write-back |
| --- | --- |
| `pdfRole: "H1"` through `"H6"` | Heading tag with matching level. |
| `artifact.isArtifact: true` | Mark as PDF artifact, not as deleted output. |
| `TableCell.role: "TH"` and `scope` | Header cell and scope metadata when writer support exists. |
| `Asset.altText.verified: true` | Figure alternate text. |
| `FormulaPayload.altText.verified: true` | Formula alternate text. |
| `CaptionLink.targetRegionId` | Caption relationship to figure/table/formula target when writer support exists. |
| `DocumentMetadata` patch | PDF metadata update. |

If the current writer cannot express a remediation decision, preserve the patch and report the unsupported write-back field during export validation.
