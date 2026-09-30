"""Local Markdown ingestion keeps source IDs stable and chunks deterministic."""

from pathlib import Path

from app.ingestion.chunkers import OVERLAP, SIZE, chunk_document
from app.ingestion.docs_loader import load_markdown


def test_markdown_loader_and_chunker(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    body = "A" * 600
    (docs_dir / "guide.md").write_text(f"---\ntitle: Example\n---\n{body}", encoding="utf-8")
    docs = load_markdown(tmp_path)
    assert len(docs) == 1
    assert docs[0].id == "docs/guide.md"
    assert docs[0].content == body
    chunks = chunk_document(docs[0])
    assert len(chunks) == 2
    assert len(chunks[0]) == SIZE
    assert chunks[0][-OVERLAP:] == chunks[1][:OVERLAP]
    assert docs == load_markdown(tmp_path)
