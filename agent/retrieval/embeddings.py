"""Local text embeddings: hashed TF-IDF vectors.

Runs fully offline with only NumPy, so indexing costs nothing and works on any
machine. Each text becomes a fixed-size, L2-normalised vector; the dot product
of two vectors is their cosine similarity.

This is keyword-weighted matching. To upgrade a client project to semantic
embeddings, replace this class with one exposing the same `fit_transform` and
`transform` methods.
"""

from __future__ import annotations

import re
import zlib
from collections import Counter

import numpy as np

DIMENSIONS = 8192

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    """a an and are as at be but by can do does for from had has have how i if in is it its
    me my of on or our so that the their them there these they this to was we were what when
    where which who why will with would you your about any am been did get got into just not
    than then too very also""".split()
)


def _stem(word: str) -> str:
    """Tiny suffix stripper so 'shipping', 'ships' and 'shipped' all match 'ship'."""
    if len(word) <= 4:
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and not word.endswith("ss"):
            word = word[: -len(suffix)]
            break
    if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "aeiouls":
        word = word[:-1]
    return word


# Customers rarely use the document's exact wording. These map common support
# vocabulary onto one shared term so "delivery" finds "shipping", and so on.
# Extend both tables with a client's own product and industry terms.
_PHRASES = {
    "money back": "refund",
    "get in touch": "contact",
    "send back": "return",
    "how much": "cost",
}
_CANONICAL_TERMS = {
    "deliver": "ship", "delivery": "ship", "shipment": "ship", "dispatch": "ship", "arrive": "ship",
    "price": "cost", "pric": "cost", "fee": "cost", "charge": "cost",
    "reimburse": "refund", "reimbursement": "refund",
    "guarantee": "warranty", "broken": "defect", "faulty": "defect", "defective": "defect",
    "open": "hour", "opening": "hour", "close": "hour", "closed": "hour",
    "reach": "contact", "talk": "contact", "speak": "contact",
    "pay": "payment", "paid": "payment",
    "exchange": "return", "cancellation": "cancel",
    "abroad": "international", "overseas": "international", "worldwide": "international",
    "coupon": "discount", "promo": "discount",
}


def tokenize(text: str) -> list[str]:
    """Lower-cased, stemmed words plus two-word phrases."""
    text = text.lower()
    for phrase, replacement in _PHRASES.items():
        text = text.replace(phrase, replacement)
    words = [_stem(w) for w in _TOKEN.findall(text) if w not in _STOPWORDS]
    words = [_CANONICAL_TERMS.get(w, w) for w in words]
    phrases = [f"{a}_{b}" for a, b in zip(words, words[1:])]
    return words + phrases


def _bucket(token: str) -> int:
    return zlib.crc32(token.encode("utf-8")) % DIMENSIONS


class HashedTfidfEmbedder:
    def __init__(self) -> None:
        self._idf = np.ones(DIMENSIONS, dtype=np.float32)

    def _term_counts(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), DIMENSIONS), dtype=np.float32)
        for row, text in enumerate(texts):
            for token, count in Counter(tokenize(text)).items():
                # Sub-linear term frequency: repeating a word helps, but not endlessly.
                matrix[row, _bucket(token)] += 1.0 + np.log(count)
        return matrix

    def _weight_and_normalise(self, counts: np.ndarray) -> np.ndarray:
        vectors = counts * self._idf
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (vectors / norms).astype(np.float32)

    def fit_transform(self, texts: list[str]) -> np.ndarray:
        """Learn word rarity from the document and return one vector per text."""
        counts = self._term_counts(texts)
        document_frequency = (counts > 0).sum(axis=0)
        self._idf = (np.log((1 + len(texts)) / (1 + document_frequency)) + 1.0).astype(np.float32)
        return self._weight_and_normalise(counts)

    def transform(self, texts: list[str]) -> np.ndarray:
        return self._weight_and_normalise(self._term_counts(texts))
