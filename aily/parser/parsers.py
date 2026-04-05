from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParseResult:
    title: str
    markdown: str
    source_type: str


def _extract_title(raw_text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", raw_text, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip())
    m = re.search(r"<h1[^>]*>(.*?)</h1>", raw_text, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1)).strip())
    return "Untitled"


def parse_kimi(url: str, raw_text: str) -> ParseResult:
    return ParseResult(title=_extract_title(raw_text), markdown=raw_text, source_type="kimi")


def parse_monica(url: str, raw_text: str) -> ParseResult:
    return ParseResult(title=_extract_title(raw_text), markdown=raw_text, source_type="monica")


def parse_arxiv(url: str, raw_text: str) -> ParseResult:
    return ParseResult(title=_extract_title(raw_text), markdown=raw_text, source_type="arxiv")


def parse_github(url: str, raw_text: str) -> ParseResult:
    return ParseResult(title=_extract_title(raw_text), markdown=raw_text, source_type="github")


def parse_youtube(url: str, raw_text: str) -> ParseResult:
    return ParseResult(title=_extract_title(raw_text), markdown=raw_text, source_type="youtube")


def parse_generic(url: str, raw_text: str) -> ParseResult:
    return ParseResult(title=_extract_title(raw_text), markdown=raw_text, source_type="generic")
