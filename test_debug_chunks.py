"""
Debug: Check what chunks are being retrieved for E-2 visa question
"""

import sys
sys.path.append('.')

from rag_system import RAGSystem

# Initialize RAG system
rag = RAGSystem()
rag.load_knowledge_base()

query = "E-2ビザの申請条件を教えて。"

print("=" * 80)
print(f"質問: {query}")
print("=" * 80)

# Search for relevant chunks
relevant_chunks = rag.search_relevant_chunks(query, k=10)

print(f"\n取得されたチャンク数: {len(relevant_chunks)}\n")

for i, chunk in enumerate(relevant_chunks, 1):
    print(f"【チャンク {i}】")
    print(f"ファイル: {chunk['file_name']}")
    print(f"ページ: {chunk['page_num']}")
    print(f"類似度: {chunk.get('similarity', 0.0):.4f}")
    print(f"内容:\n{chunk['text']}")
    print("-" * 80)
    print()
