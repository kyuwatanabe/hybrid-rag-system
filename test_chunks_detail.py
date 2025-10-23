"""
Check what chunks are retrieved with hybrid search
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

# Get chunks using hybrid search (same as the actual system)
relevant_chunks = rag.search_relevant_chunks(query, k=30)

output = []
output.append("=" * 80)
output.append(f"質問: {query}")
output.append("=" * 80)
output.append(f"\n取得されたチャンク数: {len(relevant_chunks)}\n")

for i, chunk in enumerate(relevant_chunks, 1):
    output.append(f"【チャンク {i}】")
    output.append(f"ファイル: {chunk['file_name']}")
    output.append(f"ページ: {chunk['page_num']}")
    output.append(f"ベクトルスコア: {chunk.get('vector_score', 0):.4f}")
    output.append(f"キーワードスコア: {chunk.get('keyword_score', 0):.4f}")
    output.append(f"統合スコア: {chunk.get('combined_score', 0):.4f}")
    output.append(f"内容:\n{chunk['text']}")
    output.append("-" * 80)
    output.append("")

# Write to file
with open("chunks_detail_hybrid.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print(f"詳細をchunks_detail_hybrid.txtに保存しました ({len(relevant_chunks)}件)")
