"""Read a PDF and split it into searchable chunks."""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_CHUNK_CHARS = 900
MIN_FAQ_QUESTIONS = 3

# A line that starts a FAQ entry: "Q:", "Q1.", "Question 3:" ...
_QUESTION_MARKER = re.compile(r"(?m)^[ \t]*Q(?:uestion)?[ \t]*\d*[ \t]*[:.]")
# Where the answer of a FAQ entry begins: "A:" or "Answer:"
ANSWER_MARKER = re.compile(r"(?:^|\s)A(?:nswer)?\s*:\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class PDFError(Exception):
    """A problem with the uploaded PDF, with a message safe to show the user."""


@dataclass(frozen=True)
class Chunk:
    text: str
    page: int  # 1-based page where the chunk starts
    title: str = ""  # the question, for FAQ entries; weighted higher in search


def extract_pages(file: BinaryIO | str) -> list[str]:
    """Return the text of every page. Raises PDFError if the PDF is unusable."""
    try:
        reader = PdfReader(file)
        if reader.is_encrypted:
            raise PDFError("This PDF is password-protected. Please upload an unlocked copy.")
        pages = [(page.extract_text() or "") for page in reader.pages]
    except PDFError:
        raise
    except (PyPdfError, ValueError, OSError) as exc:
        raise PDFError(f"This file could not be read as a PDF ({exc}).") from exc

    if not any(page.strip() for page in pages):
        raise PDFError(
            "No text was found in this PDF. It may be a scanned image; "
            "please upload a text-based PDF."
        )
    return pages


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]


def _pack_sentences(text: str) -> list[str]:
    """Group sentences into chunks of up to MAX_CHUNK_CHARS, overlapping by one sentence."""
    sentences: list[str] = []
    for sentence in split_sentences(" ".join(text.split())):
        # A "sentence" with no punctuation (tables, lists) can be huge; hard-split it.
        for start in range(0, len(sentence), MAX_CHUNK_CHARS):
            sentences.append(sentence[start : start + MAX_CHUNK_CHARS])

    chunks: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        if current and len(" ".join(current)) + len(sentence) + 1 > MAX_CHUNK_CHARS:
            chunks.append(" ".join(current))
            current = [current[-1]] if len(current[-1]) < MAX_CHUNK_CHARS // 3 else []
        current.append(sentence)
    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_document(pages: list[str]) -> list[Chunk]:
    """Split page texts into chunks.

    FAQ-style documents are split one question/answer pair per chunk, which
    gives the most precise retrieval. Everything else is split by sentences.
    """
    full_text = ""
    page_starts: list[int] = []
    for page in pages:
        page_starts.append(len(full_text))
        full_text += page.replace("\r", "") + "\n"

    def page_of(offset: int) -> int:
        return bisect_right(page_starts, offset)

    question_starts = [m.start() for m in _QUESTION_MARKER.finditer(full_text)]
    if len(question_starts) >= MIN_FAQ_QUESTIONS:
        boundaries = [0, *question_starts, len(full_text)]
    else:
        boundaries = [0, len(full_text)]

    chunks: list[Chunk] = []
    for start, end in zip(boundaries, boundaries[1:]):
        segment = " ".join(full_text[start:end].split())
        if not segment:
            continue
        is_faq_entry = start in question_starts
        if is_faq_entry and len(segment) <= MAX_CHUNK_CHARS * 2:
            answer = ANSWER_MARKER.search(segment)
            title = segment[: answer.start()] if answer else ""
            chunks.append(Chunk(text=segment, page=page_of(start), title=title))
            continue
        # Plain text: find each piece again in the original so its page number is right.
        cursor = start
        for piece in _pack_sentences(segment):
            found = full_text.find(piece[:40], cursor, end)
            if found != -1:
                cursor = found
            chunks.append(Chunk(text=piece, page=page_of(cursor)))
    return chunks
