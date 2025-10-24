"""
Vector Store for RAG System
Handles FAISS index creation, storage, and retrieval
"""

import os
import pickle
import numpy as np
import faiss
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
VECTOR_DB_PATH = os.getenv('VECTOR_DB_PATH', './vector_db/faiss_index.bin')
TOP_K_CHUNKS = int(os.getenv('TOP_K_CHUNKS', 10))
FINAL_CHUNKS = int(os.getenv('FINAL_CHUNKS', 5))


class VectorStore:
    def __init__(self):
        """Initialize vector store with embedding model"""
        print("Loading embedding model for vector store...")
        self.embedding_model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')
        self.index = None
        self.chunks_metadata = []
        print("Vector store initialized")

    def create_index(self, embeddings: np.ndarray, chunks: List[Dict]):
        """
        Create FAISS index from embeddings

        Args:
            embeddings: Numpy array of embeddings (N x D)
            chunks: List of chunk metadata
        """
        print(f"Creating FAISS index with {len(embeddings)} vectors...")

        # Get embedding dimension
        dimension = embeddings.shape[1]

        # Create FAISS index (L2 distance)
        self.index = faiss.IndexFlatL2(dimension)

        # Add vectors to index
        self.index.add(embeddings.astype('float32'))

        # Store metadata
        self.chunks_metadata = chunks

        print(f"FAISS index created successfully")
        print(f"Index size: {self.index.ntotal} vectors")

    def save_index(self, path: str = None):
        """
        Save FAISS index and metadata to disk

        Args:
            path: Path to save the index (default: VECTOR_DB_PATH)
        """
        if path is None:
            path = VECTOR_DB_PATH

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)

        print(f"Saving FAISS index to: {path}")

        # Save FAISS index
        faiss.write_index(self.index, path)

        # Save metadata
        metadata_path = path.replace('.bin', '_metadata.pkl')
        with open(metadata_path, 'wb') as f:
            pickle.dump(self.chunks_metadata, f)

        print(f"Index and metadata saved successfully")

    def load_index(self, path: str = None):
        """
        Load FAISS index and metadata from disk

        Args:
            path: Path to the index file (default: VECTOR_DB_PATH)
        """
        if path is None:
            path = VECTOR_DB_PATH

        if not os.path.exists(path):
            # Try to auto-build if it does not exist
            print(f"[WARNING] Vector database not found: {path}")
            print("[INFO] Attempting to auto-build vector database...")
            try:
                from startup_init import check_and_build_vector_db
                if not check_and_build_vector_db():
                    raise FileNotFoundError(f"Failed to build vector database: {path}")
                # Retry after building
                if not os.path.exists(path):
                    raise FileNotFoundError(f"Vector database still not found after build: {path}")
            except ImportError:
                raise FileNotFoundError(f"Index file not found and cannot auto-build: {path}")

        print(f"Loading FAISS index from: {path}")

        # Load FAISS index
        self.index = faiss.read_index(path)

        # Load metadata
        metadata_path = path.replace('.bin', '_metadata.pkl')
        with open(metadata_path, 'rb') as f:
            self.chunks_metadata = pickle.load(f)

        print(f"Index loaded successfully")
        print(f"Index size: {self.index.ntotal} vectors")
        print(f"Metadata size: {len(self.chunks_metadata)} chunks")

    def search(self, query: str, k: int = None) -> List[Dict]:
        """
        Search for similar chunks using a query

        Args:
            query: Search query text
            k: Number of results to return (default: TOP_K_CHUNKS)

        Returns:
            List of chunks with similarity scores
        """
        if k is None:
            k = TOP_K_CHUNKS

        if self.index is None:
            raise ValueError("Index not loaded. Call load_index() first.")

        print(f"Searching for: {query[:50]}...")

        # Encode query
        query_embedding = self.embedding_model.encode([query])

        # Search in FAISS
        distances, indices = self.index.search(query_embedding.astype('float32'), k)

        # Prepare results
        results = []
        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < len(self.chunks_metadata):
                chunk = self.chunks_metadata[idx].copy()
                # Convert L2 distance to similarity score (inverse)
                chunk['distance'] = float(distance)
                chunk['similarity'] = 1 / (1 + float(distance))
                chunk['rank'] = i + 1
                results.append(chunk)

        print(f"Found {len(results)} results")
        return results

    def filter_and_deduplicate(self, results: List[Dict], final_k: int = None) -> List[Dict]:
        """
        Filter and deduplicate search results

        Args:
            results: Search results from search()
            final_k: Number of final results to return (default: FINAL_CHUNKS)

        Returns:
            Filtered and deduplicated list of chunks
        """
        if final_k is None:
            final_k = FINAL_CHUNKS

        # Sort by similarity (higher is better)
        sorted_results = sorted(results, key=lambda x: x['similarity'], reverse=True)

        # Deduplicate by text similarity
        filtered = []
        seen_texts = set()

        for result in sorted_results:
            text_normalized = result['text'].strip().lower()

            # Check if we've seen very similar text
            is_duplicate = False
            for seen in seen_texts:
                # Simple character overlap check
                if self._text_overlap(text_normalized, seen) > 0.9:
                    is_duplicate = True
                    break

            if not is_duplicate:
                filtered.append(result)
                seen_texts.add(text_normalized)

                if len(filtered) >= final_k:
                    break

        print(f"Filtered to {len(filtered)} unique chunks")
        return filtered

    def _text_overlap(self, text1: str, text2: str) -> float:
        """Calculate text overlap ratio"""
        if not text1 or not text2:
            return 0.0

        # Simple character-based overlap
        set1 = set(text1)
        set2 = set(text2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def add_faq_to_index(self, question: str, answer: str, faq_id: str = None):
        """
        Add FAQ Q&A pair to the vector index

        Args:
            question: FAQ question
            answer: FAQ answer
            faq_id: Optional FAQ ID for tracking
        """
        if self.index is None:
            raise ValueError("Index not loaded. Call load_index() first.")

        # Combine question and answer for better semantic matching
        combined_text = f"質問: {question}\n回答: {answer}"

        # Vectorize the FAQ
        embedding = self.embedding_model.encode([combined_text])

        # Add to FAISS index
        self.index.add(embedding.astype('float32'))

        # Add metadata
        faq_metadata = {
            'text': combined_text,
            'question': question,
            'answer': answer,
            'source': 'FAQ',
            'type': 'faq',
            'faq_id': faq_id
        }
        self.chunks_metadata.append(faq_metadata)

        print(f"[OK] Added FAQ to index: {question[:50]}...")

    def rebuild_with_faqs(self, faq_list: List[Dict]):
        """
        Rebuild the entire index including all FAQs

        Args:
            faq_list: List of FAQ dicts with 'question' and 'answer' keys
        """
        if self.index is None:
            raise ValueError("Index not loaded. Call load_index() first.")

        print(f"\n[INFO] Rebuilding index with {len(faq_list)} FAQs...")

        # Get existing PDF chunks (non-FAQ)
        pdf_chunks = [chunk for chunk in self.chunks_metadata if chunk.get('type') != 'faq']
        print(f"[INFO] Existing PDF chunks: {len(pdf_chunks)}")

        # Create list for all chunks
        all_chunks = pdf_chunks.copy()
        all_texts = []

        # Add PDF chunk texts
        for chunk in pdf_chunks:
            all_texts.append(chunk['text'])

        # Add FAQ texts
        for faq in faq_list:
            combined_text = f"質問: {faq['question']}\n回答: {faq['answer']}"
            all_texts.append(combined_text)

            faq_metadata = {
                'text': combined_text,
                'question': faq['question'],
                'answer': faq['answer'],
                'source': 'FAQ',
                'type': 'faq',
                'timestamp': faq.get('timestamp', '')
            }
            all_chunks.append(faq_metadata)

        print(f"[INFO] Total chunks (PDF + FAQ): {len(all_chunks)}")

        # Vectorize all texts
        print(f"[INFO] Vectorizing {len(all_texts)} texts...")
        embeddings = self.embedding_model.encode(all_texts, show_progress_bar=True)

        # Recreate index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings.astype('float32'))

        # Update metadata
        self.chunks_metadata = all_chunks

        print(f"[OK] Index rebuilt successfully")
        print(f"[OK] Total vectors in index: {self.index.ntotal}")

        # Save updated index
        self.save_index()
        print(f"[OK] Updated index saved")

    def keyword_search(self, query: str, k: int = None) -> List[Dict]:
        """
        Keyword-based search through all chunks (improved for Japanese)

        Args:
            query: Search query text
            k: Number of results to return

        Returns:
            List of chunks with keyword match scores
        """
        if k is None:
            k = TOP_K_CHUNKS

        if not self.chunks_metadata:
            return []

        # Extract keywords from query
        # For Japanese text, extract meaningful substrings (n-grams + recognizable patterns)
        keywords = []

        # Add space-separated words
        words = [w for w in query.split() if len(w) > 1]
        keywords.extend(words)

        # Extract alphanumeric patterns (like E-2, L-1, etc.)
        import re
        alphanumeric = re.findall(r'[A-Za-z0-9\-]+', query)
        keywords.extend([w for w in alphanumeric if len(w) > 1])

        # Extract common Japanese patterns (2-4 character sequences)
        japanese_chars = re.findall(r'[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]+', query)
        for word in japanese_chars:
            if len(word) >= 2:
                keywords.append(word)
                # Also add 2-3 character substrings for partial matching
                for i in range(len(word) - 1):
                    if i + 2 <= len(word):
                        keywords.append(word[i:i+2])
                    if i + 3 <= len(word):
                        keywords.append(word[i:i+3])

        # Remove duplicates and convert to lowercase
        keywords = list(set([kw.lower() for kw in keywords if len(kw) >= 2]))

        if not keywords:
            return []

        results = []
        for idx, chunk in enumerate(self.chunks_metadata):
            text_lower = chunk['text'].lower()

            # Count keyword matches with scoring
            match_score = 0
            matched_keywords = []
            for kw in keywords:
                if kw in text_lower:
                    # Longer keywords get higher scores
                    weight = len(kw) / 10.0  # Normalize by length
                    match_score += weight
                    matched_keywords.append(kw)

            if match_score > 0:
                chunk_copy = chunk.copy()
                chunk_copy['keyword_score'] = min(match_score, 1.0)  # Cap at 1.0
                chunk_copy['keyword_matches'] = len(matched_keywords)
                chunk_copy['matched_keywords'] = matched_keywords
                chunk_copy['chunk_idx'] = idx
                results.append(chunk_copy)

        # Sort by keyword score
        results = sorted(results, key=lambda x: x['keyword_score'], reverse=True)

        return results[:k]

    def hybrid_search(self, query: str, k: int = None, alpha: float = 0.5) -> List[Dict]:
        """
        Hybrid search combining vector and keyword search

        Args:
            query: Search query text
            k: Number of results to return
            alpha: Weight for vector search (1-alpha for keyword search)
                   0.0 = keyword only, 1.0 = vector only, 0.5 = equal weight

        Returns:
            List of chunks with combined scores
        """
        if k is None:
            k = TOP_K_CHUNKS

        print(f"Hybrid search: query='{query[:50]}...', k={k}, alpha={alpha}")

        # Get vector search results
        vector_results = self.search(query, k=k*2)  # Get more candidates

        # Get keyword search results
        keyword_results = self.keyword_search(query, k=k*2)

        # Create a mapping of chunk index to scores
        score_map = {}

        # Add vector scores
        for result in vector_results:
            # Find the chunk index
            chunk_idx = None
            for idx, chunk in enumerate(self.chunks_metadata):
                if chunk['text'] == result['text']:
                    chunk_idx = idx
                    break

            if chunk_idx is not None:
                if chunk_idx not in score_map:
                    score_map[chunk_idx] = {'chunk': result, 'vector_score': 0, 'keyword_score': 0}
                score_map[chunk_idx]['vector_score'] = result['similarity']
                score_map[chunk_idx]['chunk'] = result

        # Add keyword scores
        for result in keyword_results:
            chunk_idx = result.get('chunk_idx')
            if chunk_idx is not None:
                if chunk_idx not in score_map:
                    # Need to get the full chunk
                    chunk = self.chunks_metadata[chunk_idx].copy()
                    score_map[chunk_idx] = {'chunk': chunk, 'vector_score': 0, 'keyword_score': 0}
                score_map[chunk_idx]['keyword_score'] = result['keyword_score']

        # Combine scores
        combined_results = []
        for chunk_idx, scores in score_map.items():
            chunk = scores['chunk'].copy()

            # Normalize and combine scores
            vector_score = scores['vector_score']
            keyword_score = scores['keyword_score']

            # Combined score using weighted average
            combined_score = alpha * vector_score + (1 - alpha) * keyword_score

            chunk['vector_score'] = vector_score
            chunk['keyword_score'] = keyword_score
            chunk['combined_score'] = combined_score
            chunk['similarity'] = combined_score  # Use combined score as similarity

            combined_results.append(chunk)

        # Sort by combined score
        combined_results = sorted(combined_results, key=lambda x: x['combined_score'], reverse=True)

        print(f"Hybrid search found {len(combined_results)} results (vector: {len(vector_results)}, keyword: {len(keyword_results)})")

        return combined_results[:k]


def main():
    """Test the vector store"""
    from pdf_processor import PDFProcessor

    # Process PDF
    pdf_path = "../faq_system/reference_docs/第2章.pdf"

    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return

    print("\n" + "="*60)
    print("Testing Vector Store")
    print("="*60 + "\n")

    # Step 1: Process PDF
    processor = PDFProcessor()
    chunks, embeddings = processor.process_pdf(pdf_path)

    # Step 2: Create and save index
    vector_store = VectorStore()
    vector_store.create_index(embeddings, chunks)
    vector_store.save_index()

    print("\n" + "="*60)
    print("Testing Search")
    print("="*60 + "\n")

    # Step 3: Test search
    test_queries = [
        "ビザの申請方法は？",
        "入国審査について教えてください",
        "滞在期間はどのくらいですか？"
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 60)

        results = vector_store.search(query, k=5)

        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"  Page: {result['page_num']}, File: {result['file_name']}")
            print(f"  Similarity: {result['similarity']:.4f}")
            print(f"  Text: {result['text'][:150]}...")

    print("\n" + "="*60)
    print("Vector Store Test Completed")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
