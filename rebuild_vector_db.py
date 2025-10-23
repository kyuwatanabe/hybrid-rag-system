"""
Rebuild vector database with new PDF
"""

from pdf_processor import PDFProcessor
from vector_store import VectorStore
import time

# PDF file path
pdf_path = "米国ビザ申請の手引きVer.21..pdf"

print("\n" + "="*60)
print("Rebuilding Vector Database")
print("="*60)
print(f"PDF: {pdf_path}")
print("="*60 + "\n")

start_time = time.time()

# Step 1: Process PDF
print("Step 1: Processing PDF...")
processor = PDFProcessor()
chunks, embeddings = processor.process_pdf(pdf_path)

elapsed = time.time() - start_time
print(f"\nPDF processing completed in {elapsed:.1f} seconds")
print(f"Generated {len(chunks)} chunks")

# Step 2: Create and save vector store
print("\nStep 2: Creating vector store...")
vector_store = VectorStore()
vector_store.create_index(embeddings, chunks)
vector_store.save_index()

total_time = time.time() - start_time
print("\n" + "="*60)
print("Vector Database Rebuilt Successfully!")
print(f"Total time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
print(f"Total chunks: {len(chunks)}")
print("="*60 + "\n")

print("Next steps:")
print("1. Restart the web application:")
print("   python app.py")
print("2. Or test the RAG system:")
print("   python test_rag_simple.py")
