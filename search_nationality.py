"""
Search for nationality-related chunks
"""
import sys
sys.path.append('.')

from rag_system import RAGSystem

# Initialize RAG system
rag = RAGSystem()
rag.load_knowledge_base()

# Search with nationality-related terms
queries = [
    "E-2ビザ 国籍",
    "E-2ビザ 条約国",
    "E-2 nationality requirement",
    "E-2ビザの基本的な条件"
]

for query in queries:
    print("=" * 80)
    print(f"検索クエリ: {query}")
    print("=" * 80)

    results = rag.search_relevant_chunks(query, k=5)

    for i, chunk in enumerate(results, 1):
        print(f"\n【チャンク {i}】")
        print(f"ページ: {chunk['page_num']}, 類似度: {chunk.get('similarity', 0):.4f}")
        print(f"内容: {chunk['text'][:200]}...")

    print("\n")
