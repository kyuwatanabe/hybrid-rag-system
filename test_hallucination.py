"""
Test hallucination prevention
Test with a question that is NOT in the PDF
"""

from rag_system import RAGSystem

# Initialize RAG system
print("Initializing RAG system...")
rag = RAGSystem()

# Load knowledge base
rag.load_knowledge_base()

# Test with a question NOT in the PDF (hallucination test)
query = "東京の人口は何人ですか？"

print(f"\n【ハルシネーションテスト】")
print(f"質問: {query}")
print("（この質問はPDFには書かれていません）")
print("=" * 60)

result = rag.answer_question(query)

print(f"\n回答:\n{result['answer']}")
print(f"\n参照した情報源: {result['num_sources']}件")

if result['sources']:
    print("\n【出典詳細】")
    for source in result['sources']:
        print(f"  {source['number']}. {source['file_name']} (ページ {source['page_num']})")

print("\n" + "="*60)
print("\n期待される動作: 「提供された資料に記載されておりません」と回答すること")
