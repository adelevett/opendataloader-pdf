from __future__ import annotations

import json
import locale
import os
import re
import socket
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from contextlib import nullcontext
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
import signal
from typing import Any


@dataclass
class ExtractionResult:
    backend: str
    pdf_path: Path
    pages: str | None
    output_dir: Path
    json_path: Path
    document: dict[str, Any]
    page_texts: dict[int, str]
    combined_text: str
    char_count: int
    word_count: int


_SIMPLE_PAGE_RANGE_RE = re.compile(r"^\s*(\d+)(?:\s*-\s*(\d+))?\s*$")
_JAR_NAME = "opendataloader-pdf-cli.jar"


def _normalize_timeout(timeout_seconds: float | None) -> float | None:
    if timeout_seconds is None:
        return None
    if timeout_seconds <= 0:
        return None
    return timeout_seconds


def _build_cli_args(
    pdf: Path,
    output_dir: Path,
    *,
    pages: str | None,
    quiet: bool,
    use_struct_tree: bool,
    extra_args: list[str] | None = None,
) -> list[str]:
    args = [
        str(pdf),
        "--output-dir",
        str(output_dir),
        "--format",
        "json",
        "--image-output",
        "off",
    ]
    if quiet:
        args.append("--quiet")
    if pages:
        args.extend(["--pages", pages])
    if use_struct_tree:
        args.append("--use-struct-tree")
    if extra_args:
        args.extend(extra_args)
    return args


def _run_cli_extract(
    args: list[str],
    *,
    quiet: bool,
    timeout_seconds: float | None,
    backend_label: str,
) -> None:
    timeout = _normalize_timeout(timeout_seconds)
    jar_ref = resources.files("opendataloader_pdf").joinpath("jar", _JAR_NAME)
    with resources.as_file(jar_ref) as jar_path:
        command = ["java", "-jar", str(jar_path), *args]
        popen_kwargs: dict[str, Any] = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": locale.getpreferredencoding(False),
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            popen_kwargs["start_new_session"] = True

        process = subprocess.Popen(command, **popen_kwargs)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                os.killpg(process.pid, signal.SIGKILL)

            stdout, stderr = process.communicate()
            raise TimeoutError(
                f"{backend_label} extraction timed out after {timeout_seconds:.1f}s"
            ) from exc
        if process.returncode:
            output = (stdout or stderr or "").strip()
            detail = f": {output[:500]}" if output else ""
            raise RuntimeError(
                f"{backend_label} extraction failed with exit code {process.returncode}{detail}"
            )

        if not quiet:
            if stdout:
                print(stdout, end="")
            if stderr:
                print(stderr, end="")


def _pages_to_hybrid_range(pages: str | None) -> str | None:
    if pages is None:
        return None
    match = _SIMPLE_PAGE_RANGE_RE.match(pages)
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2) or match.group(1))
    return f"{start}-{end}"


def _build_multipart_body(pdf: Path, page_ranges: str | None) -> tuple[bytes, str]:
    boundary = f"----opendataloader-{uuid.uuid4().hex}"
    line_break = b"\r\n"
    body = bytearray()

    def add_text_field(name: str, value: str) -> None:
        body.extend(f"--{boundary}".encode("ascii"))
        body.extend(line_break)
        body.extend(f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"))
        body.extend(line_break)
        body.extend(line_break)
        body.extend(value.encode("utf-8"))
        body.extend(line_break)

    if page_ranges:
        add_text_field("page_ranges", page_ranges)

    body.extend(f"--{boundary}".encode("ascii"))
    body.extend(line_break)
    body.extend(
        f'Content-Disposition: form-data; name="files"; filename="{pdf.name}"'.encode("utf-8")
    )
    body.extend(line_break)
    body.extend(b"Content-Type: application/pdf")
    body.extend(line_break)
    body.extend(line_break)
    body.extend(pdf.read_bytes())
    body.extend(line_break)
    body.extend(f"--{boundary}--".encode("ascii"))
    body.extend(line_break)

    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _extract_via_docling_fast_server(
    pdf: Path,
    *,
    output_dir: Path,
    pages: str | None,
    hybrid_url: str | None,
    timeout_seconds: float | None,
) -> tuple[Path, dict[str, Any]]:
    page_ranges = _pages_to_hybrid_range(pages)
    if pages is not None and page_ranges is None:
        raise ValueError(
            f"Direct docling-fast extraction only supports a single page range, got {pages!r}"
        )

    body, content_type = _build_multipart_body(pdf, page_ranges)
    endpoint = f"{(hybrid_url or 'http://127.0.0.1:5002').rstrip('/')}/v1/convert/file"
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": content_type,
            "Accept": "application/json",
        },
        method="POST",
    )

    timeout = _normalize_timeout(timeout_seconds)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"hybrid extraction failed with HTTP {exc.code}: {detail[:500]}"
        ) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, socket.timeout):
            raise TimeoutError(
                f"hybrid extraction timed out after {timeout_seconds:.1f}s"
            ) from exc
        raise RuntimeError(f"hybrid extraction failed: {exc.reason}") from exc
    except socket.timeout as exc:
        raise TimeoutError(
            f"hybrid extraction timed out after {timeout_seconds:.1f}s"
        ) from exc

    status = str(payload.get("status") or "")
    if status == "failure":
        errors = payload.get("errors") or []
        raise RuntimeError(f"hybrid extraction failed: {errors}")

    document_wrapper = payload.get("document") or {}
    document = document_wrapper.get("json_content")
    if not isinstance(document, dict):
        raise TypeError("Hybrid server response did not contain document.json_content")

    json_path = output_dir / f"{pdf.stem}.json"
    json_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path, document


def _coerce_page_number(value: Any) -> int:
    try:
        if value is None:
            return 0
        if isinstance(value, bool):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _collect_text_by_page(node: Any, current_page: int = 0, buckets: dict[int, list[str]] | None = None) -> dict[int, list[str]]:
    if buckets is None:
        buckets = defaultdict(list)

    if isinstance(node, dict):
        page_value = (
            node.get("page number")
            or node.get("page_no")
            or node.get("pageNumber")
            or node.get("page")
        )
        page_number = _coerce_page_number(page_value)
        if page_number:
            current_page = page_number

        for key in ("content", "text", "md_content", "html_content"):
            value = node.get(key)
            if isinstance(value, str):
                text = value.strip()
                if text:
                    buckets[current_page].append(text)

        for key, value in node.items():
            if key in {"content", "text", "md_content", "html_content"}:
                continue
            if isinstance(value, (dict, list)):
                _collect_text_by_page(value, current_page=current_page, buckets=buckets)
    elif isinstance(node, list):
        for item in node:
            _collect_text_by_page(item, current_page=current_page, buckets=buckets)

    return buckets


def _find_json_output(output_dir: Path, pdf_path: Path) -> Path:
    expected = output_dir / f"{pdf_path.stem}.json"
    if expected.exists():
        return expected

    matches = list(output_dir.rglob("*.json"))
    if not matches:
        raise FileNotFoundError(f"No JSON output was produced in {output_dir}")

    for match in matches:
        if match.stem == pdf_path.stem:
            return match
    return matches[0]


def _build_extraction_result(
    *,
    backend: str,
    pdf: Path,
    pages: str | None,
    output_dir: Path,
    json_path: Path,
    document: dict[str, Any],
) -> ExtractionResult:
    page_buckets = _collect_text_by_page(document)
    page_texts = {
        page: " ".join(chunks).strip()
        for page, chunks in page_buckets.items()
        if " ".join(chunks).strip()
    }
    combined_parts = [page_texts[page] for page in sorted(page_texts) if page != 0]
    if 0 in page_texts:
        combined_parts.insert(0, page_texts[0])
    combined_text = "\n".join(part for part in combined_parts if part)
    char_count = len(combined_text)
    word_count = len(combined_text.split())

    return ExtractionResult(
        backend=backend,
        pdf_path=pdf,
        pages=pages,
        output_dir=output_dir,
        json_path=json_path,
        document=document,
        page_texts=page_texts,
        combined_text=combined_text,
        char_count=char_count,
        word_count=word_count,
    )


def extract_pdf_text(
    pdf_path: Path | str,
    *,
    pages: str | None = None,
    backend: str = "native",
    hybrid_backend: str | None = None,
    hybrid_mode: str | None = None,
    hybrid_url: str | None = None,
    hybrid_hancom_ai_ocr_strategy: str | None = None,
    hybrid_hancom_ai_regionlist_strategy: str | None = None,
    hybrid_hancom_ai_image_cache: str | None = None,
    quiet: bool = True,
    use_struct_tree: bool = False,
    output_dir: Path | None = None,
    timeout_seconds: float | None = None,
) -> ExtractionResult:
    pdf = Path(pdf_path)

    temp_context = tempfile.TemporaryDirectory(prefix="calibre-audit-") if output_dir is None else nullcontext(None)
    with temp_context as temp_dir:
        out_dir = Path(temp_dir) if output_dir is None else Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        if backend == "hybrid":
            selected_hybrid = hybrid_backend or "docling-fast"
            if selected_hybrid == "docling-fast" and _pages_to_hybrid_range(pages) is not None:
                json_path, document = _extract_via_docling_fast_server(
                    pdf,
                    output_dir=out_dir,
                    pages=pages,
                    hybrid_url=hybrid_url,
                    timeout_seconds=timeout_seconds,
                )
            else:
                extra_args = [
                    "--hybrid",
                    selected_hybrid,
                    "--hybrid-mode",
                    hybrid_mode or "full",
                    "--hybrid-fallback",
                ]
                if hybrid_url:
                    extra_args.extend(["--hybrid-url", hybrid_url])
                if timeout_seconds and timeout_seconds > 0:
                    extra_args.extend(["--hybrid-timeout", str(int(timeout_seconds * 1000))])
                if selected_hybrid == "hancom-ai":
                    if hybrid_hancom_ai_ocr_strategy:
                        extra_args.extend([
                            "--hybrid-hancom-ai-ocr-strategy",
                            hybrid_hancom_ai_ocr_strategy,
                        ])
                    if hybrid_hancom_ai_regionlist_strategy:
                        extra_args.extend([
                            "--hybrid-hancom-ai-regionlist-strategy",
                            hybrid_hancom_ai_regionlist_strategy,
                        ])
                    if hybrid_hancom_ai_image_cache:
                        extra_args.extend([
                            "--hybrid-hancom-ai-image-cache",
                            hybrid_hancom_ai_image_cache,
                        ])
                args = _build_cli_args(
                    pdf,
                    out_dir,
                    pages=pages,
                    quiet=quiet,
                    use_struct_tree=use_struct_tree,
                    extra_args=extra_args,
                )
                _run_cli_extract(
                    args,
                    quiet=quiet,
                    timeout_seconds=timeout_seconds,
                    backend_label="hybrid",
                )
                json_path = _find_json_output(out_dir, pdf)
                document = json.loads(json_path.read_text(encoding="utf-8"))
        else:
            args = _build_cli_args(
                pdf,
                out_dir,
                pages=pages,
                quiet=quiet,
                use_struct_tree=use_struct_tree,
            )
            _run_cli_extract(
                args,
                quiet=quiet,
                timeout_seconds=timeout_seconds,
                backend_label="native",
            )
            json_path = _find_json_output(out_dir, pdf)
            document = json.loads(json_path.read_text(encoding="utf-8"))

        return _build_extraction_result(
            backend=backend,
            pdf=pdf,
            pages=pages,
            output_dir=out_dir,
            json_path=json_path,
            document=document,
        )
