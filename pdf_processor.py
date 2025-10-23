"""
PDF Processor for RAG System
Extracts text from PDFs, chunks it, and removes semantic duplicates
"""

import os
import re
import fitz  # PyMuPDF
import numpy as np
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', 800))
CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', 100))
SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', 0.93))


class PDFProcessor:
    def __init__(self):
        """Initialize PDF processor with embedding model"""
        print("Loading embedding model...")
        self.embedding_model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')
        print("Embedding model loaded successfully")

    def extract_text_from_pdf(self, pdf_path: str) -> List[Dict]:
        """
        Extract text from PDF with page numbers

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of dicts containing text and metadata
        """
        print(f"Extracting text from: {pdf_path}")

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = fitz.open(pdf_path)
        pages_data = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()

            # Clean up text
            text = self._clean_text(text)

            if text.strip():  # Only add non-empty pages
                pages_data.append({
                    'text': text,
                    'page_num': page_num + 1,  # 1-indexed
                    'file_name': os.path.basename(pdf_path)
                })

        doc.close()
        print(f"Extracted {len(pages_data)} pages")
        return pages_data

    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove page numbers (standalone numbers)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        return text.strip()

    def create_chunks(self, pages_data: List[Dict]) -> List[Dict]:
        """
        Create overlapping text chunks from pages

        Args:
            pages_data: List of page data with text and metadata

        Returns:
            List of chunks with metadata
        """
        print(f"Creating chunks (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})...")

        chunks = []

        for page_data in pages_data:
            text = page_data['text']
            page_num = page_data['page_num']
            file_name = page_data['file_name']

            # Split text into sentences for better chunking
            sentences = self._split_into_sentences(text)

            current_chunk = ""
            current_length = 0

            for sentence in sentences:
                sentence_length = len(sentence)

                # If adding this sentence exceeds chunk size
                if current_length + sentence_length > CHUNK_SIZE and current_chunk:
                    # Save current chunk
                    chunks.append({
                        'text': current_chunk.strip(),
                        'page_num': page_num,
                        'file_name': file_name
                    })

                    # Start new chunk with overlap
                    # Keep last CHUNK_OVERLAP characters for overlap
                    if len(current_chunk) > CHUNK_OVERLAP:
                        overlap_text = current_chunk[-CHUNK_OVERLAP:]
                        current_chunk = overlap_text + " " + sentence
                        current_length = len(overlap_text) + sentence_length
                    else:
                        current_chunk = sentence
                        current_length = sentence_length
                else:
                    current_chunk += " " + sentence if current_chunk else sentence
                    current_length += sentence_length

            # Add remaining chunk
            if current_chunk.strip():
                chunks.append({
                    'text': current_chunk.strip(),
                    'page_num': page_num,
                    'file_name': file_name
                })

        print(f"Created {len(chunks)} chunks")
        return chunks

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences (simple Japanese-aware split)"""
        # Split on Japanese and English sentence endings
        sentences = re.split(r'([。！？\.\!\?])', text)

        # Recombine sentences with their punctuation
        result = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                result.append(sentences[i] + sentences[i + 1])
            else:
                result.append(sentences[i])

        # Filter out very short sentences
        result = [s.strip() for s in result if len(s.strip()) > 10]
        return result

    def remove_semantic_duplicates(self, chunks: List[Dict]) -> Tuple[List[Dict], np.ndarray]:
        """
        Remove semantically similar chunks using clustering

        Args:
            chunks: List of text chunks with metadata

        Returns:
            Tuple of (filtered chunks, embeddings for filtered chunks)
        """
        print(f"Removing semantic duplicates (threshold={SIMILARITY_THRESHOLD})...")

        if not chunks:
            return [], np.array([])

        # Generate embeddings for all chunks
        texts = [chunk['text'] for chunk in chunks]
        print(f"Generating embeddings for {len(texts)} chunks...")
        embeddings = self.embedding_model.encode(texts, show_progress_bar=True)

        # Compute pairwise cosine similarities
        similarities = cosine_similarity(embeddings)

        # Find duplicates
        to_keep = set(range(len(chunks)))

        for i in range(len(chunks)):
            if i not in to_keep:
                continue

            for j in range(i + 1, len(chunks)):
                if j not in to_keep:
                    continue

                # If similarity exceeds threshold, remove the later one
                if similarities[i][j] >= SIMILARITY_THRESHOLD:
                    to_keep.discard(j)

        # Filter chunks and embeddings
        filtered_chunks = [chunks[i] for i in sorted(to_keep)]
        filtered_embeddings = embeddings[list(sorted(to_keep))]

        removed_count = len(chunks) - len(filtered_chunks)
        print(f"Removed {removed_count} duplicate chunks")
        print(f"Kept {len(filtered_chunks)} unique chunks")

        return filtered_chunks, filtered_embeddings

    def process_pdf(self, pdf_path: str) -> Tuple[List[Dict], np.ndarray]:
        """
        Complete PDF processing pipeline

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (chunks with metadata, embeddings)
        """
        print("\n" + "="*60)
        print("Starting PDF processing pipeline")
        print("="*60 + "\n")

        # Step 1: Extract text from PDF
        pages_data = self.extract_text_from_pdf(pdf_path)

        # Step 2: Create chunks
        chunks = self.create_chunks(pages_data)

        # Step 3: Remove semantic duplicates
        filtered_chunks, embeddings = self.remove_semantic_duplicates(chunks)

        print("\n" + "="*60)
        print("PDF processing completed")
        print(f"Final output: {len(filtered_chunks)} unique chunks")
        print("="*60 + "\n")

        return filtered_chunks, embeddings


def main():
    """Test the PDF processor"""
    # Test with the existing PDF
    pdf_path = "../faq_system/reference_docs/第2章.pdf"

    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        print("Please update the path or create a symlink to reference_docs")
        return

    processor = PDFProcessor()
    chunks, embeddings = processor.process_pdf(pdf_path)

    # Display sample chunks
    print("\nSample chunks:")
    print("-" * 60)
    for i, chunk in enumerate(chunks[:3]):
        print(f"\nChunk {i+1}:")
        print(f"Page: {chunk['page_num']}, File: {chunk['file_name']}")
        print(f"Text: {chunk['text'][:200]}...")
        print(f"Length: {len(chunk['text'])} characters")

    print(f"\nEmbedding shape: {embeddings.shape}")
    print(f"Total chunks: {len(chunks)}")


if __name__ == "__main__":
    main()
