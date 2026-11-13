import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from utils.normalizer import normalize_test_cases

logger = logging.getLogger(__name__)

# Cosine distance below which two test cases are flagged as duplicates
# (cosine similarity >= 0.925). Override with DUPLICATE_DISTANCE_THRESHOLD.
DEFAULT_DUPLICATE_DISTANCE = 0.075
NEIGHBOURS_PER_QUERY = 3


def _embedding_model(provider: str) -> str:
    return "gemini-embedding-001" if provider == "gemini" else "text-embedding-3-small"


def embed_texts(texts: List[str], api_key: Optional[str] = None, provider: str = "openai",
                model_name: Optional[str] = None) -> List[List[float]]:
    """Embed texts with the configured provider. Raises on any failure so callers can fall back."""
    provider = (provider or "openai").lower()
    model_name = model_name or _embedding_model(provider)
    started_at = time.perf_counter()

    if provider == "gemini":
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY is not configured.")
        from google import genai

        result = genai.Client(api_key=key).models.embed_content(model=model_name, contents=list(texts))
        vectors = [list(embedding.values) for embedding in result.embeddings]
    else:
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is not configured.")
        from openai import OpenAI

        timeout_seconds = float(os.getenv("OPENAI_EMBEDDING_TIMEOUT", "45"))
        client = OpenAI(api_key=key, timeout=timeout_seconds)
        result = client.embeddings.create(model=model_name, input=list(texts), encoding_format="float")
        vectors = [item.embedding for item in result.data]

    logger.info("%s embeddings completed in %.2fs", provider, time.perf_counter() - started_at)
    return vectors


def _test_case_document(tc: Dict[str, Any]) -> str:
    steps = " ".join(f"{s.get('action', '')} {s.get('expected_result', '')}" for s in tc.get("steps", []))
    return f"Title: {tc.get('title', '')}\nPreconditions: {tc.get('preconditions', '')}\nSteps: {steps}"


def find_duplicate_test_cases(
    test_cases: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    provider: str = "openai",
    threshold: Optional[float] = None,
) -> List[Tuple[str, str, float]]:
    """
    Use ChromaDB semantic search to detect duplicate/redundant test cases.
    Returns a list of (tc_id_1, tc_id_2, cosine_distance) tuples.
    Falls back to title-overlap heuristics if embeddings or ChromaDB are unavailable.
    """
    test_cases = normalize_test_cases(test_cases)
    if len(test_cases) < 2:
        return []
    threshold = threshold if threshold is not None else float(
        os.getenv("DUPLICATE_DISTANCE_THRESHOLD", DEFAULT_DUPLICATE_DISTANCE)
    )

    # De-duplicate IDs: Chroma rejects repeated IDs, and LLMs occasionally reuse them.
    seen_ids = set()
    ids, documents = [], []
    for tc in test_cases:
        tc_id = tc["test_case_id"]
        if tc_id in seen_ids:
            continue
        seen_ids.add(tc_id)
        ids.append(tc_id)
        documents.append(_test_case_document(tc))
    if len(ids) < 2:
        return []

    try:
        import chromadb

        embeddings = embed_texts(documents, api_key=api_key, provider=provider)
        # In-memory client + unique collection: concurrent Streamlit sessions cannot clobber each other.
        client = chromadb.EphemeralClient()
        collection = client.create_collection(
            name=f"test_cases_{uuid.uuid4().hex[:12]}",
            metadata={"hnsw:space": "cosine"},
        )
        try:
            collection.add(ids=ids, documents=documents, embeddings=embeddings)
            results = collection.query(
                query_embeddings=embeddings,
                n_results=min(NEIGHBOURS_PER_QUERY, len(ids)),
            )
        finally:
            try:
                client.delete_collection(collection.name)
            except Exception:  # noqa: BLE001 - cleanup is best effort
                pass

        duplicate_pairs: List[Tuple[str, str, float]] = []
        seen_pairs = set()
        for tc_id, neighbour_ids, distances in zip(ids, results["ids"], results["distances"]):
            for other_id, dist in zip(neighbour_ids, distances):
                if other_id == tc_id:
                    continue
                pair = tuple(sorted((tc_id, other_id)))
                if pair not in seen_pairs and dist < threshold:
                    seen_pairs.add(pair)
                    duplicate_pairs.append((pair[0], pair[1], float(dist)))
        return duplicate_pairs

    except Exception as exc:  # noqa: BLE001 - never let duplicate detection break the pipeline
        logger.warning("Semantic duplicate detection unavailable, using title-overlap fallback: %s", exc)
        return fallback_duplicate_detection(test_cases)


def fallback_duplicate_detection(test_cases: List[Dict[str, Any]], min_jaccard: float = 0.8) -> List[Tuple[str, str, float]]:
    """Jaccard-similarity duplicate checker on test case titles, used when embeddings are unavailable."""
    test_cases = normalize_test_cases(test_cases)
    duplicate_pairs: List[Tuple[str, str, float]] = []
    seen = set()

    for i in range(len(test_cases)):
        words1 = set(test_cases[i]["title"].lower().split())
        if not words1:
            continue
        for j in range(i + 1, len(test_cases)):
            words2 = set(test_cases[j]["title"].lower().split())
            if not words2:
                continue
            jaccard = len(words1 & words2) / len(words1 | words2)
            if jaccard > min_jaccard:
                pair = tuple(sorted((test_cases[i]["test_case_id"], test_cases[j]["test_case_id"])))
                if pair[0] != pair[1] and pair not in seen:
                    seen.add(pair)
                    duplicate_pairs.append((pair[0], pair[1], 1.0 - jaccard))

    return duplicate_pairs
