"""
Startup initialization script for Railway deployment
Automatically builds vector database if it doesn't exist
"""

import os
import glob
from pdf_processor import PDFProcessor
from vector_store import VectorStore


def check_and_build_vector_db():
    """
    Check if vector database exists, and build it if missing

    Returns:
        bool: True if vector DB is ready, False otherwise
    """
    vector_db_path = './vector_db/faiss_index.bin'
    reference_docs_dir = './reference_docs'

    print("\n" + "="*60)
    print("Startup: Checking Vector Database")
    print("="*60)

    # Check if vector DB already exists
    if os.path.exists(vector_db_path):
        print(f"✓ Vector database found: {vector_db_path}")
        print("="*60 + "\n")
        return True

    print(f"✗ Vector database not found: {vector_db_path}")
    print("Attempting to build vector database automatically...")

    # Check if reference_docs directory exists
    if not os.path.exists(reference_docs_dir):
        print(f"✗ ERROR: Reference docs directory not found: {reference_docs_dir}")
        print("Cannot build vector database without PDF files.")
        print("="*60 + "\n")
        return False

    # Find PDF files in reference_docs
    pdf_files = glob.glob(os.path.join(reference_docs_dir, '*.pdf'))

    if not pdf_files:
        print(f"✗ ERROR: No PDF files found in {reference_docs_dir}")
        print("Cannot build vector database without PDF files.")
        print("="*60 + "\n")
        return False

    print(f"✓ Found {len(pdf_files)} PDF file(s):")
    for pdf in pdf_files:
        print(f"  - {os.path.basename(pdf)}")

    # Build vector database
    try:
        print("\nBuilding vector database (this may take several minutes)...")
        print("-" * 60)

        all_chunks = []
        all_embeddings = None

        # Process each PDF file
        processor = PDFProcessor()

        for pdf_file in pdf_files:
            print(f"\nProcessing: {os.path.basename(pdf_file)}")
            chunks, embeddings = processor.process_pdf(pdf_file)

            if all_embeddings is None:
                all_embeddings = embeddings
                all_chunks = chunks
            else:
                import numpy as np
                all_embeddings = np.vstack([all_embeddings, embeddings])
                all_chunks.extend(chunks)

        print(f"\nTotal chunks from all PDFs: {len(all_chunks)}")

        # Create and save vector store
        print("\nCreating vector store...")
        vector_store = VectorStore()
        vector_store.create_index(all_embeddings, all_chunks)
        vector_store.save_index()

        print("\n" + "="*60)
        print("✓ Vector database built successfully!")
        print(f"Total chunks: {len(all_chunks)}")
        print("="*60 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ ERROR building vector database: {e}")
        print("="*60 + "\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # Can be run standalone for testing
    success = check_and_build_vector_db()
    if success:
        print("Vector database is ready!")
    else:
        print("Failed to prepare vector database.")
        exit(1)
