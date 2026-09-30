"""Deterministic fixed-size Markdown chunks, with overlap measured in characters."""

from app.ingestion.docs_loader import SourceDocument

STRATEGY = "fixed_512_50"
SIZE = 512
OVERLAP = 50


def chunk_document(doc: SourceDocument) -> list[str]:
    text = doc.content
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + SIZE, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - OVERLAP
    return chunks
