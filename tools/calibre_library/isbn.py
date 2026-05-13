from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

ISBN10_RE = re.compile(r"(?<!\d)(\d[\d\s-]{8,}[0-9Xx])(?!\d)")
ISBN13_RE = re.compile(r"(?<!\d)(97[89][\d\s-]{10,}[0-9Xx])(?!\d)")


@dataclass(frozen=True)
class IsbnCandidate:
    isbn: str
    canonical_isbn: str
    raw: str
    source_kind: str
    source_label: str
    page_number: int | None
    confidence: float


def _clean_isbn(value: str) -> str:
    return re.sub(r"[^0-9Xx]", "", value).upper()


def isbn10_checksum(value: str) -> bool:
    if len(value) != 10:
        return False
    total = 0
    for index, char in enumerate(value[:9], start=1):
        if not char.isdigit():
            return False
        total += index * int(char)
    check = value[9]
    if check == "X":
        total += 10 * 10
    elif check.isdigit():
        total += 10 * int(check)
    else:
        return False
    return total % 11 == 0


def isbn13_checksum(value: str) -> bool:
    if len(value) != 13 or not value.isdigit():
        return False
    total = 0
    for index, char in enumerate(value[:12]):
        digit = int(char)
        total += digit if index % 2 == 0 else digit * 3
    expected = (10 - (total % 10)) % 10
    return expected == int(value[12])


def isbn10_to_isbn13(value: str) -> str | None:
    if len(value) != 10 or not isbn10_checksum(value):
        return None
    core = "978" + value[:9]
    total = 0
    for index, char in enumerate(core):
        digit = int(char)
        total += digit if index % 2 == 0 else digit * 3
    check = (10 - (total % 10)) % 10
    return core + str(check)


def normalize_isbn(raw: str) -> str | None:
    cleaned = _clean_isbn(raw)
    if len(cleaned) == 13 and isbn13_checksum(cleaned):
        return cleaned
    if len(cleaned) == 10 and isbn10_checksum(cleaned):
        return cleaned
    return None


def canonical_isbn(raw: str) -> str | None:
    cleaned = normalize_isbn(raw)
    if cleaned is None:
        return None
    if len(cleaned) == 13:
        return cleaned
    return isbn10_to_isbn13(cleaned) or cleaned


def _candidate_pattern_matches(text: str) -> Iterable[str]:
    patterns = (
        ISBN13_RE,
        ISBN10_RE,
    )
    for pattern in patterns:
        for match in pattern.finditer(text):
            yield match.group(1)


def find_isbn_candidates(
    text: str,
    source_kind: str,
    source_label: str,
    page_number: int | None = None,
    confidence: float = 0.0,
) -> list[IsbnCandidate]:
    seen: set[str] = set()
    candidates: list[IsbnCandidate] = []
    for raw in _candidate_pattern_matches(text):
        isbn = normalize_isbn(raw)
        if isbn is None or isbn in seen:
            continue
        seen.add(isbn)
        candidates.append(
            IsbnCandidate(
                isbn=isbn,
                canonical_isbn=canonical_isbn(isbn) or isbn,
                raw=raw,
                source_kind=source_kind,
                source_label=source_label,
                page_number=page_number,
                confidence=confidence,
            )
        )
    return candidates


def find_isbn_candidates_in_strings(
    strings: Iterable[str],
    source_kind: str,
    source_label: str,
    page_number: int | None = None,
    confidence: float = 0.0,
) -> list[IsbnCandidate]:
    candidates: list[IsbnCandidate] = []
    for value in strings:
        candidates.extend(
            find_isbn_candidates(
                value,
                source_kind=source_kind,
                source_label=source_label,
                page_number=page_number,
                confidence=confidence,
            )
        )
    return candidates

