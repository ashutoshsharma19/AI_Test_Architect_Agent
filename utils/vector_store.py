import os
import chromadb
import time
from chromadb.api.types import Documents, Embeddings, EmbeddingFunction
from openai import OpenAI
from typing import List, Dict, Any, Tuple
from utils.normalizer import normalize_test_cases

class ProviderEmbeddingFunction(EmbeddingFunction):
    """Custom embedding function for ChromaDB that uses the configured provider."""
    def __init__(self, api_key: str = None, provider: str = "openai", model_name: str = None):
        self.api_key = api_key
        self.provider = (provider or "openai").lower()
        self.model_name = model_name or (
            "models/text-embedding-004" if self.provider == "gemini" else "text-embedding-3-small"
        )
        
    def __call__(self, input: Documents) -> Embeddings:
        try:
            if self.provider == "gemini":
                return self._embed_gemini(input)
            return self._embed_openai(input)
        except Exception as e:
            print(f"{self.provider.title()} embeddings unavailable, using fallback duplicate detection embeddings: {e}")
            # Fallback embedding (1536-dimensional based on simple hashing) to prevent pipeline crashes
            embeddings = []
            for text in input:
                words = text.lower().split()
                emb = [0.0] * 1536
                for idx, w in enumerate(words):
                    if idx < 1536:
                        emb[idx] = float(hash(w) % 10000) / 10000.0
                embeddings.append(emb)
            return embeddings

    def _embed_openai(self, input: Documents) -> Embeddings:
        key = self.api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is not configured.")
        timeout_seconds = float(os.getenv("OPENAI_EMBEDDING_TIMEOUT", "45"))
        client = OpenAI(api_key=key, timeout=timeout_seconds)
        started_at = time.perf_counter()
        result = client.embeddings.create(
            model=self.model_name,
            input=list(input),
            encoding_format="float"
        )
        print(f"OpenAI embeddings completed in {time.perf_counter() - started_at:.2f}s")
        return [item.embedding for item in result.data]

    def _embed_gemini(self, input: Documents) -> Embeddings:
        key = self.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY is not configured.")
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError("Gemini provider requires the google-genai package. Install requirements.txt again.") from exc

        client = genai.Client(api_key=key)
        started_at = time.perf_counter()
        result = client.models.embed_content(
            model=self.model_name,
            contents=list(input),
        )
        print(f"Gemini embeddings completed in {time.perf_counter() - started_at:.2f}s")
        return [embedding.values for embedding in result.embeddings]

def init_chroma_client(persist_directory: str = "./.chromadb") -> chromadb.ClientAPI:
    """Initialize a persistent ChromaDB client."""
    return chromadb.PersistentClient(path=persist_directory)

def find_duplicate_test_cases(test_cases: List[Dict[str, Any]], api_key: str = None, provider: str = "openai") -> List[Tuple[str, str, float]]:
    """
    Use ChromaDB to detect semantically duplicate/redundant test cases.
    Returns:
        List of tuples: (tc_id_1, tc_id_2, distance)
    """
    if len(test_cases) < 2:
        return []
    test_cases = normalize_test_cases(test_cases)
        
    try:
        # Initialize client and embedding function
        client = init_chroma_client()
        emb_fn = ProviderEmbeddingFunction(api_key=api_key, provider=provider)
        
        # Reset or get collection
        collection_name = "test_cases_eval"
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass
            
        collection = client.create_collection(
            name=collection_name,
            embedding_function=emb_fn
        )
        
        # Add test cases to ChromaDB
        ids = []
        documents = []
        metadatas = []
        
        for tc in test_cases:
            tc_id = tc.get("test_case_id", "")
            title = tc.get("title", "")
            precond = tc.get("preconditions", "")
            steps = " ".join([s.get("action", "") + " " + s.get("expected_result", "") for s in tc.get("steps", [])])
            
            doc_content = f"Title: {title}\nPreconditions: {precond}\nSteps: {steps}"
            
            ids.append(tc_id)
            documents.append(doc_content)
            metadatas.append({"title": title})
            
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        
        duplicate_pairs = []
        seen = set()
        
        # Query ChromaDB for similar test cases
        for i, tc_id in enumerate(ids):
            query_results = collection.query(
                query_texts=[documents[i]],
                n_results=min(3, len(ids))
            )
            
            # The query results return distances. A very small distance indicates high similarity.
            # In ChromaDB, L2 distance is default. Low distance = high similarity.
            # L2 distance under 0.25 (or cosine distance depending on config) indicates likely duplicates.
            results_ids = query_results.get("ids", [[]])[0]
            distances = query_results.get("distances", [[]])[0]
            
            for other_id, dist in zip(results_ids, distances):
                if other_id != tc_id:
                    # Sort IDs to avoid duplicates (A, B) vs (B, A)
                    pair = tuple(sorted([tc_id, other_id]))
                    if pair not in seen and dist < 0.15: # threshold for duplicate
                        seen.add(pair)
                        duplicate_pairs.append((pair[0], pair[1], float(dist)))
                        
        return duplicate_pairs
        
    except Exception as e:
        print(f"Error in ChromaDB duplicate detection: {e}")
        # Return fallback heuristic-based duplication checks (e.g. title word overlap)
        return fallback_duplicate_detection(test_cases)

def fallback_duplicate_detection(test_cases: List[Dict[str, Any]]) -> List[Tuple[str, str, float]]:
    """Fallback Jaccard-similarity duplicate checker in case ChromaDB fails."""
    test_cases = normalize_test_cases(test_cases)
    duplicate_pairs = []
    seen = set()
    
    for i in range(len(test_cases)):
        for j in range(i + 1, len(test_cases)):
            tc1 = test_cases[i]
            tc2 = test_cases[j]
            
            words1 = set(tc1.get("title", "").lower().split())
            words2 = set(tc2.get("title", "").lower().split())
            
            if not words1 or not words2:
                continue
                
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            jaccard = len(intersection) / len(union)
            
            if jaccard > 0.8: # high Jaccard similarity in title
                id1 = tc1.get("test_case_id", "")
                id2 = tc2.get("test_case_id", "")
                pair = tuple(sorted([id1, id2]))
                if pair not in seen:
                    seen.add(pair)
                    duplicate_pairs.append((pair[0], pair[1], 1.0 - jaccard))
                    
    return duplicate_pairs
