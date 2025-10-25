"""
Startup initialization script for Railway deployment
Automatically builds vector database if it doesn't exist or if PDFs are updated
"""

import os
import glob
import json
from pdf_processor import PDFProcessor
from vector_store import VectorStore


def get_pdf_metadata(pdf_files):
    """
    Get metadata for PDF files (filename and modification time)

    Args:
        pdf_files: List of PDF file paths

    Returns:
        dict: Dictionary mapping filename to modification time
    """
    metadata = {}
    for pdf_file in pdf_files:
        filename = os.path.basename(pdf_file)
        mtime = os.path.getmtime(pdf_file)
        metadata[filename] = mtime
    return metadata


def check_pdf_updates(pdf_files, vector_db_dir='./vector_db'):
    """
    Check if PDFs have been updated since last vector DB build

    Args:
        pdf_files: List of current PDF file paths
        vector_db_dir: Directory where vector DB is stored

    Returns:
        bool: True if PDFs have been updated, False otherwise
    """
    metadata_path = os.path.join(vector_db_dir, 'pdf_metadata.json')

    # If metadata doesn't exist, consider it as updated
    if not os.path.exists(metadata_path):
        return True

    # Load previous metadata
    try:
        with open(metadata_path, 'r') as f:
            prev_metadata = json.load(f)
    except Exception as e:
        print(f"[WARNING] Could not read PDF metadata: {e}")
        return True

    # Get current metadata
    current_metadata = get_pdf_metadata(pdf_files)

    # Check if PDF list or modification times have changed
    if set(prev_metadata.keys()) != set(current_metadata.keys()):
        print("[INFO] PDF file list has changed")
        return True

    for filename, mtime in current_metadata.items():
        if filename not in prev_metadata:
            print(f"[INFO] New PDF detected: {filename}")
            return True
        if abs(prev_metadata[filename] - mtime) > 1:  # Allow 1 second tolerance
            print(f"[INFO] PDF updated: {filename}")
            return True

    print("[INFO] No PDF updates detected")
    return False


def save_pdf_metadata(pdf_files, vector_db_dir='./vector_db'):
    """
    Save PDF metadata to track updates

    Args:
        pdf_files: List of PDF file paths
        vector_db_dir: Directory where vector DB is stored
    """
    os.makedirs(vector_db_dir, exist_ok=True)
    metadata_path = os.path.join(vector_db_dir, 'pdf_metadata.json')

    metadata = get_pdf_metadata(pdf_files)

    try:
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"[INFO] PDF metadata saved to {metadata_path}")
    except Exception as e:
        print(f"[WARNING] Could not save PDF metadata: {e}")


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

    # Find PDF files first
    if not os.path.exists(reference_docs_dir):
        print(f"✗ ERROR: Reference docs directory not found: {reference_docs_dir}")
        print("="*60 + "\n")
        return False

    pdf_files = glob.glob(os.path.join(reference_docs_dir, '*.pdf'))

    if not pdf_files:
        print(f"✗ ERROR: No PDF files found in {reference_docs_dir}")
        print("="*60 + "\n")
        return False

    print(f"✓ Found {len(pdf_files)} PDF file(s):")
    for pdf in pdf_files:
        print(f"  - {os.path.basename(pdf)}")

    # Check if vector DB exists AND PDFs haven't been updated
    vector_db_exists = os.path.exists(vector_db_path)
    pdfs_updated = check_pdf_updates(pdf_files)

    if vector_db_exists and not pdfs_updated:
        print(f"✓ Vector database is up-to-date: {vector_db_path}")
        print("✓ No PDF updates detected - skipping rebuild")
        print("="*60 + "\n")
        return True

    if vector_db_exists and pdfs_updated:
        print(f"✓ Vector database exists: {vector_db_path}")
        print("⚠ PDF updates detected - rebuilding vector database...")
    else:
        print(f"✗ Vector database not found: {vector_db_path}")
    print("Attempting to build vector database automatically...")

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

        # Save PDF metadata to track updates
        save_pdf_metadata(pdf_files)

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
