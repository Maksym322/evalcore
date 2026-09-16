"""A trivial keyword-match retrieval target for the EvalCore toy example.

Receives ``item.input`` (never the reference). Returns the predicted category as ``answer``
and the ids of corpus docs whose text contains any query word as ``retrieved_ids``.
"""

from typing import Any


def answer(input: dict[str, Any]) -> dict[str, Any]:
    query_words = input["query"].lower().split()
    corpus: dict[str, str] = input["corpus"]
    hits = [
        doc_id
        for doc_id, text in corpus.items()
        if any(word in text.lower() for word in query_words)
    ]
    return {"answer": input.get("category_guess", "general"), "retrieved_ids": hits}
