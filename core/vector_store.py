"""Lightweight transcript index with optional FAISS backend."""

from typing import List, Dict, Any


class TranscriptIndex:
    """Store transcripts and support simple semantic/keyword search.

    FAISS + embeddings are used if available; otherwise we fall back to a
    simple substring filter over the in-memory list. This keeps the runtime
    tolerant when optional deps or API keys are missing.
    """

    def __init__(self):
        self._use_faiss = False
        self._entries: List[Dict[str, Any]] = []
        self._vector_store = None
        self._embedding_model = None

        try:
            from langchain_community.vectorstores import FAISS  # type: ignore
            from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore

            self._embedding_model = HuggingFaceEmbeddings()
            self._vector_store = FAISS.from_texts([], self._embedding_model)
            self._use_faiss = True
        except Exception:
            # Optional dependency not available; fall back to in-memory list.
            self._use_faiss = False

    def add(self, text: str, metadata: Dict[str, Any]):
        """Add a transcript to the index."""
        entry = {"text": text, **metadata}
        self._entries.append(entry)
        if self._use_faiss and self._vector_store is not None:
            try:
                self._vector_store.add_texts([text], [metadata])
            except Exception:
                # If FAISS insert fails, silently degrade to list-only.
                self._use_faiss = False

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search transcripts and return best matches."""
        if self._use_faiss and self._vector_store is not None:
            try:
                docs = self._vector_store.similarity_search(query, k=k)
                results = []
                for doc in docs:
                    results.append(
                        {
                            "text": doc.page_content,
                            **(doc.metadata or {}),
                        }
                    )
                return results
            except Exception:
                # fall through to keyword search
                pass
        # Keyword fallback: filter by substring and return most recent first
        matches = [e for e in self._entries if query.lower() in e.get("text", "").lower()]
        return list(reversed(matches))[:k]

    def last(self, n: int = 10) -> List[Dict[str, Any]]:
        return list(self._entries[-n:])

