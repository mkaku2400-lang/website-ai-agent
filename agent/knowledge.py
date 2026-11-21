"""Load the business's own information (FAQ, price list, policies) into a search index."""

from __future__ import annotations

from pathlib import Path

from .retrieval.pdf_loader import chunk_document, extract_pages
from .retrieval.vector_store import SearchHit, VectorStore


def load_knowledge(path: Path) -> VectorStore:
    """Build a search index from a .md, .txt or .pdf file.

    FAQ files written as "Q: ... / A: ..." are split one question per chunk,
    which gives the most precise answers.
    """
    if not path.exists():
        raise FileNotFoundError(f"Knowledge file not found: {path}")
    if path.suffix.lower() == ".pdf":
        pages = extract_pages(str(path))
    else:
        pages = [path.read_text(encoding="utf-8")]
    chunks = chunk_document(pages)
    if not chunks:
        raise ValueError(f"No text found in {path}")
    return VectorStore(chunks)


def format_excerpts(hits: list[SearchHit]) -> str:
    if not hits:
        return "(Nothing in the business information matches this message.)"
    return "\n\n".join(f"[{i}] {hit.chunk.text}" for i, hit in enumerate(hits, start=1))
