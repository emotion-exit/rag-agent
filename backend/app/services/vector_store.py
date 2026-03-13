import os
import uuid
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings
from app.services.embedding import get_embedding, get_embeddings

# Singleton ChromaDB client
_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None
COLLECTION_NAME = "knowledge_base"


def _get_chroma_max_batch_size(collection: chromadb.Collection) -> int:
    client = getattr(collection, "_client", None)
    getter = getattr(client, "get_max_batch_size", None)

    if callable(getter):
        try:
            value = int(getter())
            if value > 0:
                return value
        except Exception:
            pass

    return 5000


def _build_where_clause(metadata_filters: dict[str, str] | None) -> dict | None:
    if not metadata_filters:
        return None

    clauses = []
    for key, value in metadata_filters.items():
        normalized = value.strip()
        if normalized:
            clauses.append({key: {"$eq": normalized}})

    if not clauses:
        return None

    if len(clauses) == 1:
        return clauses[0]

    return {"$and": clauses}


def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _client is None:
        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    if _collection is None:
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_documents(
    chunks: list[str],
    metadatas: list[dict],
    doc_id: str,
) -> int:
    """Embed and store document chunks in the vector store."""
    collection = _get_collection()
    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    embeddings = get_embeddings(chunks)
    max_batch_size = _get_chroma_max_batch_size(collection)

    for start in range(0, len(chunks), max_batch_size):
        end = start + max_batch_size
        collection.add(
            ids=ids[start:end],
            documents=chunks[start:end],
            embeddings=embeddings[start:end],
            metadatas=metadatas[start:end],
        )

    return len(chunks)


def query_documents(
    query: str,
    n_results: int = 5,
    metadata_filters: dict[str, str] | None = None,
) -> list[dict]:
    """Search for relevant documents using semantic similarity."""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    query_embedding = get_embedding(query)
    where = _build_where_clause(metadata_filters)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
        where=where,
    )
    docs = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        docs.append({"content": doc, "metadata": meta, "distance": dist})
    return docs


def get_document_chunk(doc_id: str, chunk_index: int) -> dict | None:
    """Return a single stored chunk by document id and chunk index."""
    collection = _get_collection()
    result = collection.get(
        where={
            "$and": [
                {"doc_id": {"$eq": doc_id}},
                {"chunk_index": {"$eq": chunk_index}},
            ]
        },
        include=["documents", "metadatas"],
    )

    if not result["ids"]:
        return None

    return {
        "id": result["ids"][0],
        "content": result["documents"][0],
        "metadata": result["metadatas"][0],
    }


def delete_document(doc_id: str) -> int:
    """Delete all chunks belonging to a document."""
    collection = _get_collection()
    existing = collection.get(where={"doc_id": {"$eq": doc_id}})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
        return len(existing["ids"])
    return 0


def list_documents() -> list[dict]:
    """Return a deduplicated list of documents stored in the vector store."""
    collection = _get_collection()
    all_items = collection.get(include=["metadatas"])
    seen: dict[str, dict] = {}
    for meta in all_items["metadatas"]:
        doc_id = meta.get("doc_id", "")
        if doc_id and doc_id not in seen:
            seen[doc_id] = meta
    return list(seen.values())


def collection_count() -> int:
    return _get_collection().count()
