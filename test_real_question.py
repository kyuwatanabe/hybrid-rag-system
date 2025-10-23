"""
Test with multiple real questions from the PDF
"""

from rag_system import RAGSystem
import time

# Initialize RAG system
print("Initializing RAG system...")
rag = RAGSystem()

# Load knowledge base
rag.load_knowledge_base()

# Test queries that should be in the PDF
test_queries = [
    "ビザウェーバープログラムとは何ですか？",
    "入国審査で必要な書類は何ですか？",
    "滞在期間の延長はできますか？"
]

for i, query in enumerate(test_queries, 1):
    print(f"\n\n{'='*60}")
    print(f"テスト {i}/{len(test_queries)}")
    print(f"{'='*60}")

    result = rag.answer_question(query)

    print(f"\n質問: {result['query']}")
    print("-" * 60)
    print(f"\n回答:\n{result['answer']}")
    print(f"\n参照した情報源: {result['num_sources']}件")

    if result['sources']:
        print("\n【出典】")
        for source in result['sources']:
            print(f"  - {source['file_name']} (ページ {source['page_num']})")

    if i < len(test_queries):
        time.sleep(1)  # Wait 1 second between requests

print(f"\n\n{'='*60}")
print("全てのテスト完了")
print(f"{'='*60}")
