"""
Simple test for RAG system with one question
"""

from rag_system import RAGSystem

# Initialize RAG system
print("Initializing RAG system...")
rag = RAGSystem()

# Load knowledge base
rag.load_knowledge_base()

# Test with one question
query = "ビザの申請方法について教えてください"

result = rag.answer_question(query)

print(f"\n質問: {result['query']}")
print("=" * 60)
print(f"\n回答:\n{result['answer']}")
print(f"\n参照した情報源: {result['num_sources']}件")

if result['sources']:
    print("\n【出典詳細】")
    for source in result['sources']:
        print(f"  {source['number']}. {source['file_name']} (ページ {source['page_num']})")
        print(f"     類似度: {source['similarity']:.4f}")

print("\n" + "="*60)
