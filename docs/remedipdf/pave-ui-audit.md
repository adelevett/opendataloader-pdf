# PAVE 2.0 Screenshot Audit for RemediPDF Viewer

Source material:
- `frontend_docs/images/*.jpg`
- `frontend_docs/pave_help_corpus.md`
- `frontend_docs/paper.md`

Scope:
- No code changes.
- No frontend build.
- No API changes.

This audit extracts reusable viewer requirements from the PAVE 2.0 screenshots and maps them to the current RemediPDF structure contract in [`api-contract.md`](./api-contract.md) and [`intermediate-schema.md`](./intermediate-schema.md).

## Screenshot Review

### Region detection and editing

Screenshots: `DetectRegions_1080p.jpg`, `NewRegion_1080p.jpg`, `ChangeRegionType_1080p.jpg`, `ConnectRegions_1080p.jpg`

- The page view uses color-coded bounding boxes with type labels pinned to the top-right of each region.
- The left workspace combines page navigation, detection actions, a selected-region inspector, and bulk region actions.
- The inspector switches from an empty state to an editable state with a region-type dropdown, content preview, and region actions such as delete, combine, and separate.
- Region visibility is controlled independently from artifact visibility.

### Reading order

Screenshots: `DetectReadingOrder_1080p.jpg`, `DrawReadingOrder_1080p.jpg`, `MoveReadingOrderItem_1080p.jpg`

- Reading order is shown twice: as numbered overlays on the page and as an ordered list in the workspace.
- The page overlay uses connecting lines and numbered markers to show sequence.
- The list rows show item type plus a text excerpt, which makes the order readable without looking at the page render.
- Users can detect order automatically, draw it manually, or adjust individual items in the list.

### Heading structure

Screenshot: `HeadingStructure_1080p.jpg`

- Headings are presented as a flat editable list rather than a tree editor.
- Each heading row has a level selector, and the page overlay shows the heading level label.
- The step provides an automatic detection action, but the user still reviews and corrects the hierarchy.

### Tables

Screenshots: `TableNewColumnRows_1080p.jpg`, `TableRemoveRow_1080p.jpg`, `TableChangeHeading_1080p.jpg`

- Table editing is grid-based and uses a preview that mirrors the page view.
- The workspace exposes detection, row/column combine or removal, and header-cell coverage controls.
- Header coverage is expressed as first row, first column, or both.
- The page overlay shows row and column boundaries and highlights the current structure.

### Lists

Screenshot: `NewListItems_1080p.jpg`

- Lists are edited as grouped list items rather than as raw structure nodes.
- The workspace exposes combine and delete actions, plus visible list-item numbering.
- The page render shows the list in context, but the editing control stays in the side panel.

### Figures

Screenshot: `Figure_1080p.jpg`

- The figure editor shows a preview image, an alt-text input, a recognition action, and a decorative toggle.
- The user can review the figure in context while editing its description.

### Formulas

Screenshots: `MathEditor_1080p.jpg`, `MathEditor2_1080p.jpg`

- The formula editor exposes a formula preview, Math Editor and LaTeX modes, keyboard access, recognition, conversion, and an output/alt-text area.
- Formula editing is separate from the page overlay and is treated as a dedicated remediation step.

### Metadata and download

Screenshots: `MetaInformation_1080p.jpg`, `Download_1080p.jpg`

- The final step combines metadata entry with download/export.
- The metadata panel covers title, author, language, keywords, and subject.
- The final review view can hide region labels and artifacts independently.

## Reusable UI Requirements

| Requirement | What the screenshots imply | RemediPDF fields / endpoints | Gap or note |
| --- | --- | --- | --- |
| Page overlay labels | Show type labels and numbering directly on the rendered page, with per-step label modes and visibility toggles | `GET /documents/{id}/structure`, `pages[].regionIds`, `pages[].size`, `regions[].bbox`, `regions[].type`, `regions[].pdfRole`, `regions[].artifact.isArtifact`, `readingOrder.regionIds`, `tables`, `lists`, `assets`, `captions` | `pages[].size` is optional in v0; accurate overlay placement still needs page dimensions from the renderer or a page-image endpoint |
| Selected-region panel | Show an inspector for the active object with type-specific controls, content preview, and action buttons | `regions[].text`, `regions[].review`, `regions[].artifact`, `regions[].childIds`, `regions[].parentId`, `regions[].tableId`, `regions[].listId`, `regions[].assetId`, `regions[].captionId`, `assets[].altText`, `assets[].formula`, `captions[].targetRegionId`; `PATCH /documents/{id}/structure` with `setRegionType`, `setArtifact`, `setHeadingLevel`, `setAltText`, `setFormulaLatex`, `setFormulaAltText`, `setCaptionTarget`, `setMetadata`, `setReviewStatus` | Selection state is UI-only and should not be persisted in the structure contract |
| Heading structure controls | Show a per-heading level selector, keep the heading list flat and reviewable, and show the level on the page render | `regions[].type`, `regions[].pdfRole`, `PATCH /documents/{id}/structure` with `setHeadingLevel`; `GET /documents/{id}/structure` for the heading list itself | Existing structure state is enough; the UI should enforce valid heading hierarchy as a presentation rule rather than as a new data model |
| Reading-order list behavior | Keep a numbered list that mirrors the page sequence, supports per-item review, and allows reordering without direct tree editing | `readingOrder.mode`, `readingOrder.regionIds`, `readingOrder.pageOrder`, `PATCH /documents/{id}/structure` with `moveReadingOrder`; `GET /documents/{id}/review-queue` for `reading-order` items | Existing model is enough for ordered lists; drag/drop and drawing gestures can remain client-side interaction details |
| Table grid and header controls | Show a grid preview, row/column edit actions, and explicit header-cell coverage choices | `tables`, `TableModel.rows`, `TableCell.row`, `TableCell.column`, `TableCell.rowSpan`, `TableCell.columnSpan`, `TableCell.role`, `TableCell.scope`; `PATCH /documents/{id}/structure` with `setTableDimensions`, `setTableCellRole`, `setTableCellScope`, `setTableCellSpan`; `GET /documents/{id}/review-queue` for `table-headers` and `table-spans` | The contract represents final table structure well; if the UI wants to persist intermediate grid-drawing state, that state is client-only or needs a separate edit model |
| List editing controls | Show a compact list-item editor with item numbering, nesting, and combine/delete actions | `lists`, `ListModel.numberingStyle`, `ListModel.itemIds`, `ListItem.level`, `ListItem.ordinal`, `ListItem.parentItemId`; `PATCH /documents/{id}/structure` with `setListItemLevel`, `setListItemOrder` | Existing list fields are enough for list remediation; multi-column or multi-page list edge cases remain a modeling and product decision |
| Figure review controls | Let the user review the image, enter or accept alt text, and mark the figure decorative when needed | `assets[assetId].kind`, `assets[assetId].source`, `assets[assetId].data`, `assets[assetId].format`, `assets[assetId].altText`, `assets[assetId].review`; `PATCH /documents/{id}/structure` with `setAltText` | Generated alt text should be stored through `AltText.source` and `verified`; the screenshot's recognition button is a UI action, not a separate persisted field |
| Formula review controls | Let the user review the formula, switch between LaTeX and editor modes, and edit the formula narration | `assets[assetId].kind`, `assets[assetId].formula.latex`, `assets[assetId].formula.altText`, `assets[assetId].formula.verified`; `PATCH /documents/{id}/structure` with `setFormulaLatex` and `setFormulaAltText`; `GET /documents/{id}/review-queue` for `formula-latex` items | The math keyboard, editor mode, and conversion widgets are UI-only. Do not treat MathML output as canonical RemediPDF state unless a new field is added later |
| Artifact handling | Keep artifact state explicit while letting the viewer hide or show artifacts independently | `regions[].artifact.isArtifact`, `regions[].artifact.reason`, `PATCH /documents/{id}/structure` with `setArtifact`; `GET /documents/{id}/review-queue` for `possible-artifact` | Hide/show is view state only; do not conflate it with deletion |
| Keyboard and accessibility gaps to avoid | Avoid mouse-only drawing, drag-only reordering, and color-only meaning | No persisted field. This is viewer behavior only. | Provide keyboard-reachable controls, visible focus, text labels, non-color cues, and a non-drawing fallback for each edit step |
| Metadata and download flow | Support final metadata edits and a downloadable repaired artifact | `metadata`, `PATCH /documents/{id}/structure` with `setMetadata`; `GET /documents/{id}/structure`; `GET /documents/{id}/review-queue` | The current contract covers metadata editing, but it does not define a binary download/export endpoint or report payload |

## Contract Fit

Already modeled in the current RemediPDF schema:
- Region, heading, table, list, figure, formula, caption, artifact, and review state.
- Reading order as `readingOrder.regionIds` plus `readingOrder.pageOrder`.
- Metadata as `metadata.title`, `metadata.author`, `metadata.language`, `metadata.creationDate`, and `metadata.modificationDate`.
- Review surfacing via `reviewQueue` and `GET /documents/{id}/review-queue`.

Still external to the current contract:
- Page rendering and overlay transform data if page size is not already present.
- UI selection state, panel layout, overlay visibility, and other transient viewer preferences.
- Binary export/download behavior for the repaired PDF and any download-time report.

## Accessibility Gaps To Avoid

- Do not encode meaning only in red/green state.
- Do not require drawing gestures for the only way to perform an edit.
- Do not make list reordering depend on hidden drag handles.
- Do not let overlays obscure the content without a hide toggle.
- Do not treat artifact visibility as a destructive action.
- Do not leave the selected object ambiguous; every inspector state needs a clear object type and label.
- Do not bury the keyboard path behind the mouse path; every primary action should have a keyboard equivalent.

## RemediPDF Mapping Summary

- `GET /documents/{id}/structure` supplies the editable document state.
- `PATCH /documents/{id}/structure` records remediation actions.
- `GET /documents/{id}/review-queue` supports review badges, counts, and category-based queues.
- The screenshot-driven UI patterns should be implemented as presentation and interaction state on top of those endpoints, not as new persisted structure fields unless a future contract revision needs them.
