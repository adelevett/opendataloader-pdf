from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _bootstrap_repo_imports() -> Path:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[2]
    package_src = repo_root / "python" / "opendataloader-pdf" / "src"
    for candidate in (repo_root, package_src):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
    return repo_root


REPO_ROOT = _bootstrap_repo_imports()

from tools.calibre_library.io import load_jsonl, write_json, write_jsonl
from tools.calibre_library.paths import calibre_artifacts_dir, calibre_work_dir, ensure_calibre_dirs


TERMINAL_STATUSES = {
    "success",
    "no_result",
    "ambiguous_result",
    "manual_review_required",
    "provider_error",
    "timeout",
}

RETRYABLE_STATUSES = {
    "provider_error",
    "timeout",
    "rate_limited",
}

DC_NS = "{http://purl.org/dc/elements/1.1/}"
OPF_NS = "{http://www.idpf.org/2007/opf}"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and cache Calibre OPF metadata for unique ISBNs."
    )
    parser.add_argument(
        "--queue-jsonl",
        type=Path,
        default=calibre_work_dir() / "metadata_fetch_queue.jsonl",
        help="Metadata fetch queue produced by build_review_reports.py",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=calibre_work_dir(),
        help="Ignored repo-local workspace for JSONL manifests",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=calibre_artifacts_dir(),
        help="Ignored repo-local workspace for human-readable artifacts",
    )
    parser.add_argument(
        "--fetch-command",
        default="fetch-ebook-metadata",
        help="fetch-ebook-metadata executable path or command name",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=45.0,
        help="Calibre metadata lookup timeout passed to --timeout",
    )
    parser.add_argument(
        "--process-timeout-seconds",
        type=float,
        default=90.0,
        help="Outer subprocess timeout",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.0,
        help="Delay between uncached provider requests",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum uncached ISBNs to fetch in this run; 0 means all",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch every ISBN even when a cache status already exists",
    )
    parser.add_argument(
        "--retry-failures",
        action="store_true",
        help="Retry existing timeout/provider/rate-limit statuses",
    )
    return parser.parse_args(argv)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_dir(work_dir: Path, isbn: str) -> Path:
    return work_dir / "metadata_cache" / "isbn" / isbn


def _read_existing_status(cache_dir: Path) -> dict[str, Any] | None:
    status_path = cache_dir / "fetch_status.json"
    if not status_path.exists():
        return None
    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "status": "provider_error",
            "error": "existing fetch_status.json is not valid JSON",
        }


def _should_skip(existing: dict[str, Any] | None, *, force: bool, retry_failures: bool) -> bool:
    if force or not existing:
        return False
    status = str(existing.get("status") or "")
    if retry_failures and status in RETRYABLE_STATUSES:
        return False
    return status in TERMINAL_STATUSES


def _extract_opf(stdout: str) -> str:
    text = stdout.strip()
    if not text:
        return ""
    xml_index = text.find("<?xml")
    package_index = text.find("<package")
    candidates = [index for index in (xml_index, package_index) if index >= 0]
    if candidates:
        return text[min(candidates) :].strip()
    return text


def _parse_opf_summary(opf_text: str) -> dict[str, Any]:
    if not opf_text:
        return {}
    try:
        root = ET.fromstring(opf_text)
    except ET.ParseError:
        return {}

    metadata = root.find(f"{OPF_NS}metadata")
    if metadata is None and root.tag.endswith("metadata"):
        metadata = root
    if metadata is None:
        return {}

    def text_values(tag: str) -> list[str]:
        values: list[str] = []
        for element in metadata.findall(f"{DC_NS}{tag}"):
            if element.text and element.text.strip():
                values.append(element.text.strip())
        return values

    identifiers: dict[str, list[str]] = {}
    for element in metadata.findall(f"{DC_NS}identifier"):
        scheme = (
            element.attrib.get(f"{OPF_NS}scheme")
            or element.attrib.get("scheme")
            or element.attrib.get("id")
            or "identifier"
        )
        value = (element.text or "").strip()
        if value:
            identifiers.setdefault(str(scheme), []).append(value)

    return {
        "title": next(iter(text_values("title")), None),
        "authors": text_values("creator"),
        "publisher": next(iter(text_values("publisher")), None),
        "language": next(iter(text_values("language")), None),
        "subjects": text_values("subject"),
        "identifiers": identifiers,
    }


def _looks_like_opf(opf_text: str) -> bool:
    summary = _parse_opf_summary(opf_text)
    return bool(summary.get("title") or summary.get("authors") or summary.get("identifiers"))


def _status_from_result(
    *,
    returncode: int | None,
    stdout: str,
    stderr: str,
    timed_out: bool,
) -> tuple[str, str, dict[str, Any]]:
    if timed_out:
        return "timeout", "", {}
    opf_text = _extract_opf(stdout)
    opf_summary = _parse_opf_summary(opf_text)
    if _looks_like_opf(opf_text):
        return "success", opf_text, opf_summary
    combined = f"{stdout}\n{stderr}".lower()
    if "no matches" in combined or "no results" in combined:
        return "no_result", "", {}
    if "429" in combined or "rate limit" in combined or "too many requests" in combined:
        return "rate_limited", "", {}
    if returncode == 0:
        return "no_result", "", {}
    return "provider_error", "", {}


def _run_fetch(args: argparse.Namespace, isbn: str) -> dict[str, Any]:
    command = [
        args.fetch_command,
        "--isbn",
        isbn,
        "--opf",
        "--timeout",
        str(int(args.timeout_seconds)),
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.process_timeout_seconds,
            check=False,
        )
        duration_seconds = round(time.monotonic() - started, 3)
        status, opf_text, opf_summary = _status_from_result(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
        )
        return {
            "status": status,
            "command": command,
            "exit_code": completed.returncode,
            "duration_seconds": duration_seconds,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "opf_text": opf_text,
            "opf_summary": opf_summary,
        }
    except subprocess.TimeoutExpired as exc:
        duration_seconds = round(time.monotonic() - started, 3)
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "status": "timeout",
            "command": command,
            "exit_code": None,
            "duration_seconds": duration_seconds,
            "stdout": stdout,
            "stderr": stderr,
            "opf_text": "",
            "opf_summary": {},
            "error": f"subprocess timed out after {args.process_timeout_seconds} seconds",
        }


def _write_cache(
    *,
    cache_dir: Path,
    isbn: str,
    queue_row: dict[str, Any],
    fetch_result: dict[str, Any],
) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    opf_path = cache_dir / "calibre.opf"
    stdout_path = cache_dir / "calibre.stdout.txt"
    stderr_path = cache_dir / "calibre.stderr.txt"
    command_path = cache_dir / "calibre.command.json"
    status_path = cache_dir / "fetch_status.json"

    if fetch_result.get("opf_text"):
        opf_path.write_text(str(fetch_result["opf_text"]), encoding="utf-8", newline="\n")
    elif opf_path.exists() and fetch_result.get("status") != "success":
        opf_path.unlink()

    stdout_path.write_text(str(fetch_result.get("stdout") or ""), encoding="utf-8", newline="\n")
    stderr_path.write_text(str(fetch_result.get("stderr") or ""), encoding="utf-8", newline="\n")
    write_json(command_path, {"command": fetch_result.get("command")})

    status_record = {
        "canonical_isbn": isbn,
        "status": fetch_result.get("status"),
        "fetched_utc": _utc_now(),
        "exit_code": fetch_result.get("exit_code"),
        "duration_seconds": fetch_result.get("duration_seconds"),
        "opf_path": str(opf_path) if fetch_result.get("status") == "success" else None,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "command_path": str(command_path),
        "metadata_only": True,
        "cover_download_requested": False,
        "opf_summary": fetch_result.get("opf_summary") or {},
        "error": fetch_result.get("error"),
        "queue_row": queue_row,
    }
    write_json(status_path, status_record)
    return status_record


def _cached_result_row(isbn: str, cache_dir: Path, existing: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_isbn": isbn,
        "status": existing.get("status"),
        "cached": True,
        "cache_dir": str(cache_dir),
        "opf_path": existing.get("opf_path"),
        "duration_seconds": existing.get("duration_seconds"),
        "title": (existing.get("opf_summary") or {}).get("title"),
        "authors": (existing.get("opf_summary") or {}).get("authors", []),
    }


def _fetched_result_row(isbn: str, cache_dir: Path, status_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_isbn": isbn,
        "status": status_record.get("status"),
        "cached": False,
        "cache_dir": str(cache_dir),
        "opf_path": status_record.get("opf_path"),
        "duration_seconds": status_record.get("duration_seconds"),
        "title": (status_record.get("opf_summary") or {}).get("title"),
        "authors": (status_record.get("opf_summary") or {}).get("authors", []),
    }


def _render_summary_md(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    lines = [
        "# Calibre Metadata Fetch Summary",
        "",
        f"- generated_utc: {manifest['generated_utc']}",
        f"- queue_jsonl: {manifest['queue_jsonl']}",
        f"- fetch_command: {manifest['fetch_command']}",
        f"- timeout_seconds: {manifest['timeout_seconds']}",
        f"- metadata_only: {manifest['metadata_only']}",
        f"- cover_download_requested: {manifest['cover_download_requested']}",
        "",
        "## Counts",
        f"- queue_items: {summary['queue_items']}",
        f"- fetched_this_run: {summary['fetched_this_run']}",
        f"- cached_skipped: {summary['cached_skipped']}",
        f"- result_rows: {summary['result_rows']}",
        "",
        "## Statuses",
    ]
    for name, count in sorted(summary["status_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    samples = manifest.get("sample_results", [])
    if samples:
        lines.extend(["", "## Sample Results"])
        for row in samples:
            authors = ", ".join(row.get("authors", [])[:3])
            lines.append(
                f"- {row['canonical_isbn']} | {row['status']} | "
                f"{row.get('title') or ''} | {authors}"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not args.queue_jsonl.exists():
        raise FileNotFoundError(f"Metadata fetch queue not found: {args.queue_jsonl}")

    work_dir, artifact_dir = ensure_calibre_dirs(args.work_dir, args.artifact_dir)
    queue_rows = load_jsonl(args.queue_jsonl)

    results: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    fetched_this_run = 0
    cached_skipped = 0

    for row in queue_rows:
        isbn = str(row.get("canonical_isbn") or "").strip()
        if not isbn:
            continue
        cache_dir = _cache_dir(work_dir, isbn)
        existing = _read_existing_status(cache_dir)
        if _should_skip(existing, force=args.force, retry_failures=args.retry_failures):
            assert existing is not None
            result_row = _cached_result_row(isbn, cache_dir, existing)
            results.append(result_row)
            status_counts[str(result_row["status"])] += 1
            cached_skipped += 1
            continue

        if args.limit and fetched_this_run >= args.limit:
            break

        fetch_result = _run_fetch(args, isbn)
        status_record = _write_cache(
            cache_dir=cache_dir,
            isbn=isbn,
            queue_row=row,
            fetch_result=fetch_result,
        )
        result_row = _fetched_result_row(isbn, cache_dir, status_record)
        results.append(result_row)
        status_counts[str(result_row["status"])] += 1
        fetched_this_run += 1

        if args.sleep_seconds > 0 and fetched_this_run < len(queue_rows):
            time.sleep(args.sleep_seconds)

    manifest = {
        "generated_utc": _utc_now(),
        "repo_root": str(REPO_ROOT),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "command": list(sys.argv if argv is None else [sys.argv[0], *argv]),
        "queue_jsonl": str(args.queue_jsonl),
        "fetch_command": args.fetch_command,
        "timeout_seconds": args.timeout_seconds,
        "process_timeout_seconds": args.process_timeout_seconds,
        "sleep_seconds": args.sleep_seconds,
        "metadata_only": True,
        "cover_download_requested": False,
        "summary": {
            "queue_items": len(queue_rows),
            "fetched_this_run": fetched_this_run,
            "cached_skipped": cached_skipped,
            "result_rows": len(results),
            "status_counts": dict(status_counts),
        },
        "sample_results": results[:25],
    }

    write_jsonl(work_dir / "metadata_fetch_results.jsonl", results)
    write_json(work_dir / "metadata_fetch_manifest.json", manifest)
    write_json(artifact_dir / "metadata_fetch_summary.json", manifest)
    (artifact_dir / "metadata_fetch_summary.md").write_text(
        _render_summary_md(manifest),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "queue_items": len(queue_rows),
                "fetched_this_run": fetched_this_run,
                "cached_skipped": cached_skipped,
                "statuses": dict(status_counts),
                "work_dir": str(work_dir),
                "artifact_dir": str(artifact_dir),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
