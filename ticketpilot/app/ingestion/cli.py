"""Index local Markdown files into Postgres for the active embedding model."""

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.db import get_sessionmaker
from app.ingestion.chunkers import STRATEGY, chunk_document
from app.ingestion.docs_loader import load_markdown
from app.ingestion.gemini_embedder import GeminiEmbedder
from app.models import Chunk, Document
from app.settings import get_settings


async def ingest(root: Path) -> tuple[int, int]:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is required for ingestion")
    if settings.active_strategy != STRATEGY:
        raise ValueError(f"only {STRATEGY} is implemented")
    docs = load_markdown(root)
    embedder = GeminiEmbedder(settings.gemini_api_key, settings.active_embed_model)
    chunk_count = 0
    for doc in docs:
        parts = chunk_document(doc)
        vectors = [await embedder.embed_document(part) for part in parts]
        chunk_ids = [
            f"{doc.id}#{index}@{STRATEGY}:{settings.active_embed_model}"
            for index in range(len(parts))
        ]
        async with get_sessionmaker()() as session, session.begin():
            doc_values = {"id": doc.id, "title": doc.title, "source_sha": doc.source_sha}
            doc_stmt = insert(Document).values(**doc_values)
            await session.execute(
                doc_stmt.on_conflict_do_update(
                    index_elements=[Document.id],
                    set_={"title": doc.title, "source_sha": doc.source_sha},
                )
            )
            await session.execute(
                delete(Chunk).where(
                    Chunk.doc_id == doc.id,
                    Chunk.strategy == STRATEGY,
                    Chunk.embed_model == settings.active_embed_model,
                    Chunk.id.not_in(chunk_ids),
                )
            )
            for chunk_id, content, vector in zip(chunk_ids, parts, vectors, strict=True):
                values = {
                    "id": chunk_id,
                    "doc_id": doc.id,
                    "strategy": STRATEGY,
                    "embed_model": settings.active_embed_model,
                    "content": content,
                    "embedding": vector,
                }
                stmt = insert(Chunk).values(**values)
                await session.execute(
                    stmt.on_conflict_do_update(
                        index_elements=[Chunk.id],
                        set_={"content": content, "embedding": vector},
                    )
                )
        chunk_count += len(parts)
    return len(docs), chunk_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Markdown from a local checkout")
    parser.add_argument("source", type=Path, help="directory containing Markdown files")
    args = parser.parse_args()
    doc_count, chunk_count = asyncio.run(ingest(args.source))
    print(f"Indexed {doc_count} documents and {chunk_count} chunks")


if __name__ == "__main__":
    main()
