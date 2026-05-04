Research target: determine whether `adelevett/opendataloader-pdf` can act as the parsing, auto-tagging, and write-back engine for a PAVE 2.0-style remediation front end (code name RemediPDF), and identify the exact schema, API, UI, and accessibility gaps that must be closed.

PAVE 2.0 resources are available under the `frontend_docs` folder.

Baseline facts to anchor the investigation: the fork exposes OpenDataLoader PDF as a Java-backed parser with Python/Node/Java SDKs, JSON/Markdown/HTML/annotated PDF/tagged-PDF outputs, deterministic local mode, and optional hybrid mode for OCR, complex tables, formulas, and picture descriptions.  The root package is a monorepo workspace for Java build, option generation, and schema generation, not a front-end app workspace.  The Python package is explicitly a wrapper around the Java CLI, with `opendataloader-pdf` and `opendataloader-pdf-hybrid` script entry points.  PAVE 2.0’s relevant design pattern is an eight-step remediation flow with region, reading order, heading structure, tables, lists, figures, formulas, and metadata/page review, with a React UI and backend PDF modification. 

## Phase 1 — Repository and runtime audit

Goal: establish what is actually present in the fork, not just what the README promises.

Tasks:

1. Build the Java CLI from source and record the exact commands required on a clean machine.
2. Run the Python wrapper locally and verify the CLI options generated from `options.json`.
3. Run all relevant modes on a small PDF corpus:

   * `format=json`
   * `format=json,html`
   * `format=json,tagged-pdf`
   * `use_struct_tree=True`
   * `--table-method default`
   * `--table-method cluster`
   * `--reading-order xycut`
   * `--hybrid docling-fast`
   * `--hybrid-mode full`
   * hybrid with `--enrich-formula`
   * hybrid with `--enrich-picture-description`

Specific questions:

* Does every mode produce stable element IDs?
* Are IDs preserved between `json` and `tagged-pdf` output?
* Does HTML output preserve enough structure for preview, or is PDF rendering required for front-end overlays?
* Does `use_struct_tree=True` expose existing PDF tags in a way that can be edited?

Relevant code to inspect: `wrapper.py`, `convert_generated.py`, `runner.py`, `cli_options_generated.py`, Java CLI source, output processors, tagged-PDF writer, and schema-generation scripts. The wrapper delegates to generated options and a generated `convert()` function, so the actual integration contract should be traced from Python options down to Java CLI invocation. 

Deliverable: “Runtime capability matrix” with command, output artifacts, schema conformance, timing, failure modes, and whether the result is usable by a remediation UI.

## Phase 2 — Schema and semantic model audit

Goal: define the exact object model RemediPDF can rely on.

The published schema root requires `file name`, `number of pages`, `author`, `title`, `creation date`, `modification date`, and `kids`; each content element has `type`, `page number`, and `bounding box`; text-like elements carry `font`, `font size`, `text color`, and `content`.  The schema includes structural types for paragraph, heading, caption, table, text block, list, image, header/footer, table row, table cell, and list item.  Tables include row/cell structure with row/column indices, spans, and nested kids; lists include numbering style, item counts, and list items. 

Tasks:

1. Generate actual JSON outputs from at least 30 PDFs and validate them against `schema.json`.
2. Identify all fields that appear in real output but not in `schema.json`, especially `formula`, `picture`, confidence-like values, generated descriptions, and hybrid-only fields.
3. Determine whether bounding boxes are page-space coordinates suitable for front-end canvas overlays without transformation loss.
4. Determine whether typography is block-level only or whether per-span/per-character styling is available in Java internals.
5. Determine whether headers/footers are preserved, filtered, or optionally included via `--include-header-footer`.

Specific questions:

* Are `formula` and `picture` formal schema extensions or README-only examples?
* Are captions reliably linked by `linked content id`?
* Do tables retain enough information for a table-grid editor?
* Do list items retain enough structure for nested-list editing?
* Is there any confidence score or provenance flag indicating local vs hybrid vs source PDF structure tree?
* Is there enough metadata to support document-wide style rules such as “all 14pt bold blocks are H2”?

Deliverable: “Canonical RemediPDF intermediate schema,” with three layers:

1. Raw OpenDataLoader output.
2. Normalized remediation state.
3. Patch/mutation model for user edits.

## Phase 3 — PAVE 2.0 workflow mapping

Goal: map OpenDataLoader output to a PAVE-like remediation workflow with minimal guesswork.

Proposed mapping:

```text
OpenDataLoader element      RemediPDF/PAVE-style UI object
paragraph                   region: paragraph
heading + heading level     region: heading + heading-level editor
caption + linked id         caption object + linked figure/table target
table + rows/cells          table editor with grid, spans, header-cell controls
list + list items           list editor with item boundaries and nesting
image                       figure object with alt-text editor
picture                     figure/chart object with generated description
formula                     formula object with LaTeX + alt-text review
header/footer               artifact/header/footer decision
bounding box                page overlay rectangle
kids                        logical structure tree / nesting
font metadata               document-wide style rule candidate
```

PAVE 2.0’s region step explicitly includes paragraphs, headings, lists, formulas, figures, captions, artifacts, and tables; users can inspect selected regions, check assigned text, resize regions, delete tags, and change region type.  Its reading-order step gives both a visual directed graph and an ordered list, with support for changing regions into artifacts.  Its heading step allows document-wide heading-level adjustment and automatic heading-level detection based on text size. 

Tasks:

1. Build a mapping document from OpenDataLoader `type` values to PDF tag roles and UI controls.
2. Identify which PAVE-like steps can be bulk-verified using typography:

   * headings
   * paragraphs
   * captions in consistent styles
   * headers/footers
   * artifacts
3. Identify which steps require object-level review:

   * tables
   * lists
   * formulas
   * images/charts
   * ambiguous captions
   * reading-order anomalies
4. Design document-wide override operations:

   * “all blocks with same font/style/size become H2”
   * “all recurring top-page elements become artifacts”
   * “all captions matching this pattern link to nearest figure/table”
5. Design per-object override operations:

   * split/merge regions
   * change type
   * change reading-order position
   * edit heading level
   * edit table cell structure
   * edit list nesting
   * edit figure alt text
   * edit formula LaTeX and generated alt text

Deliverable: “PAVE 2.0 compatibility map,” including required UI controls, backend fields, and write-back semantics.

## Phase 4 — Write-back and mutation model investigation

Goal: determine whether the fork can support interactive remediation, not just one-shot auto-tagging.

The CLI exposes output format values including `json`, `text`, `html`, `pdf`, `markdown`, `markdown-with-html`, `markdown-with-images`, and `tagged-pdf`; it also exposes options for structure-tree use, table method, reading-order algorithm, page extraction, image output, hybrid mode, and header/footer inclusion.  The README describes auto-tagging as “untagged PDF in → Tagged PDF out” and says tagged-PDF generation creates structure tags for headings, paragraphs, lists, tables, and reading order. 

The core research question is whether corrected UI state can be written back. One-shot `format=tagged-pdf` is not enough for a remediation front end unless there is a way to inject user edits into the tag-generation pipeline.

Tasks:

1. Locate the Java classes responsible for tagged-PDF generation.
2. Determine whether the writer consumes the same object tree as JSON output.
3. Determine whether a modified JSON tree can be passed back into the writer.
4. Determine whether region edits require PDF operator-level assignment or whether bounding-box-level edits are sufficient.
5. Determine whether alt text, table headers, formula alt text, artifact marking, and metadata can be written into the PDF tag tree.
6. Determine whether existing tagged PDFs can be read, edited, and re-emitted without destroying existing structure.

Specific questions:

* Is there a public or internal API equivalent to `writeTaggedPdf(inputPdf, correctedStructureJson)`?
* Are PDF operators mapped to content IDs?
* Can the system distinguish “mark as artifact” from “delete from output”?
* Can figure/formula alt text be added to the structure tree?
* Can table header scope and cell spans be represented and written?
* Can heading levels be changed without re-running detection?

Deliverable: “Write-back feasibility report,” with one of three conclusions:

1. Existing writer can be adapted directly.
2. Writer can be adapted after exposing an internal structure model.
3. A new remediation-patch layer is required.

## Phase 5 — Hybrid-mode investigation for hard objects

Goal: determine whether hybrid mode should be optional, required, or selectively invoked by the front end.

The hybrid package depends on `docling[easyocr]`, FastAPI, Uvicorn, and `python-multipart`.  The hybrid server is a FastAPI service around a Docling `DocumentConverter`, returns Docling JSON, and states that Markdown/HTML are generated by Java.  The server supports `--force-ocr`, `--no-ocr`, OCR engine selection, CPU/MPS/CUDA/XPU device selection, `--enrich-formula`, and `--enrich-picture-description`.  The README says formula extraction produces LaTeX in JSON and picture description produces a `picture` object with a generated description; both require `--hybrid-mode full` on the client side. 

Tasks:

1. Compare local vs hybrid output on the same corpus.
2. Measure changes in:

   * reading order
   * heading hierarchy
   * table structure
   * list structure
   * image detection
   * formula detection
   * caption linkage
3. Identify whether hybrid results can be merged into the local OpenDataLoader schema deterministically.
4. Test CPU-only performance with `--device cpu`.
5. Test whether `--hybrid-mode auto` misses formulas or picture descriptions compared with `--hybrid-mode full`.
6. Determine whether formulas should be always routed to hybrid when detected, or only after user requests formula review.

Deliverable: “Hybrid routing policy” for RemediPDF:

* default local pass
* optional page-level hybrid reprocess
* required full hybrid pass for formulas/picture descriptions
* fallback behavior when hybrid fails

## Phase 6 — Review-queue and front-end interaction design

Goal: improve on PAVE 2.0’s linear step flow by adding targeted review queues.

PAVE 2.0’s content-dependent steps cover tables, lists, figures, and mathematical formulas; table and list editing are explicit drawing/structure tasks, figure editing centers on alternative text, and formula editing centers on LaTeX correction followed by MathSpeak-style alternative-text generation.  The paper reports that PAVE 2.0 improved tag accuracy over Adobe Acrobat Pro, but also identifies persistent problems: captions were often left as paragraphs, figures were sometimes marked as artifacts, several users did not reach the formula step, and reading-order errors remained common. 

Tasks:

1. Define a `reviewQueue` object generated from OpenDataLoader output.
2. Define queue categories:

   * “needs alt text”
   * “generated alt text requires verification”
   * “table header cells unresolved”
   * “table has spans or uncertain grid”
   * “formula LaTeX requires verification”
   * “caption linkage uncertain”
   * “reading order conflict”
   * “possible artifact”
   * “style-rule conflict”
3. Prototype keyboard-first navigation:

   * next unresolved item
   * previous unresolved item
   * approve current item
   * apply same decision document-wide
   * mark decorative/artifact
   * jump to page
4. Define confidence/provenance badges:

   * source tag tree
   * deterministic local
   * hybrid
   * user-edited
   * rule-applied
5. Design audit mode:

   * show only unresolved items
   * show all items of type
   * show low-confidence items
   * show document-wide style groups

Deliverable: clickable front-end prototype or low-fidelity UI spec with state machine and keyboard interactions.

## Phase 7 — Evaluation corpus and metrics

Goal: measure whether OpenDataLoader materially reduces human remediation work.

Corpus:

1. Simple born-digital academic PDFs.
2. Two-column scientific papers.
3. PDFs with existing tags.
4. Untagged PDFs.
5. PDFs with complex/borderless tables.
6. PDFs with lists and nested lists.
7. PDFs with formulas.
8. PDFs with charts and figures.
9. Scanned PDFs with OCR.
10. Administrative forms or non-scientific PDFs.

Metrics:

1. Element classification accuracy.
2. Reading-order accuracy.
3. Heading-level accuracy.
4. Table structure accuracy.
5. List structure accuracy.
6. Caption detection and linkage accuracy.
7. Formula detection and LaTeX accuracy.
8. Figure/chart alt-text coverage.
9. PDF tag validity after write-back.
10. Time-to-first-usable tagged PDF.
11. Number of required human corrections.
12. Number of false “safe to approve” suggestions.
13. Keyboard accessibility of the UI.

Use PAVE 2.0’s thirteen tag-accuracy criteria as the evaluation baseline: all content tagged, reading order, headings tagged, heading levels, tables tagged, table structure, lists tagged, list structure, figures tagged, figure alt text, formulas tagged, formula alt text, and captions. 

Deliverable: benchmark report comparing:

* OpenDataLoader local auto-tagging alone
* OpenDataLoader hybrid auto-tagging
* RemediPDF UI with human correction
* PAVE 2.0 paper results as reference, not as a directly comparable implementation benchmark

## Phase 8 — Accessibility and compliance validation

Goal: separate machine-checkable validity from actual tag accuracy.

Tasks:

1. Run generated tagged PDFs through veraPDF/PDF-UA checks where available.
2. Manually inspect structure trees for the thirteen PAVE criteria.
3. Test screen-reader reading order on representative PDFs.
4. Test whether generated HTML is useful as an accessible alternate format.
5. Test whether PDF/UA export is available in the fork or only through enterprise code.
6. Verify metadata writing: title, author, language.
7. Verify alt text writing for figures and formulas.
8. Verify artifact handling.

The README says auto-tagging is free and PDF/UA export is an enterprise add-on, so the investigation should not assume that open-source tagged-PDF output equals PDF/UA compliance. 

Deliverable: compliance gap matrix:

* tagged-PDF possible now
* PDF/UA possible now
* PDF/UA blocked by missing feature
* requires external validator/manual inspection
* requires user judgment

## Phase 9 — Architecture proposal

Target architecture:

```text
PDF upload
  ↓
OpenDataLoader local parse
  ↓
optional hybrid enrichment for selected pages/objects
  ↓
normalize to RemediPDF remediation state
  ↓
document-wide style-rule inference
  ↓
review queue generation
  ↓
PAVE-style front-end correction
  ↓
patch log / audit trail
  ↓
tagged-PDF write-back
  ↓
validation report + final export
```

Core services to specify:

1. `POST /documents` — upload PDF.
2. `POST /documents/{id}/analyze` — run local/hybrid analysis.
3. `GET /documents/{id}/structure` — normalized remediation state.
4. `PATCH /documents/{id}/structure` — apply user edits.
5. `GET /documents/{id}/review-queue` — unresolved items.
6. `POST /documents/{id}/rules` — document-wide style rules.
7. `POST /documents/{id}/export/tagged-pdf` — generate corrected PDF.
8. `POST /documents/{id}/validate` — run automated and manual-check scaffolding.
9. `GET /documents/{id}/page/{n}/image` — page raster for overlay.
10. `GET /documents/{id}/artifacts` — extracted images/formulas/tables for editors.

Deliverable: architecture decision record with API shapes, data ownership, and failure modes.

## Phase 10 — Implementation roadmap

Week 1: build, run, and schema audit. Produce a corpus, run all output modes, validate against `schema.json`, and document every schema mismatch.

Week 2: Java internals and write-back audit. Trace JSON generation and tagged-PDF generation to determine whether corrected structure can be re-injected.

Week 3: adapter design. Define RemediPDF normalized schema, review queue schema, patch schema, and OpenDataLoader-to-RemediPDF mapping.

Week 4: prototype. Build a minimal viewer showing PDF page image, OpenDataLoader bounding boxes, type labels, reading order, and per-item override controls.

Week 5: hard-object editors. Prototype table review, list nesting review, figure alt-text review, and formula LaTeX/alt-text review.

Week 6: export and validation. Attempt corrected tagged-PDF output; run validation; document blockers.

Final deliverables:

1. Repository audit report.
2. Schema conformance report.
3. OpenDataLoader-to-PAVE mapping.
4. RemediPDF normalized schema.
5. Review queue design.
6. Write-back feasibility report.
7. Hybrid routing policy.
8. Minimal front-end prototype specification.
9. Accessibility validation matrix.
10. Implementation backlog with prioritized issues/PRs.

Primary risk areas:

1. The open-source API may not expose a way to write user-corrected structure back into the PDF.
2. The formal schema may lag hybrid outputs such as `formula` and `picture`.
3. Bounding boxes may not be sufficient if PDF operator-level assignment is required for reliable tag writing.
4. Formula and picture enrichment require hybrid full mode, which may affect latency and deployment complexity.
5. PAVE 2.0’s usability gains came from guided human verification, so a RemediPDF front end should not over-optimize for invisible automation at the expense of review.
