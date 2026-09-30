"""Read Markdown documents from a local checkout without following links outside it."""

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceDocument:
    id: str
    title: str
    content: str
    source_sha: str


def load_markdown(root: Path) -> list[SourceDocument]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("document source must be a directory")
    docs: list[SourceDocument] = []
    for path in sorted(root.rglob("*.md")):
        if not path.is_file() or not path.resolve().is_relative_to(root):
            continue
        raw = path.read_text(encoding="utf-8-sig")
        content = _strip_frontmatter(raw).strip()
        if not content:
            continue
        doc_id = path.relative_to(root).as_posix()
        docs.append(
            SourceDocument(
                id=doc_id,
                title=path.stem,
                content=content,
                source_sha=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            )
        )
    return docs


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    return text[end + 5 :] if end >= 0 else text
