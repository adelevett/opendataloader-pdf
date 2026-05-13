# Calibre Library Roadmap

This roadmap defines an incremental path from the current corpus inventory to a portable Calibre library on flash storage, while keeping the 5 TB source disk read-only.

## Current Findings

- The OCR/extraction working directory is `C:\Users\delevetta\opendataloader-pdf\python\opendataloader-pdf`; `HOW_TO_RUN_LOCALLY.md` says to use `uv run` from that package directory or call the package venv Python directly.
- The verified CUDA environment in that directory reports `torch 2.11.0+cu128`, CUDA `12.8`, and `NVIDIA RTX 2000 Ada Generation Laptop GPU`.
- Do not run `uv sync` casually in the OCR package after the CUDA wheel override, because the local runbook says sync can replace the GPU PyTorch build with a CPU build.
- The source inventory is `C:\Users\delevetta\PDLay\data\extended_validation\chapter_paths_inventory\chapter_inventory.json`.
- The inventory contains `35,613` PDF rows across `2,055` parent directories, with `19,545` chapter candidates and `16,068` non-chapter files.
- The inventory also contains `1,282` `._*` dot-underscore artifacts and `362` `__MACOSX` artifact rows. These should be filtered before curation or import.
- Calibre's `fetch-ebook-metadata` can fetch online metadata from ISBN/title/author and can output OPF with `--opf`; its documented plugins include Google, Google Images, Amazon.com, Edelweiss, and Open Library. [Calibre fetch-ebook-metadata docs](https://manual.calibre-ebook.com/generated/en/fetch-ebook-metadata.html)
- `calibredb set_metadata` accepts an OPF file for an existing Calibre book record. [Calibre calibredb docs](https://manual.calibre-ebook.com/en/generated/en/calibredb.html)
- `calibredb add_format` can attach files as extra data using `--as-extra-data-file`, which is the correct path for zipped split components rather than repeated PDF formats. [Calibre calibredb docs](https://manual.calibre-ebook.com/en/generated/en/calibredb.html)
- Open Library asks API clients to cache responses, identify requests with a `User-Agent` and email, and says default non-identified requests are limited to 1 request per second while identified requests get 3 requests per second. [Open Library API docs](https://openlibrary.org/developers/api)
- Google API usage can be capped by requests per second per user and requests per day, and excess requests trigger limit-exceeded errors. [Google API Console Help](https://support.google.com/googleapi/answer/7035610?hl=en)

## Blockers

No hard blocker is identified.

Known risks:

- ISBN extraction coverage is unknown until an offline audit pass is run.
- Metadata fetches can be rate-limited or return incorrect records, so network metadata must be cached and reviewed rather than trusted blindly.
- Some groups are structurally ambiguous: page-range files, section/unit files, nested duplicate folders, and groups without clear chapter candidates.
- Calibre import should be tested against a disposable library before writing to the final flash library.

## Working Principles

1. Keep the source disk read-only.
2. Treat the JSON inventory as the system of record for source paths.
3. Run OCR/extraction through the known-good `opendataloader-pdf` GPU environment.
4. Separate data collection, metadata fetch, curation, and Calibre import into resumable phases.
5. Cache every network metadata result by normalized ISBN and source.
6. Never let missing metadata block import.
7. Preserve provenance for every Calibre record.
8. Prefer deterministic classification first; reserve manual or agent-assisted review for low-confidence records.

## Target Architecture

```text
5 TB source disk
  -> inventory JSON
  -> artifact filtering
  -> grouped book candidates
  -> offline ISBN audit
  -> curation and duplicate review
  -> metadata fetch queue
  -> cached OPF/JSON metadata
  -> dry-run Calibre import
  -> final flash Calibre library
```

Recommended directories:

```text
C:\Users\delevetta\opendataloader-pdf
  CALIBRE_LIBRARY_ROADMAP.md
  tools\calibre_library\
    audit_isbn.py
    classify_inventory.py
    fetch_metadata.py
    build_import_manifest.py
    import_calibre.py
    validate_calibre.py
  .calibre-work\
    run_manifest.json
    inventory_normalized.jsonl
    isbn_audit.jsonl
    book_groups.jsonl
    metadata_cache\
    import_manifest.jsonl
    import_log.jsonl
    review_queue.jsonl
  .calibre-artifacts\
    validation_summary.md
    validation_counts.json
    duplicate_decisions.csv
    metadata_failures.csv
    manual_review_queue.csv

C:\Users\delevetta\PDLay\data\extended_validation\chapter_paths_inventory\
  chapter_inventory.json

<flash drive>\CalibreLibrary\
  metadata.db
  Calibre-managed book folders
```

## Phase 0: Environment Baseline

Goal: verify that the OCR/extraction environment, Calibre CLI, and target storage are available before running corpus work.

Tasks:

- Confirm `uv run` from `C:\Users\delevetta\opendataloader-pdf\python\opendataloader-pdf` sees CUDA.
- Confirm `opendataloader-pdf-hybrid` can start on `127.0.0.1:5002`.
- Confirm `/health` returns `{"status":"ok"}`.
- Confirm Calibre CLI tools are discoverable:
  - `calibredb.exe`
  - `fetch-ebook-metadata.exe`
- Confirm target flash storage has enough free space.
- Create a disposable Calibre test library on flash, separate from the final library.

Acceptance criteria:

- CUDA check passes.
- OCR server health check passes.
- Calibre CLI check passes.
- Disposable Calibre library can be created and removed.

## Phase 1: Inventory Normalization

Goal: convert `chapter_inventory.json` into a clean, stable, line-oriented working manifest.

Input:

```text
C:\Users\delevetta\PDLay\data\extended_validation\chapter_paths_inventory\chapter_inventory.json
```

Tasks:

- Load the `rows` array.
- Drop artifact rows:
  - paths containing `__MACOSX`
  - file names starting with `._`
- Validate that source files still exist on disk.
- Add normalized fields:
  - `source_path`
  - `relative_path`
  - `parent_dir`
  - `file_name`
  - `stem`
  - `extension`
  - `file_size_bytes`
  - `modified_time_utc`
  - `page_count`
  - `inventory_sample_id`
  - `source_exists`
- Emit `inventory_normalized.jsonl`.

Acceptance criteria:

- Every retained row has a stable source path.
- Missing files are logged but do not stop the run.
- Artifact rows are excluded from downstream manifests.

## Phase 2: File and Group Classification

Goal: identify likely book records and component types before doing OCR or metadata fetches.

File-level classes:

```text
full_pdf_candidate
chapter_split_pdf
front_matter_pdf
toc_pdf
index_pdf
appendix_pdf
glossary_pdf
bibliography_pdf
answers_or_solutions_pdf
page_range_pdf
part_unit_section_pdf
kes_split
artifact
unknown_pdf
```

Group-level classes:

```text
single_file_book
full_pdf_plus_splits
split_only_book
chapter_only_book
nonchapter_collection
nested_duplicate_candidate
edition_duplicate_candidate
manual_review_required
```

Tasks:

- Group rows by `parent_dir`.
- Detect immediate nested duplicate folders.
- Detect likely edition duplicates using normalized title keys, year signals, and edition signals.
- Choose a provisional primary file per group:
  - full standalone PDF if present
  - front matter PDF if no full PDF exists
  - first chapter split if no better primary exists
  - empty Calibre record if no primary file should be treated as the book format
- Emit `book_groups.jsonl`.

Acceptance criteria:

- Every retained source row belongs to exactly one provisional group.
- Every group has a `confidence` score.
- Low-confidence groups are added to `review_queue.jsonl`.

## Phase 3: Offline ISBN Audit

Goal: measure ISBN coverage without any network calls.

Scan order:

1. File name and parent folder name.
2. Standalone/full PDF candidate text.
3. Front matter files.
4. TOC/contents files.
5. First few pages of chapter split files.
6. OCR fallback only when extracted text is missing or too short.

Recommended extraction policy:

```text
normal text extraction first
scan first 8 pages by default
scan more pages only for front matter files with very low text yield
OCR only when normal extraction returns insufficient text
```

ISBN candidate fields:

```text
raw_match
normalized_isbn
isbn_type
source_path
source_component_type
page_number
context_snippet
checksum_valid
confidence
```

Book-level audit output:

```text
group_id
parent_dir
primary_pdf
isbn_candidates
best_isbn
best_isbn_source
best_isbn_confidence
text_extraction_status
ocr_used
needs_metadata_fetch
needs_manual_review
```

Acceptance criteria:

- `isbn_audit.jsonl` exists.
- ISBN coverage percentage is known.
- OCR usage percentage is known.
- Failed extraction paths are logged.
- No network metadata calls occur in this phase.

## Phase 4: Curation and Deduplication

Goal: decide what should become one Calibre record before import.

Deduplication priority:

1. Same valid ISBN.
2. Same normalized title plus same edition.
3. Same normalized title with different editions.
4. Same folder title nested under another folder title.
5. Same source file checksum.

Policy:

- Same ISBN: treat as same work/edition candidate.
- Same title but different edition/year: keep latest by default, but preserve older candidates in review output.
- Nested duplicate folders: collapse only when file lists or checksums indicate duplicated content.
- No ISBN and ambiguous structure: keep in review queue rather than discard.

Outputs:

```text
curated_books.jsonl
duplicate_candidates.jsonl
review_queue.jsonl
```

Acceptance criteria:

- Every proposed Calibre record has a durable `group_id`.
- Every skipped duplicate has a reason and source reference.
- No source file is deleted or moved.

## Phase 5: Metadata Fetch Cache

Goal: fetch metadata once per unique ISBN and cache the result.

Preferred order:

1. Calibre `fetch-ebook-metadata --isbn <isbn> --opf`
2. Calibre plugin restriction for targeted retries, if needed.
3. Custom Open Library or Google Books calls only for unresolved ISBNs.

Throttle policy:

```text
default: 1 request per second
Open Library identified requests: maximum 3 requests per second
retry: exponential backoff for timeout, 429, and 5xx
cache key: normalized ISBN plus provider
```

Cache files:

```text
metadata_cache\
  isbn\
    9780000000000\
      calibre.opf
      calibre.stderr.txt
      openlibrary.json
      googlebooks.json
      fetch_status.json
```

Fetch status values:

```text
not_attempted
success
no_result
ambiguous_result
rate_limited
timeout
provider_error
manual_review_required
```

Acceptance criteria:

- Metadata fetches are resumable.
- Re-running the job does not re-fetch cached successes.
- Rate limits are handled without losing progress.
- Every ISBN has a fetch status.

## Phase 6: Import Manifest Generation

Goal: produce an exact plan for what Calibre will receive.

Per-book import manifest fields:

```text
group_id
title_guess
author_guess
best_isbn
metadata_opf_path
primary_format_path
extra_data_files
source_manifest_path
component_zip_path
custom_columns
import_action
confidence
review_flags
```

Component packaging:

- Zip split PDF components into one deterministic archive per book.
- Zip KES components with split PDFs when they represent the same source book.
- Preserve original file names inside the zip.
- Include a `source_manifest.json` inside each component zip.
- Attach the component zip as extra data, not as another PDF format.

Custom columns to create in Calibre:

```text
#source_root
#source_paths
#inventory_group_id
#inventory_sample_ids
#best_isbn_source
#import_confidence
#review_flags
#duplicate_policy
#source_manifest_hash
```

Acceptance criteria:

- `import_manifest.jsonl` is deterministic.
- Every Calibre action is represented before execution.
- Every source file is either imported, attached, skipped as duplicate, or sent to review.

## Phase 7: Disposable Library Dry Run

Goal: test Calibre commands against a small representative set.

Dry-run sample:

```text
10 single-file books with ISBN
10 full PDF plus split-component books
10 split-only books
10 no-ISBN books
10 duplicate/edition candidates
10 low-confidence groups
```

Command sequence per record:

```text
calibredb add <primary_format_path> --with-library <test_library>
calibredb set_metadata <book_id> <metadata.opf> --with-library <test_library>
calibredb add_format <book_id> <component_zip> --as-extra-data-file --with-library <test_library>
calibredb set_custom <column> <book_id> <value> --with-library <test_library>
```

Acceptance criteria:

- Book IDs are captured correctly.
- OPF metadata is applied correctly.
- Extra data attachments are present.
- Custom columns are populated.
- The dry-run library can be opened by Calibre.
- Failed imports are logged with command, exit code, stdout, and stderr.

## Phase 8: Full Flash Library Import

Goal: create the final Calibre library on flash storage.

Rules:

- Run in batches.
- Commit import progress after every book.
- Never mutate the source disk.
- Never delete source files.
- Stop on repeated Calibre database errors.
- Continue past missing metadata.

Batch size recommendation:

```text
start: 100 records
increase: 500 records only after clean validation
checkpoint: after every record
```

Import log fields:

```text
timestamp_utc
group_id
calibre_book_id
action
command
exit_code
stdout
stderr
duration_seconds
status
error_type
```

Acceptance criteria:

- The final library exists on flash storage.
- Every imported record has a Calibre ID.
- Every failure has a retryable or manual-review status.
- Import can resume after interruption without duplicating successful books.

## Phase 9: Validation

Goal: prove that the final Calibre library is usable, portable, and traceable back to source files.

Validation checks:

- Count imported records.
- Count records with ISBN.
- Count records with title and author.
- Count records with attached source manifests.
- Count records with component zips.
- Count records requiring manual review.
- Sample books in the Calibre GUI.
- Verify Calibre server can serve the library.
- Verify the library can be moved as a directory and reopened.

Reports:

```text
validation_summary.md
validation_counts.json
manual_review_queue.csv
metadata_failures.csv
duplicate_decisions.csv
```

Acceptance criteria:

- Validation report reconciles source groups, imported books, duplicates, and review records.
- No source path is lost from provenance.
- The library opens in Calibre and Calibre server.

## Phase 10: Maintenance Workflow

Goal: support future imports without rebuilding the library from scratch.

Tasks:

- Keep the import manifests and metadata cache.
- Add a new inventory delta mode.
- Re-run ISBN audit only for new or changed files.
- Re-fetch metadata only for missing, failed, or explicitly invalidated ISBNs.
- Keep duplicate decisions in a durable file.
- Maintain a manual corrections file that can override title, author, ISBN, edition, grouping, and duplicate policy.

Manual override shape:

```json
{
  "group_id": "example-group",
  "title": "Corrected Title",
  "authors": ["Corrected Author"],
  "isbn": "9780000000000",
  "edition": "15th",
  "grouping_policy": "keep",
  "duplicate_policy": "latest",
  "notes": "Human-reviewed"
}
```

## Implementation Order

1. `classify_inventory.py`
2. `audit_isbn.py`
3. `build_review_reports.py`
4. `fetch_metadata.py`
5. `build_import_manifest.py`
6. `import_calibre.py`
7. `validate_calibre.py`

## Immediate Next Step

Build `tools\calibre_library\classify_inventory.py` and `tools\calibre_library\audit_isbn.py`.

The first measurable milestone is:

```text
inventory_normalized.jsonl
book_groups.jsonl
isbn_audit.jsonl
isbn_coverage_summary.md
review_queue.jsonl
```

This milestone answers the core planning question before any Calibre import or network metadata fetch:

```text
How many source book groups have a valid ISBN that can meaningfully populate Calibre metadata?
```
